from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.auth_guard import get_current_user
from app.models.piece import Piece
from app.services.dxf_analysis import get_bounding_box
from app.services.nesting import NestingResult, calculate_nesting

router = APIRouter(prefix="/nesting", tags=["nesting"])


class NestingRequest(BaseModel):
    piece_id: int
    sheet_width_mm: float = Field(..., gt=0)
    sheet_height_mm: float = Field(..., gt=0)
    margin_mm: float = Field(5.0, ge=0)


@router.post("/calculate", response_model=NestingResult)
def calculate(
    payload: NestingRequest,
    db: Session = Depends(get_db),
    current_user: int = Depends(get_current_user),
):
    piece = db.query(Piece).filter(Piece.id == payload.piece_id, Piece.active.is_(True)).first()
    if not piece:
        raise HTTPException(status_code=404, detail="Piece not found")
    if not piece.dxf_path:
        raise HTTPException(status_code=400, detail="La pieza no tiene DXF cargado.")

    piece_w, piece_h = get_bounding_box(piece.dxf_path)
    if piece_w == 0 or piece_h == 0:
        raise HTTPException(status_code=400, detail="No se pudo calcular el bounding box del DXF.")

    return calculate_nesting(
        piece_w=piece_w,
        piece_h=piece_h,
        sheet_w=payload.sheet_width_mm,
        sheet_h=payload.sheet_height_mm,
        margin_mm=payload.margin_mm,
    )
