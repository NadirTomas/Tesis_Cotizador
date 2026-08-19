from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.auth_guard import get_current_user
from app.models.material import Material
from app.models.piece import Piece
from app.models.quotation import Quotation
from app.models.quotation_item import QuotationItem
from app.schemas.quotation_item import QuotationItemCreate, QuotationItemRead
from app.services.quotation_calculator import calculate_quotation_item


router = APIRouter(prefix="/quotation-items", tags=["quotation-items"])


@router.post("/", response_model=QuotationItemRead)
def create_quotation_item(
    payload: QuotationItemCreate,
    db: Session = Depends(get_db),
    current_user: int = Depends(get_current_user),
):
    quotation = db.query(Quotation).filter(Quotation.id == payload.quotation_id).first()
    if not quotation:
        raise HTTPException(status_code=404, detail="Quotation not found")
    piece = db.query(Piece).filter(Piece.id == payload.piece_id).first()
    if not piece:
        raise HTTPException(status_code=404, detail="Piece not found")
    material = db.query(Material).filter(Material.id == payload.material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    item = QuotationItem(**payload.dict())
    item.created_by_id = current_user
    db.add(item)
    db.flush()
    try:
        calculate_quotation_item(db, item)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return item


@router.get("/quotation/{quotation_id}", response_model=list[QuotationItemRead])
def list_items_by_quotation(quotation_id: int, db: Session = Depends(get_db)):
    quotation = db.query(Quotation).filter(Quotation.id == quotation_id).first()
    if not quotation:
        raise HTTPException(status_code=404, detail="Quotation not found")
    return (
        db.query(QuotationItem)
        .filter(QuotationItem.quotation_id == quotation_id)
        .all()
    )


@router.delete("/{item_id}", status_code=204)
def delete_quotation_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: int = Depends(get_current_user),
):
    item = db.query(QuotationItem).filter(QuotationItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    quotation = db.query(Quotation).filter(Quotation.id == item.quotation_id).first()
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
