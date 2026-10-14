import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.company_member import CompanyMember
from app.models.delivery_note import DELIVERY_NOTE_STATUSES, DRAFT, DeliveryNote
from app.schemas.delivery_note import (
    DeliveryNoteCreate,
    DeliveryNoteRead,
    DeliveryNoteSummary,
    DeliveryNoteUpdate,
    DeliveryNoteVoid,
    DeliveryStatusRead,
)
from app.services import delivery_notes as service
from app.services.company_guard import get_current_company, require_owner
from app.services.delivery_note_pdf import generate_delivery_note_pdf

router = APIRouter(prefix="/delivery-notes", tags=["delivery-notes"])
logger = logging.getLogger(__name__)

_STATUS_FOR_KIND = {service.NOT_FOUND: 404, service.INVALID: 400, service.CONFLICT: 409}


def _raise_http(exc: service.DeliveryNoteError) -> None:
    raise HTTPException(status_code=_STATUS_FOR_KIND.get(exc.kind, 400), detail=exc.detail) from exc


def _read(db: Session, note: DeliveryNote) -> DeliveryNoteRead:
    data = DeliveryNoteRead.model_validate(note)
    data.total_units = sum(line.quantity for line in note.items)
    if note.status == DRAFT:
        data.cut_confirmed, data.cut_pending_pieces = service.get_note_cut_status(db, note)
    return data


def _summary(note: DeliveryNote) -> DeliveryNoteSummary:
    return DeliveryNoteSummary(
        id=note.id,
        quotation_id=note.quotation_id,
        number=note.number,
        status=note.status,
        issue_date=note.issue_date,
        quotation_number=note.quotation_number,
        client_name=note.client_name,
        total_units=sum(line.quantity for line in note.items),
        created_at=note.created_at,
    )


# Las rutas /quotation/... van antes que /{note_id} para que no se confundan.


@router.get("/quotation/{quotation_id}/status", response_model=DeliveryStatusRead)
def get_quotation_delivery_status(
    quotation_id: int,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
):
    try:
        return service.get_delivery_status(db, member.company_id, quotation_id)
    except service.DeliveryNoteError as exc:
        _raise_http(exc)


@router.get("/quotation/{quotation_id}", response_model=list[DeliveryNoteSummary])
def list_quotation_delivery_notes(
    quotation_id: int,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
):
    try:
        service.get_delivery_status(db, member.company_id, quotation_id)  # 404 si no es de la empresa
    except service.DeliveryNoteError as exc:
        _raise_http(exc)
    notes = service.list_notes(db, company_id=member.company_id, quotation_id=quotation_id)
    return [_summary(n) for n in notes]


@router.post("/", response_model=DeliveryNoteRead, status_code=201)
def create_delivery_note(
    payload: DeliveryNoteCreate,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
):
    try:
        note = service.create_draft(
            db,
            company_id=member.company_id,
            user_id=member.user_id,
            quotation_id=payload.quotation_id,
            notes=payload.notes,
            lines=[(line.quotation_item_id, line.quantity) for line in payload.items],
        )
        db.commit()
    except service.DeliveryNoteError as exc:
        db.rollback()
        _raise_http(exc)
    db.refresh(note)
    return _read(db, note)


@router.get("/", response_model=list[DeliveryNoteSummary])
def list_delivery_notes(
    status: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
):
    if status is not None and status not in DELIVERY_NOTE_STATUSES:
        raise HTTPException(status_code=400, detail=f"Estado inválido. Valores: {', '.join(DELIVERY_NOTE_STATUSES)}")
    notes = service.list_notes(db, company_id=member.company_id, status=status)
    return [_summary(n) for n in notes]


@router.get("/{note_id}", response_model=DeliveryNoteRead)
def get_delivery_note(
    note_id: int,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
):
    try:
        return _read(db, service.get_note(db, member.company_id, note_id))
    except service.DeliveryNoteError as exc:
        _raise_http(exc)


@router.put("/{note_id}", response_model=DeliveryNoteRead)
def update_delivery_note(
    note_id: int,
    payload: DeliveryNoteUpdate,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
):
    try:
        note = service.update_draft(
            db,
            company_id=member.company_id,
            note_id=note_id,
            notes=payload.notes,
            notes_provided="notes" in payload.model_fields_set,
            lines=None if payload.items is None else [(line.quotation_item_id, line.quantity) for line in payload.items],
        )
        db.commit()
    except service.DeliveryNoteError as exc:
        db.rollback()
        _raise_http(exc)
    db.refresh(note)
    return _read(db, note)


@router.delete("/{note_id}", status_code=204)
def delete_delivery_note(
    note_id: int,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
):
    try:
        service.delete_draft(db, company_id=member.company_id, note_id=note_id)
        db.commit()
    except service.DeliveryNoteError as exc:
        db.rollback()
        _raise_http(exc)


@router.post("/{note_id}/issue", response_model=DeliveryNoteRead)
def issue_delivery_note(
    note_id: int,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
):
    try:
        note = service.issue(db, company_id=member.company_id, user_id=member.user_id, note_id=note_id)
        db.commit()
    except service.DeliveryNoteError as exc:
        db.rollback()
        _raise_http(exc)
    db.refresh(note)
    return _read(db, note)


@router.post("/{note_id}/void", response_model=DeliveryNoteRead)
def void_delivery_note(
    note_id: int,
    payload: DeliveryNoteVoid,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(require_owner),
):
    try:
        note = service.void(
            db, company_id=member.company_id, user_id=member.user_id, note_id=note_id, reason=payload.reason
        )
        db.commit()
    except service.DeliveryNoteError as exc:
        db.rollback()
        _raise_http(exc)
    db.refresh(note)
    return _read(db, note)


@router.get("/{note_id}/pdf")
def get_delivery_note_pdf(
    note_id: int,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
):
    try:
        note = service.get_note(db, member.company_id, note_id)
        pdf_bytes = generate_delivery_note_pdf(db, note.id, member.company_id)
    except service.DeliveryNoteError as exc:
        _raise_http(exc)
    except Exception:
        logger.exception("Error generating delivery note PDF", extra={"delivery_note_id": note_id})
        raise HTTPException(status_code=500, detail="Error generating PDF")

    filename = f"remito_{note.number}.pdf" if note.number else f"remito_borrador_{note.id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
