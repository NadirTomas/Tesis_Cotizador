import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.company_member import CompanyMember
from app.models.piece import Piece
from app.services.company_guard import get_current_company
from app.services.dxf_analysis import get_bounding_box
from app.services.nesting import NestingItemInput, NestingResult, pack_pieces

router = APIRouter(prefix="/nesting", tags=["nesting"])


class NestingItemRequest(BaseModel):
    piece_id: int
    quantity: int = Field(..., gt=0)


class NestingRequest(BaseModel):
    items: list[NestingItemRequest] = Field(..., min_length=1)
    sheet_width_mm: float = Field(..., gt=0)
    sheet_height_mm: float = Field(..., gt=0)
    margin_mm: float = Field(5.0, ge=0)
    allow_rotation: bool = True


def _get_piece_bbox(piece: Piece) -> tuple[float, float]:
    with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as tmp:
        tmp.write(piece.dxf_data)
        tmp_path = tmp.name
    try:
        return get_bounding_box(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@router.post("/calculate", response_model=NestingResult)
def calculate(
    payload: NestingRequest,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
):
    piece_ids = [item.piece_id for item in payload.items]
    pieces = (
        db.query(Piece)
        .filter(Piece.id.in_(piece_ids), Piece.company_id == member.company_id, Piece.active.is_(True))
        .all()
    )
    pieces_by_id = {p.id: p for p in pieces}

    for item in payload.items:
        piece = pieces_by_id.get(item.piece_id)
        if not piece:
            raise HTTPException(status_code=404, detail=f"Pieza {item.piece_id} no encontrada")
        if not piece.dxf_data:
            raise HTTPException(status_code=400, detail=f"La pieza '{piece.name}' no tiene DXF cargado.")

    material_ids = {pieces_by_id[item.piece_id].material_id for item in payload.items}
    if len(material_ids) > 1:
        raise HTTPException(
            status_code=400, detail="Todas las piezas de una misma corrida de nesting deben ser del mismo material."
        )

    nesting_items: list[NestingItemInput] = []
    for item in payload.items:
        piece = pieces_by_id[item.piece_id]
        width, height = _get_piece_bbox(piece)
        if width == 0 or height == 0:
            raise HTTPException(status_code=400, detail=f"No se pudo calcular el bounding box de '{piece.name}'.")
        nesting_items.append(
            NestingItemInput(piece_id=piece.id, label=piece.name, width_mm=width, height_mm=height, quantity=item.quantity)
        )

    return pack_pieces(
        items=nesting_items,
        sheet_w=payload.sheet_width_mm,
        sheet_h=payload.sheet_height_mm,
        margin_mm=payload.margin_mm,
        allow_rotation=payload.allow_rotation,
    )
