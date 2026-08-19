import logging
import os

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.auth_guard import get_current_user
from app.models.company import CompanyConfig
from app.schemas.company import CompanyConfigRead, CompanyConfigUpdate

router = APIRouter(prefix="/company", tags=["company"])
logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)

from app.core.config import get_settings

settings = get_settings()

DEFAULT_NAME = "CotizaLaser"
ALLOWED_LOGO_EXTS = {".png", ".jpg", ".jpeg", ".svg", ".webp"}


def _get_or_create(db: Session) -> CompanyConfig:
    config = db.query(CompanyConfig).first()
    if not config:
        config = CompanyConfig(company_name=DEFAULT_NAME)
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


@router.get("/", response_model=CompanyConfigRead)
def get_company(db: Session = Depends(get_db)):
    config = _get_or_create(db)
    result = CompanyConfigRead.from_orm(config)
    return result


@router.put("/", response_model=CompanyConfigRead)
def update_company(payload: CompanyConfigUpdate, db: Session = Depends(get_db)):
    config = _get_or_create(db)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(config, key, value)
    db.commit()
    db.refresh(config)
    result = CompanyConfigRead.from_orm(config)
    return result


@router.post("/logo", response_model=CompanyConfigRead)
@limiter.limit("5/minute")
def upload_logo(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: int = Depends(get_current_user),
):
    _, ext = os.path.splitext(file.filename or "")
    if ext.lower() not in ALLOWED_LOGO_EXTS:
        logger.warning("Logo upload failed: invalid format", extra={"filename": file.filename, "user": current_user})
        raise HTTPException(status_code=400, detail="Formato no permitido. Usá PNG, JPG, SVG o WEBP.")

    # Leer contenido
    content = file.file.read()
    if len(content) > settings.MAX_LOGO_SIZE:
        logger.warning("Logo upload failed: file too large", extra={"filename": file.filename, "file_size_mb": len(content) / 1024 / 1024, "user": current_user})
        raise HTTPException(status_code=400, detail=f"Logo muy grande. Máximo {settings.MAX_LOGO_SIZE / 1024 / 1024:.0f}MB.")

    config = _get_or_create(db)
    config.logo_data = content
    config.logo_filename = f"logo{ext.lower()}"
    db.commit()
    db.refresh(config)
    result = CompanyConfigRead.from_orm(config)
    logger.info("Logo uploaded successfully", extra={"filename": file.filename, "file_size_kb": len(content) / 1024, "user": current_user})
    return result


@router.get("/logo")
def get_logo(db: Session = Depends(get_db)):
    config = _get_or_create(db)
    if not config.logo_data:
        raise HTTPException(status_code=404, detail="No hay logo configurado.")

    # Determinar media type
    ext = config.logo_filename or "logo.png"
    media_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".svg": "image/svg+xml",
        ".webp": "image/webp",
    }
    _, file_ext = os.path.splitext(ext)
    media_type = media_types.get(file_ext.lower(), "image/png")

    return StreamingResponse(iter([config.logo_data]), media_type=media_type)
