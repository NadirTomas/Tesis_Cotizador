import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from shapely import affinity
from shapely.geometry import mapping, shape
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.company import Company
from app.models.company_member import CompanyMember
from app.models.machine_config import MachineConfig
from app.models.material import Material
from app.models.piece import Piece
from app.models.quotation import Quotation
from app.models.stock_movement import StockMovement
from app.models.stock_reservation import StockReservation
from app.models.stock_sheet import StockSheet
from app.schemas.stock_recommendation import StockRecommendation, StockRecommendationRequest
from app.schemas.stock_reservation import (
    ConfirmCutResult,
    RemnantResult,
    ReserveStockRequest,
    StockMovementRead,
    StockReservationRead,
)
from app.schemas.stock_sheet import StockSheetCreate, StockSheetRead, StockSheetUpdate
from app.services.company_guard import get_current_company, require_owner
from app.services.dxf_analysis import extract_piece_polygon
from app.services.geometry import measure_geometry, rectangle_geojson
from app.services.stock_cut import compute_remnants
from app.services.stock_placement import find_placement, occupied_geometry_at
from app.services.stock_recommendation import recommend_stock_for_piece
from app.services.stock_reservations import release_reservation

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


def _log_movement(db, company_id, stock_sheet_id, movement_type, quotation_id=None, created_by_id=None, details=None):
    db.add(
        StockMovement(
            company_id=company_id,
            stock_sheet_id=stock_sheet_id,
            movement_type=movement_type,
            quotation_id=quotation_id,
            created_by_id=created_by_id,
            details=details,
        )
    )


def _extract_piece_polygon_or_400(piece: Piece):
    if not piece.dxf_data:
        raise HTTPException(status_code=400, detail="La pieza no tiene DXF cargado.")
    with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as tmp:
        tmp.write(piece.dxf_data)
        tmp_path = tmp.name
    try:
        return extract_piece_polygon(tmp_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def _get_active_machine_config(db: Session, material_id: int, company_id: int) -> MachineConfig:
    machine_config = (
        db.query(MachineConfig)
        .filter(MachineConfig.material_id == material_id, MachineConfig.company_id == company_id, MachineConfig.active.is_(True))
        .order_by(MachineConfig.id)
        .first()
    )
    if not machine_config:
        raise HTTPException(status_code=400, detail="No hay configuración de máquina activa para este material")
    return machine_config


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
            db.flush()
            break
        except IntegrityError:
            db.rollback()
            if attempt == 1:
                raise HTTPException(
                    status_code=409, detail="No se pudo generar un código único, reintentá."
                )
    _log_movement(db, member.company_id, stock.id, "CREATED", created_by_id=member.user_id)
    db.commit()
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
        _log_movement(
            db, member.company_id, stock.id, "ADJUSTED", created_by_id=member.user_id,
            details={"material_id": payload.material_id},
        )

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
    _log_movement(db, member.company_id, stock.id, "DISCARDED", created_by_id=member.user_id)
    db.commit()
    db.refresh(stock)
    return stock


@router.post("/recommendations", response_model=list[StockRecommendation])
def recommend_stock(
    payload: StockRecommendationRequest,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
):
    """
    Devuelve todas las alternativas de stock compatibles que contienen la
    pieza, ordenadas de mejor a peor score — la primera es "la
    recomendación", el resto son alternativas para que el usuario elija.
    """
    piece = (
        db.query(Piece)
        .filter(Piece.id == payload.piece_id, Piece.company_id == member.company_id)
        .first()
    )
    if not piece:
        raise HTTPException(status_code=404, detail="Piece not found")

    piece_polygon = _extract_piece_polygon_or_400(piece)

    try:
        results = recommend_stock_for_piece(db, member.company_id, piece_polygon, payload.material_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not results:
        raise HTTPException(status_code=404, detail="No hay stock disponible que contenga la pieza")

    recommendations = []
    for result in results:
        # Ancho/alto del bounding box ya rotado (mismo criterio que usa
        # stock_placement.find_placement para reportar x/y) — así el
        # frontend dibuja el rectángulo con las dimensiones correctas para
        # la rotación elegida, no las de la pieza sin rotar.
        rotated_piece = affinity.rotate(piece_polygon, result.rotation, origin="centroid")
        pminx, pminy, pmaxx, pmaxy = rotated_piece.bounds
        recommendations.append(
            StockRecommendation(
                stock_sheet_id=result.stock_sheet.id,
                stock_code=result.stock_sheet.code,
                stock_type=result.stock_sheet.stock_type,
                rotation=result.rotation,
                x=result.x,
                y=result.y,
                piece_area_mm2=result.piece_area_mm2,
                piece_width_mm=round(pmaxx - pminx, 2),
                piece_height_mm=round(pmaxy - pminy, 2),
                stock_remaining_area_mm2=result.stock_sheet.remaining_area_mm2,
                utilization_percent=result.utilization_percent,
                score=result.score,
                reason=result.reason,
            )
        )
    return recommendations


@router.post("/{stock_id}/reserve", response_model=StockReservationRead)
def reserve_stock(
    stock_id: int,
    payload: ReserveStockRequest,
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

    quotation = (
        db.query(Quotation)
        .filter(Quotation.id == payload.quotation_id, Quotation.company_id == member.company_id)
        .first()
    )
    if not quotation:
        raise HTTPException(status_code=404, detail="Quotation not found")
    if quotation.status != "accepted":
        raise HTTPException(
            status_code=400, detail="Solo se puede reservar material contra una cotización aceptada"
        )

    piece = (
        db.query(Piece)
        .filter(Piece.id == payload.piece_id, Piece.company_id == member.company_id)
        .first()
    )
    if not piece:
        raise HTTPException(status_code=404, detail="Piece not found")

    piece_polygon = _extract_piece_polygon_or_400(piece)
    material = _get_active_material(db, payload.material_id, member.company_id)
    machine_config = _get_active_machine_config(db, material.id, member.company_id)

    stock_polygon = shape(stock.geometry)
    placement = find_placement(
        piece_polygon, stock_polygon, machine_config.kerf_mm, machine_config.minimum_spacing_mm
    )
    if placement is None:
        raise HTTPException(status_code=400, detail="La pieza no entra en el stock indicado")

    # UPDATE condicional: atómico ante requests concurrentes, sin locking
    # especial y portable entre SQLite (tests) y Postgres (producción).
    updated = (
        db.query(StockSheet)
        .filter(StockSheet.id == stock_id, StockSheet.status == "AVAILABLE")
        .update({"status": "RESERVED"})
    )
    if updated == 0:
        db.rollback()
        raise HTTPException(status_code=409, detail="El stock ya no está disponible")

    reservation = StockReservation(
        company_id=member.company_id,
        stock_sheet_id=stock.id,
        piece_id=piece.id,
        quotation_id=quotation.id,
        quotation_item_id=payload.quotation_item_id,
        rotation=placement.rotation,
        x=placement.x,
        y=placement.y,
        status="ACTIVE",
        created_by_id=member.user_id,
    )
    db.add(reservation)
    db.flush()
    _log_movement(
        db, member.company_id, stock.id, "RESERVED", quotation_id=quotation.id, created_by_id=member.user_id,
        details={"reservation_id": reservation.id, "rotation": placement.rotation, "x": placement.x, "y": placement.y},
    )
    db.commit()
    db.refresh(reservation)
    return reservation


@router.post("/reservations/{reservation_id}/release", response_model=StockReservationRead)
def release_stock_reservation(
    reservation_id: int,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
):
    reservation = (
        db.query(StockReservation)
        .filter(StockReservation.id == reservation_id, StockReservation.company_id == member.company_id)
        .first()
    )
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    if reservation.status != "ACTIVE":
        raise HTTPException(status_code=400, detail=f"La reserva está en estado '{reservation.status}', no se puede liberar")

    if not release_reservation(db, reservation, member.user_id):
        db.rollback()
        raise HTTPException(status_code=409, detail="La reserva ya fue procesada por otra operación")
    db.commit()
    db.refresh(reservation)
    return reservation


@router.post("/reservations/{reservation_id}/confirm-cut", response_model=ConfirmCutResult)
def confirm_cut(
    reservation_id: int,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
):
    reservation = (
        db.query(StockReservation)
        .filter(StockReservation.id == reservation_id, StockReservation.company_id == member.company_id)
        .first()
    )
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")

    stock = db.query(StockSheet).filter(StockSheet.id == reservation.stock_sheet_id).first()

    if reservation.status == "CONSUMED":
        # Idempotente: ya se había confirmado antes — se reconstruye la misma
        # respuesta sin recalcular ni tocar la geometría de nuevo.
        remnants = (
            db.query(StockSheet)
            .filter(
                StockSheet.source_sheet_id == stock.id,
                StockSheet.source_quotation_id == reservation.quotation_id,
                StockSheet.stock_type == "REMNANT",
            )
            .all()
        )
        return ConfirmCutResult(
            reservation_id=reservation.id,
            stock_sheet_id=stock.id,
            stock_code=stock.code,
            status=stock.status,
            remnants=[
                RemnantResult(stock_sheet_id=r.id, code=r.code, area_mm2=r.original_area_mm2) for r in remnants
            ],
        )

    if reservation.status != "ACTIVE":
        raise HTTPException(
            status_code=400, detail=f"La reserva está en estado '{reservation.status}', no se puede confirmar"
        )

    piece = db.query(Piece).filter(Piece.id == reservation.piece_id).first()
    if not piece:
        raise HTTPException(status_code=404, detail="Piece not found")
    piece_polygon = _extract_piece_polygon_or_400(piece)
    material = _get_active_material(db, stock.material_id, member.company_id)
    machine_config = _get_active_machine_config(db, material.id, member.company_id)

    # UPDATE condicional doble: reserva ACTIVE->CONSUMED y stock RESERVED->CONSUMED.
    # Si cualquiera de los dos afecta 0 filas, otra operación ya lo procesó
    # (doble click, reintento HTTP, request concurrente) — se aborta sin
    # tocar geometría ni crear nada, en vez de consumir dos veces.
    updated_res = (
        db.query(StockReservation)
        .filter(StockReservation.id == reservation_id, StockReservation.status == "ACTIVE")
        .update({"status": "CONSUMED"})
    )
    if updated_res == 0:
        db.rollback()
        raise HTTPException(status_code=409, detail="La reserva ya fue procesada por otra operación")

    updated_stock = (
        db.query(StockSheet)
        .filter(StockSheet.id == stock.id, StockSheet.status == "RESERVED")
        .update({"status": "CONSUMED"})
    )
    if updated_stock == 0:
        db.rollback()
        raise HTTPException(status_code=409, detail="El stock no estaba en estado reservado")

    occupied = occupied_geometry_at(
        piece_polygon, reservation.rotation, reservation.x, reservation.y,
        machine_config.kerf_mm, machine_config.minimum_spacing_mm,
    )
    company = db.query(Company).filter(Company.id == member.company_id).first()
    remnant_candidates = compute_remnants(
        shape(stock.geometry), occupied, company.minimum_remnant_area_mm2,
        company.minimum_remnant_width_mm, company.minimum_remnant_height_mm,
    )

    _log_movement(
        db, member.company_id, stock.id, "CONSUMED", quotation_id=reservation.quotation_id,
        created_by_id=member.user_id, details={"reservation_id": reservation.id},
    )

    created_remnants: list[StockSheet] = []
    for candidate in remnant_candidates:
        code = _next_stock_code(db, member.company_id, "REMNANT")
        minx, miny, maxx, maxy = candidate.geometry.bounds
        remnant = StockSheet(
            company_id=member.company_id,
            material_id=stock.material_id,
            code=code,
            stock_type="REMNANT",
            status="AVAILABLE",
            original_width_mm=maxx - minx,
            original_height_mm=maxy - miny,
            original_area_mm2=candidate.area_mm2,
            remaining_area_mm2=candidate.area_mm2,
            geometry=mapping(candidate.geometry),
            source_sheet_id=stock.id,
            source_quotation_id=reservation.quotation_id,
            created_by_id=member.user_id,
        )
        db.add(remnant)
        db.flush()
        _log_movement(
            db, member.company_id, remnant.id, "REMNANT_CREATED", quotation_id=reservation.quotation_id,
            created_by_id=member.user_id, details={"source_sheet_id": stock.id},
        )
        created_remnants.append(remnant)

    db.commit()
    db.refresh(stock)

    return ConfirmCutResult(
        reservation_id=reservation.id,
        stock_sheet_id=stock.id,
        stock_code=stock.code,
        status=stock.status,
        remnants=[
            RemnantResult(stock_sheet_id=r.id, code=r.code, area_mm2=r.original_area_mm2) for r in created_remnants
        ],
    )


@router.get("/{stock_id}/movements", response_model=list[StockMovementRead])
def list_stock_movements(
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
    return (
        db.query(StockMovement)
        .filter(StockMovement.stock_sheet_id == stock_id, StockMovement.company_id == member.company_id)
        .order_by(StockMovement.id.asc())
        .all()
    )
