import logging
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.client import Client
from app.models.company_member import CompanyMember
from app.models.quotation import Quotation
from app.models.quotation_event import QuotationEvent
from app.models.stock_reservation import StockReservation
from app.models.user import User
from app.schemas.quotation import QuotationCreate, QuotationRead
from app.schemas.quotation_event import QuotationEventRead
from app.services.pdf_generator import generate_quotation_pdf
from app.services.company_guard import get_current_company
from app.services.quotation_events import log_event
from app.services.stock_reservations import release_reservation


router = APIRouter(prefix="/quotations", tags=["quotations"])
logger = logging.getLogger(__name__)

VALID_TRANSITIONS: dict[str, list[str]] = {
    "draft":     ["sent", "cancelled"],
    "sent":      ["accepted", "cancelled"],
    # "accepted" -> "cancelled": un cliente puede aceptar y después bajarse
    # antes de que se corte el material. Necesario para que la reserva de
    # stock pueda liberarse alguna vez (ver services/stock_reservations.py).
    "accepted":  ["cancelled"],
    "cancelled": [],
}

STATUS_LABELS: dict[str, str] = {
    "draft": "Borrador",
    "sent": "Enviado",
    "accepted": "Aceptado",
    "cancelled": "Cancelado",
}


def _auto_expire(db: Session, company_id: int) -> None:
    """Marca como 'cancelled' las cotizaciones draft con due_date vencida."""
    now = datetime.now()
    expired = (
        db.query(Quotation)
        .filter(
            Quotation.company_id == company_id,
            Quotation.status == "draft",
            Quotation.due_date < now,
        )
        .all()
    )
    for q in expired:
        q.status = "cancelled"
    if expired:
        db.commit()


def _get_active_client(db: Session, client_id: int, company_id: int) -> Client | None:
    return (
        db.query(Client)
        .filter(
            Client.id == client_id,
            Client.company_id == company_id,
            Client.active.is_(True),
        )
        .first()
    )


def _next_number(db: Session, company_id: int) -> str:
    count = db.query(Quotation).filter(Quotation.company_id == company_id).count()
    return f"COT-{count + 1:04d}"


@router.post("/", response_model=QuotationRead)
def create_quotation(
    payload: QuotationCreate,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
):
    client = _get_active_client(db, payload.client_id, member.company_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    quotation = Quotation(
        **payload.dict(),
        number=_next_number(db, member.company_id),
        company_id=member.company_id,
        total_ars=0.0,
        total_usd=0.0,
    )
    quotation.created_by_id = member.user_id
    db.add(quotation)
    db.flush()
    log_event(db, quotation.id, "created", "Cotización creada", member.user_id)
    db.commit()
    db.refresh(quotation)
    return quotation


@router.get("/stats")
def get_stats(
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
):
    _auto_expire(db, member.company_id)
    now = datetime.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    week_ahead = now + timedelta(days=7)

    base = db.query(Quotation).filter(Quotation.company_id == member.company_id)

    total = base.count()

    this_month_query = base.filter(Quotation.issue_date >= month_start)
    this_month = this_month_query.count()
    total_ars_this_month = (
        this_month_query.with_entities(func.coalesce(func.sum(Quotation.total_ars), 0.0)).scalar()
    )

    expiring_soon = base.filter(
        Quotation.status.in_(("draft", "sent")),
        Quotation.due_date.isnot(None),
        Quotation.due_date >= now,
        Quotation.due_date <= week_ahead,
    ).count()

    by_status = dict(
        base.with_entities(Quotation.status, func.count(Quotation.id))
        .group_by(Quotation.status)
        .all()
    )

    recent = base.order_by(Quotation.issue_date.desc()).limit(5).all()

    return {
        "total": total,
        "this_month": this_month,
        "total_ars_this_month": float(total_ars_this_month or 0.0),
        "by_status": by_status,
        "expiring_soon": expiring_soon,
        "recent": [
            {
                "id": q.id,
                "number": q.number,
                "client_id": q.client_id,
                "status": q.status,
                "total_ars": q.total_ars,
                "issue_date": q.issue_date.isoformat(),
            }
            for q in recent
        ],
    }


@router.get("/", response_model=list[QuotationRead])
def list_quotations(
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
):
    _auto_expire(db, member.company_id)
    return (
        db.query(Quotation)
        .filter(Quotation.company_id == member.company_id)
        .order_by(Quotation.issue_date.desc())
        .all()
    )


@router.get("/{quotation_id}", response_model=QuotationRead)
def get_quotation(
    quotation_id: int,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
):
    _auto_expire(db, member.company_id)
    quotation = (
        db.query(Quotation)
        .filter(Quotation.id == quotation_id, Quotation.company_id == member.company_id)
        .first()
    )
    if not quotation:
        raise HTTPException(status_code=404, detail="Quotation not found")
    return quotation


@router.delete("/{quotation_id}", status_code=204)
def delete_quotation(
    quotation_id: int,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
):
    quotation = (
        db.query(Quotation)
        .filter(Quotation.id == quotation_id, Quotation.company_id == member.company_id)
        .first()
    )
    if not quotation:
        raise HTTPException(status_code=404, detail="Quotation not found")
    if quotation.status != "draft":
        raise HTTPException(
            status_code=400,
            detail="Solo se pueden eliminar cotizaciones en estado 'draft'",
        )
    db.delete(quotation)
    db.commit()


@router.patch("/{quotation_id}/status", response_model=QuotationRead)
def update_status(
    quotation_id: int,
    status: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
):
    quotation = (
        db.query(Quotation)
        .filter(Quotation.id == quotation_id, Quotation.company_id == member.company_id)
        .first()
    )
    if not quotation:
        raise HTTPException(status_code=404, detail="Quotation not found")
    allowed = VALID_TRANSITIONS.get(quotation.status, [])
    if status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Transición inválida: '{quotation.status}' → '{status}'.",
        )
    previous_status = quotation.status
    quotation.status = status
    log_event(
        db, quotation.id, "status_changed",
        f"{STATUS_LABELS.get(previous_status, previous_status)} → {STATUS_LABELS.get(status, status)}",
        member.user_id,
    )
    if status == "cancelled":
        active_reservations = (
            db.query(StockReservation)
            .filter(StockReservation.quotation_id == quotation.id, StockReservation.status == "ACTIVE")
            .all()
        )
        for reservation in active_reservations:
            release_reservation(db, reservation, member.user_id)
    db.commit()
    db.refresh(quotation)
    return quotation


@router.get("/{quotation_id}/events", response_model=list[QuotationEventRead])
def list_quotation_events(
    quotation_id: int,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
):
    quotation = (
        db.query(Quotation)
        .filter(Quotation.id == quotation_id, Quotation.company_id == member.company_id)
        .first()
    )
    if not quotation:
        raise HTTPException(status_code=404, detail="Quotation not found")

    rows = (
        db.query(QuotationEvent, User.email)
        .outerjoin(User, User.id == QuotationEvent.created_by_id)
        .filter(QuotationEvent.quotation_id == quotation_id)
        .order_by(QuotationEvent.id.desc())
        .all()
    )
    return [
        QuotationEventRead(
            id=event.id,
            event_type=event.event_type,
            description=event.description,
            created_by_id=event.created_by_id,
            created_by_email=email,
            created_at=event.created_at,
        )
        for event, email in rows
    ]


@router.get("/{quotation_id}/pdf")
def get_quotation_pdf(
    quotation_id: int,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
):
    try:
        # Generar PDF en directorio temporal
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = generate_quotation_pdf(
                db, quotation_id, member.company_id, output_dir=Path(tmpdir)
            )
            pdf_bytes = pdf_path.read_bytes()
    except ValueError:
        raise HTTPException(status_code=404, detail="Quotation not found")
    except Exception:
        logger.exception("Error generating PDF", extra={"quotation_id": quotation_id})
        raise HTTPException(status_code=500, detail="Error generating PDF")

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=quotation_{quotation_id}.pdf"},
    )
