import logging
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from app.services.company_guard import get_current_company
from fastapi.responses import StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.company_member import CompanyMember
from app.models.piece import Piece
from app.services.dxf_analysis import analyze_dxf
from app.services.dxf_preview import generate_dxf_preview
from app.services.lookups import get_active_material
from app.schemas.piece import PieceCreate, PieceRead, PieceUpdate
from app.core.config import get_settings


router = APIRouter(prefix="/pieces", tags=["pieces"])
logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)

settings = get_settings()


@router.post("/", response_model=PieceRead)
def create_piece(
    payload: PieceCreate,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
):
    if payload.material_id is not None:
        material = get_active_material(db, payload.material_id, member.company_id)
        if not material:
            raise HTTPException(status_code=404, detail="Material not found")
    piece = Piece(**payload.dict())
    piece.company_id = member.company_id
    piece.created_by_id = member.user_id
    db.add(piece)
    db.commit()
    db.refresh(piece)
    return piece


@router.get("/", response_model=list[PieceRead])
def list_pieces(
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
):
    return (
        db.query(Piece)
        .filter(Piece.company_id == member.company_id, Piece.active.is_(True))
        .all()
    )


@router.get("/{piece_id}", response_model=PieceRead)
def get_piece(
    piece_id: int,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
):
    piece = (
        db.query(Piece)
        .filter(
            Piece.id == piece_id,
            Piece.company_id == member.company_id,
            Piece.active.is_(True),
        )
        .first()
    )
    if not piece:
        raise HTTPException(status_code=404, detail="Piece not found")
    return piece


@router.put("/{piece_id}", response_model=PieceRead)
def update_piece(
    piece_id: int,
    payload: PieceUpdate,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
):
    piece = (
        db.query(Piece)
        .filter(Piece.id == piece_id, Piece.company_id == member.company_id)
        .first()
    )
    if not piece:
        raise HTTPException(status_code=404, detail="Piece not found")
    if payload.material_id is not None:
        material = get_active_material(db, payload.material_id, member.company_id)
        if not material:
            raise HTTPException(status_code=404, detail="Material not found")
    update_data = payload.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(piece, key, value)
    db.commit()
    db.refresh(piece)
    return piece


@router.delete("/{piece_id}", response_model=PieceRead)
def deactivate_piece(
    piece_id: int,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
):
    piece = (
        db.query(Piece)
        .filter(Piece.id == piece_id, Piece.company_id == member.company_id)
        .first()
    )
    if not piece:
        raise HTTPException(status_code=404, detail="Piece not found")
    piece.active = False
    db.commit()
    db.refresh(piece)
    return piece


# Paso 7: Upload y análisis de DXF para piezas
@router.post("/{piece_id}/upload-dxf", response_model=PieceRead)
@limiter.limit("5/minute")
def upload_dxf(
    request: Request,
    piece_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
):
    piece = (
        db.query(Piece)
        .filter(
            Piece.id == piece_id,
            Piece.company_id == member.company_id,
            Piece.active.is_(True),
        )
        .first()
    )
    if not piece:
        logger.warning("DXF upload failed: piece not found", extra={"piece_id": piece_id, "user": member.user_id})
        raise HTTPException(status_code=404, detail="Piece not found")

    _, ext = os.path.splitext(file.filename or "")
    if ext.lower() != ".dxf":
        logger.warning("DXF upload failed: invalid file format", extra={"piece_id": piece_id, "filename": file.filename, "user": member.user_id})
        raise HTTPException(status_code=400, detail="Only .dxf files are allowed")

    # Leer contenido del archivo
    dxf_content = file.file.read()
    if len(dxf_content) > settings.MAX_DXF_SIZE:
        logger.warning("DXF upload failed: file too large", extra={"piece_id": piece_id, "file_size_mb": len(dxf_content) / 1024 / 1024, "user": member.user_id})
        raise HTTPException(status_code=400, detail=f"DXF file too large. Maximum {settings.MAX_DXF_SIZE / 1024 / 1024:.0f}MB.")

    # Analizar DXF guardando en temp file
    try:
        with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as tmp:
            tmp.write(dxf_content)
            tmp_path = tmp.name
        length_cut_mm, area_mm2 = analyze_dxf(tmp_path)
    except Exception:
        logger.exception("DXF analysis failed", extra={"piece_id": piece_id, "filename": file.filename, "user": member.user_id})
        raise HTTPException(status_code=400, detail="No se pudo leer el archivo DXF. Verificá que sea un DXF válido.")
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    piece.dxf_data = dxf_content
    piece.dxf_filename = file.filename or f"piece_{piece_id}.dxf"
    piece.length_cut_mm = length_cut_mm
    piece.area_mm2 = area_mm2

    # Generar preview
    try:
        with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as tmp:
            tmp.write(dxf_content)
            tmp_path = tmp.name
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_png:
            png_path = tmp_png.name
        generate_dxf_preview(tmp_path, png_path)
        preview_data = Path(png_path).read_bytes()
        piece.preview_data = preview_data
        Path(png_path).unlink(missing_ok=True)
    except Exception:
        piece.preview_data = None  # preview no es bloqueante
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    db.commit()
    db.refresh(piece)
    logger.info("DXF uploaded successfully", extra={"piece_id": piece_id, "dxf_filename": file.filename, "file_size_kb": len(dxf_content) / 1024, "length_cut_mm": length_cut_mm, "area_mm2": area_mm2, "user": member.user_id})
    return piece


@router.get("/{piece_id}/preview")
def get_piece_preview(
    piece_id: int,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
):
    piece = (
        db.query(Piece)
        .filter(
            Piece.id == piece_id,
            Piece.company_id == member.company_id,
            Piece.active.is_(True),
        )
        .first()
    )
    if not piece or not piece.preview_data:
        raise HTTPException(status_code=404, detail="Preview not found")
    return StreamingResponse(iter([piece.preview_data]), media_type="image/png")
