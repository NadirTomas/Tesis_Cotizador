import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.client import Client
from app.models.quotation import Quotation
from app.schemas.quotation import QuotationCreate, QuotationRead
from app.services.pdf_generator import generate_quotation_pdf
from app.services.auth_guard import get_current_user


router = APIRouter(prefix="/quotations", tags=["quotations"])

VALID_TRANSITIONS: dict[str, list[str]] = {
    "draft":     ["sent", "cancelled"],
    "sent":      ["accepted", "cancelled"],
    "accepted":  [],
    "cancelled": [],
}


def _auto_expire(db: Session) -> None:
    """Marca como 'cancelled' las cotizaciones draft con due_date vencida."""
    now = datetime.now()
    expired = (
        db.query(Quotation)
        .filter(Quotation.status == "draft", Quotation.due_date < now)
        .all()
    )
    for q in expired:
        q.status = "cancelled"
    if expired:
        db.commit()


def _get_active_client(db: Session, client_id: int) -> Client | None:
    return (
        db.query(Client)
        .filter(Client.id == client_id, Client.active.is_(True))
        .first()
    )


@router.post("/", response_model=QuotationRead)
def create_quotation(
    payload: QuotationCreate,
    db: Session = Depends(get_db),
    current_user: int = Depends(get_current_user),
):
    client = _get_active_client(db, payload.client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    quotation = Quotation(**payload.dict(), total_ars=0.0, total_usd=0.0)
    quotation.created_by_id = current_user
    db.add(quotation)
    db.commit()
    db.refresh(quotation)
    return quotation


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    from datetime import timedelta
    _auto_expire(db)
    now = datetime.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    week_ahead = now + timedelta(days=7)

    all_q = db.query(Quotation).all()
    this_month = [q for q in all_q if q.issue_date >= month_start]
    expiring = [
        q for q in all_q
        if q.status in ("draft", "sent") and q.due_date and now <= q.due_date <= week_ahead
    ]

    by_status: dict[str, int] = {}
    for q in all_q:
        by_status[q.status] = by_status.get(q.status, 0) + 1

    recent = sorted(all_q, key=lambda q: q.issue_date, reverse=True)[:5]

    return {
        "total": len(all_q),
        "this_month": len(this_month),
        "total_ars_this_month": sum(q.total_ars for q in this_month),
        "by_status": by_status,
        "expiring_soon": len(expiring),
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
def list_quotations(db: Session = Depends(get_db)):
    _auto_expire(db)
    return db.query(Quotation).order_by(Quotation.issue_date.desc()).all()


@router.get("/{quotation_id}", response_model=QuotationRead)
def get_quotation(quotation_id: int, db: Session = Depends(get_db)):
    _auto_expire(db)
    quotation = db.query(Quotation).filter(Quotation.id == quotation_id).first()
    if not quotation:
        raise HTTPException(status_code=404, detail="Quotation not found")
    return quotation


@router.patch("/{quotation_id}/status", response_model=QuotationRead)
def update_status(
    quotation_id: int,
    status: str = Body(..., embed=True),
    db: Session = Depends(get_db),
):
    quotation = db.query(Quotation).filter(Quotation.id == quotation_id).first()
    if not quotation:
        raise HTTPException(status_code=404, detail="Quotation not found")
    allowed = VALID_TRANSITIONS.get(quotation.status, [])
    if status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Transición inválida: '{quotation.status}' → '{status}'.",
        )
    quotation.status = status
    db.commit()
    db.refresh(quotation)
    return quotation


@router.get("/{quotation_id}/pdf")
def get_quotation_pdf(quotation_id: int, db: Session = Depends(get_db)):
    try:
        # Generar PDF en directorio temporal
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = generate_quotation_pdf(db, quotation_id, output_dir=Path(tmpdir))
            pdf_bytes = pdf_path.read_bytes()
    except ValueError:
        raise HTTPException(status_code=404, detail="Quotation not found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Error generating PDF") from exc

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=quotation_{quotation_id}.pdf"},
    )
