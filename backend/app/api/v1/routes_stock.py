from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.company_member import CompanyMember
from app.models.material import Material
from app.models.quotation import Quotation
from app.models.stock_sheet import StockSheet
from app.schemas.stock_sheet import StockSheetCreate, StockSheetRead, StockSheetUpdate
from app.services.company_guard import get_current_company, require_owner
from app.services.geometry import measure_geometry, rectangle_geojson

router = APIRouter(prefix="/stock", tags=["stock"])

_DISCARDABLE_STATUSES = ("AVAILABLE", "RESERVED")


def _get_active_material(db: Session, material_id: int, company_id: int) -> Material:
    material = (
        db.query(Material)
        .filter(Material.id == material_id, Material.company_id == company_id, Material.active.is_(True))
        .first()
    )
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    return material


def _next_stock_code(db: Session, company_id: int, stock_type: str) -> str:
    prefix = "CH-" if stock_type == "FULL_SHEET" else "R-"
    count = (
        db.query(StockSheet)
        .filter(StockSheet.company_id == company_id, StockSheet.stock_type == stock_type)
        .count()
    )
    return f"{prefix}{count + 1:04d}"


@router.post("", response_model=StockSheetRead)
def create_stock_sheet(
    payload: StockSheetCreate,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(require_owner),
):
    _get_active_material(db, payload.material_id, member.company_id)

    if payload.source_sheet_id is not None:
        source = (
            db.query(StockSheet)
            .filter(StockSheet.id == payload.source_sheet_id, StockSheet.company_id == member.company_id)
            .first()
        )
        if not source:
            raise HTTPException(status_code=404, detail="Chapa de origen no encontrada")

    if payload.source_quotation_id is not None:
        quotation = (
            db.query(Quotation)
            .filter(Quotation.id == payload.source_quotation_id, Quotation.company_id == member.company_id)
            .first()
        )
        if not quotation:
            raise HTTPException(status_code=404, detail="Cotización de origen no encontrada")

    geojson = payload.geometry or rectangle_geojson(payload.width_mm, payload.height_mm)
    try:
        area_mm2, bbox_w, bbox_h = measure_geometry(geojson)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    for attempt in range(2):
        code = _next_stock_code(db, member.company_id, payload.stock_type)
        stock = StockSheet(
            company_id=member.company_id,
            material_id=payload.material_id,
            code=code,
            stock_type=payload.stock_type,
            status="AVAILABLE",
            original_width_mm=bbox_w,
            original_height_mm=bbox_h,
            original_area_mm2=area_mm2,
            remaining_area_mm2=area_mm2,
            geometry=geojson,
            source_sheet_id=payload.source_sheet_id,
            source_quotation_id=payload.source_quotation_id,
            created_by_id=member.user_id,
        )
        db.add(stock)
        try:
            db.commit()
            break
        except IntegrityError:
            db.rollback()
            if attempt == 1:
                raise HTTPException(
                    status_code=409, detail="No se pudo generar un código único, reintentá."
                )
    db.refresh(stock)
    return stock


@router.get("", response_model=list[StockSheetRead])
def list_stock_sheets(
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
    material_id: int | None = Query(default=None),
    material_type: str | None = Query(default=None),
    alloy: str | None = Query(default=None),
    thickness_mm: float | None = Query(default=None),
    status: str | None = Query(default=None),
    stock_type: str | None = Query(default=None),
):
    query = db.query(StockSheet).filter(StockSheet.company_id == member.company_id)

    if material_id is not None:
        query = query.filter(StockSheet.material_id == material_id)
    if status is not None:
        query = query.filter(StockSheet.status == status)
    if stock_type is not None:
        query = query.filter(StockSheet.stock_type == stock_type)

    if material_type is not None or alloy is not None or thickness_mm is not None:
        query = query.join(Material, Material.id == StockSheet.material_id)
        if material_type is not None:
            query = query.filter(Material.material_type == material_type)
        if alloy is not None:
            query = query.filter(Material.alloy == alloy)
        if thickness_mm is not None:
            query = query.filter(Material.thickness_mm == thickness_mm)

    return query.order_by(StockSheet.id.desc()).all()


@router.get("/{stock_id}", response_model=StockSheetRead)
def get_stock_sheet(
    stock_id: int,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
):
    stock = (
        db.query(StockSheet)
        .filter(StockSheet.id == stock_id, StockSheet.company_id == member.company_id)
        .first()
    )
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    return stock


@router.put("/{stock_id}", response_model=StockSheetRead)
def update_stock_sheet(
    stock_id: int,
    payload: StockSheetUpdate,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(require_owner),
):
    stock = (
        db.query(StockSheet)
        .filter(StockSheet.id == stock_id, StockSheet.company_id == member.company_id)
        .first()
    )
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    if payload.material_id is not None:
        _get_active_material(db, payload.material_id, member.company_id)
        stock.material_id = payload.material_id

    db.commit()
    db.refresh(stock)
    return stock


@router.patch("/{stock_id}/discard", response_model=StockSheetRead)
def discard_stock_sheet(
    stock_id: int,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(require_owner),
):
    stock = (
        db.query(StockSheet)
        .filter(StockSheet.id == stock_id, StockSheet.company_id == member.company_id)
        .first()
    )
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    if stock.status not in _DISCARDABLE_STATUSES:
        raise HTTPException(
            status_code=400, detail=f"No se puede descartar stock en estado '{stock.status}'"
        )
    stock.status = "DISCARDED"
    db.commit()
    db.refresh(stock)
    return stock
