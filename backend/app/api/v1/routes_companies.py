import logging
import os

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.company import Company
from app.models.company_member import CompanyMember, CompanyRole
from app.models.user import User
from app.schemas.company import CompanyCreate, CompanyRead, CompanyUpdate, MyCompanyRead
from app.schemas.company_member import CompanyMemberCreate, CompanyMemberRead, CompanyMemberUpdate
from app.services.auth import hash_password
from app.services.auth_guard import get_current_user
from app.services.company_guard import get_current_company, require_owner

router = APIRouter(prefix="/companies", tags=["companies"])
logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)

settings = get_settings()

ALLOWED_LOGO_EXTS = {".png", ".jpg", ".jpeg", ".svg", ".webp"}


def _require_matching_company(company_id: int, member: CompanyMember) -> None:
    """Evita que el id de la URL y el de X-Company-Id (ya validado) diverjan."""
    if company_id != member.company_id:
        raise HTTPException(status_code=403, detail="No pertenecés a esta empresa")


@router.post("/", response_model=CompanyRead, status_code=201)
@limiter.limit("10/minute")
def create_company(
    request: Request,
    payload: CompanyCreate,
    db: Session = Depends(get_db),
    current_user: int = Depends(get_current_user),
):
    company = Company(**payload.dict())
    db.add(company)
    db.flush()
    member = CompanyMember(
        company_id=company.id,
        user_id=current_user,
        role=CompanyRole.OWNER.value,
    )
    db.add(member)
    db.commit()
    db.refresh(company)
    logger.info("Company created", extra={"company_id": company.id, "user": current_user})
    return company


@router.get("/me", response_model=list[MyCompanyRead])
def list_my_companies(
    db: Session = Depends(get_db),
    current_user: int = Depends(get_current_user),
):
    rows = (
        db.query(CompanyMember, Company)
        .join(Company, Company.id == CompanyMember.company_id)
        .filter(CompanyMember.user_id == current_user)
        .all()
    )
    return [
        MyCompanyRead(
            id=company.id,
            company_name=company.company_name,
            is_active=company.is_active,
            role=member.role,
            member_is_active=member.is_active,
        )
        for member, company in rows
    ]


@router.get("/{company_id}", response_model=CompanyRead)
def get_company(
    company_id: int,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
):
    _require_matching_company(company_id, member)
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.put("/{company_id}", response_model=CompanyRead)
def update_company(
    company_id: int,
    payload: CompanyUpdate,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(require_owner),
):
    _require_matching_company(company_id, member)
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    update_data = payload.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(company, key, value)
    db.commit()
    db.refresh(company)
    return company


@router.post("/{company_id}/logo", response_model=CompanyRead)
@limiter.limit("5/minute")
def upload_logo(
    request: Request,
    company_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(require_owner),
):
    _require_matching_company(company_id, member)
    _, ext = os.path.splitext(file.filename or "")
    if ext.lower() not in ALLOWED_LOGO_EXTS:
        raise HTTPException(status_code=400, detail="Formato no permitido. Usá PNG, JPG, SVG o WEBP.")

    content = file.file.read()
    if len(content) > settings.MAX_LOGO_SIZE:
        raise HTTPException(status_code=400, detail=f"Logo muy grande. Máximo {settings.MAX_LOGO_SIZE / 1024 / 1024:.0f}MB.")

    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    company.logo_data = content
    company.logo_filename = f"logo{ext.lower()}"
    db.commit()
    db.refresh(company)
    logger.info("Logo uploaded", extra={"company_id": company_id})
    return company


@router.get("/{company_id}/logo")
def get_logo(
    company_id: int,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
):
    _require_matching_company(company_id, member)
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company or not company.logo_data:
        raise HTTPException(status_code=404, detail="No hay logo configurado.")

    media_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".svg": "image/svg+xml",
        ".webp": "image/webp",
    }
    _, file_ext = os.path.splitext(company.logo_filename or "logo.png")
    media_type = media_types.get(file_ext.lower(), "image/png")
    return StreamingResponse(iter([company.logo_data]), media_type=media_type)


def _member_read(member: CompanyMember) -> CompanyMemberRead:
    return CompanyMemberRead(
        id=member.id,
        company_id=member.company_id,
        user_id=member.user_id,
        email=member.user.email,
        role=member.role,
        is_active=member.is_active,
        created_at=member.created_at,
    )


@router.get("/{company_id}/members", response_model=list[CompanyMemberRead])
def list_members(
    company_id: int,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
):
    _require_matching_company(company_id, member)
    members = db.query(CompanyMember).filter(CompanyMember.company_id == company_id).all()
    return [_member_read(m) for m in members]


@router.post("/{company_id}/members", response_model=CompanyMemberRead, status_code=201)
def create_member(
    company_id: int,
    payload: CompanyMemberCreate,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(require_owner),
):
    _require_matching_company(company_id, member)
    email_lower = payload.email.lower()
    user = db.query(User).filter(User.email == email_lower).first()
    if not user:
        user = User(email=email_lower, hashed_password=hash_password(payload.password))
        db.add(user)
        db.flush()

    existing = (
        db.query(CompanyMember)
        .filter(CompanyMember.company_id == company_id, CompanyMember.user_id == user.id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Ese usuario ya es miembro de la empresa")

    new_member = CompanyMember(
        company_id=company_id,
        user_id=user.id,
        role=payload.role.value,
    )
    db.add(new_member)
    db.commit()
    db.refresh(new_member)
    logger.info("Company member created", extra={"company_id": company_id, "user_id": user.id, "role": payload.role.value})
    return _member_read(new_member)


@router.patch("/{company_id}/members/{member_id}", response_model=CompanyMemberRead)
def update_member(
    company_id: int,
    member_id: int,
    payload: CompanyMemberUpdate,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(require_owner),
):
    _require_matching_company(company_id, member)
    target = (
        db.query(CompanyMember)
        .filter(CompanyMember.id == member_id, CompanyMember.company_id == company_id)
        .first()
    )
    if not target:
        raise HTTPException(status_code=404, detail="Member not found")

    will_deactivate = payload.is_active is False
    will_demote = payload.role is not None and payload.role != CompanyRole.OWNER
    if target.role == CompanyRole.OWNER.value and target.is_active and (will_deactivate or will_demote):
        other_owners = (
            db.query(CompanyMember)
            .filter(
                CompanyMember.company_id == company_id,
                CompanyMember.role == CompanyRole.OWNER.value,
                CompanyMember.is_active.is_(True),
                CompanyMember.id != target.id,
            )
            .count()
        )
        if other_owners == 0:
            raise HTTPException(status_code=400, detail="La empresa debe tener al menos un OWNER activo")

    if payload.role is not None:
        target.role = payload.role.value
    if payload.is_active is not None:
        target.is_active = payload.is_active
    db.commit()
    db.refresh(target)
    return _member_read(target)
