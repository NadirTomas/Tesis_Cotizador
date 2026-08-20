from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.company_member import CompanyMember
from app.services.company_guard import get_current_company
from app.models.material import Material
from app.models.piece import Piece
from app.models.quotation import Quotation
from app.models.quotation_item import QuotationItem
from app.models.stock_reservation import StockReservation
from app.schemas.quotation_item import QuotationItemCreate, QuotationItemRead, QuotationItemUpdate
from app.services.quotation_calculator import calculate_quotation_item
from app.services.quotation_events import log_event
from app.services.stock_reservations import release_reservation


router = APIRouter(prefix="/quotation-items", tags=["quotation-items"])

_FIELD_LABELS = {"quantity": "Cantidad", "margin_percent": "Margen"}


@router.post("/", response_model=QuotationItemRead)
def create_quotation_item(
    payload: QuotationItemCreate,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
):
    quotation = (
        db.query(Quotation)
        .filter(Quotation.id == payload.quotation_id, Quotation.company_id == member.company_id)
        .first()
    )
    if not quotation:
        raise HTTPException(status_code=404, detail="Quotation not found")
    piece = (
        db.query(Piece)
        .filter(Piece.id == payload.piece_id, Piece.company_id == member.company_id)
        .first()
    )
    if not piece:
        raise HTTPException(status_code=404, detail="Piece not found")
    material = (
        db.query(Material)
        .filter(Material.id == payload.material_id, Material.company_id == member.company_id)
        .first()
    )
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    item = QuotationItem(**payload.dict())
    item.created_by_id = member.user_id
    db.add(item)
    db.flush()
    log_event(
        db, item.quotation_id, "item_added",
        f"Pieza agregada: {piece.name} ×{item.quantity}", member.user_id,
    )
    try:
        calculate_quotation_item(db, item, member.company_id)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return item


@router.get("/quotation/{quotation_id}", response_model=list[QuotationItemRead])
def list_items_by_quotation(
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
    return (
        db.query(QuotationItem)
        .filter(QuotationItem.quotation_id == quotation_id)
        .all()
    )


@router.put("/{item_id}", response_model=QuotationItemRead)
def update_quotation_item(
    item_id: int,
    payload: QuotationItemUpdate,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
):
    item = (
        db.query(QuotationItem)
        .join(Quotation, Quotation.id == QuotationItem.quotation_id)
        .filter(QuotationItem.id == item_id, Quotation.company_id == member.company_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    update_data = payload.dict(exclude_unset=True)
    changes = [f"{_FIELD_LABELS.get(key, key)}: {getattr(item, key)} → {value}" for key, value in update_data.items()]
    for key, value in update_data.items():
        setattr(item, key, value)
    db.flush()
    if changes:
        log_event(db, item.quotation_id, "item_updated", "Ítem actualizado — " + ", ".join(changes), member.user_id)
    try:
        calculate_quotation_item(db, item, member.company_id)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return item


@router.delete("/{item_id}", status_code=204)
def delete_quotation_item(
    item_id: int,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
):
    item = (
        db.query(QuotationItem)
        .join(Quotation, Quotation.id == QuotationItem.quotation_id)
        .filter(QuotationItem.id == item_id, Quotation.company_id == member.company_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    quotation = db.query(Quotation).filter(Quotation.id == item.quotation_id).first()
    piece = db.query(Piece).filter(Piece.id == item.piece_id).first()
    piece_label = piece.name if piece else f"pieza #{item.piece_id}"
    log_event(db, item.quotation_id, "item_removed", f"Pieza eliminada: {piece_label}", member.user_id)

    active_reservation = (
        db.query(StockReservation)
        .filter(StockReservation.quotation_item_id == item.id, StockReservation.status == "ACTIVE")
        .first()
    )
    if active_reservation:
        release_reservation(db, active_reservation, member.user_id)

    db.delete(item)
    db.flush()
    # Recalcular totales
    remaining = db.query(QuotationItem).filter(QuotationItem.quotation_id == quotation.id).all()
    quotation.total_ars = sum(i.total_price_ars for i in remaining)
    if quotation.exchange_rate:
        quotation.total_usd = quotation.total_ars / quotation.exchange_rate
    else:
        quotation.total_usd = 0.0
    db.commit()
