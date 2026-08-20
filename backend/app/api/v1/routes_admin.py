import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, EmailStr
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.company import Company
from app.models.company_member import CompanyMember, CompanyRole
from app.models.user import User
from app.services.auth import hash_password

router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)

settings = get_settings()


class AdminCreateCompanyRequest(BaseModel):
    company_name: str
    owner_email: EmailStr
    owner_password: str


class AdminCreateCompanyResponse(BaseModel):
    company_id: int
    company_name: str
    owner_email: str
    owner_created: bool


def _require_admin_secret(x_admin_secret: str = Header(..., alias="X-Admin-Secret")) -> None:
    if not settings.ADMIN_SECRET or x_admin_secret != settings.ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="No autorizado")


@router.post("/companies", response_model=AdminCreateCompanyResponse, status_code=201)
@limiter.limit("5/minute")
def create_company_for_client(
    request: Request,
    payload: AdminCreateCompanyRequest,
    db: Session = Depends(get_db),
    _: None = Depends(_require_admin_secret),
):
    """
    Da de alta una empresa nueva junto con su primer usuario OWNER. Pensado
    para que solo el desarrollador la use (onboarding manual de clientes),
    no para registro público. Si el email ya existe como usuario, se lo
    vincula como OWNER en vez de crear una cuenta nueva.
    """
    company = Company(company_name=payload.company_name)
    db.add(company)
    db.flush()

    email_lower = payload.owner_email.lower()
    user = db.query(User).filter(User.email == email_lower).first()
    owner_created = user is None
    if user is None:
        user = User(email=email_lower, hashed_password=hash_password(payload.owner_password))
        db.add(user)
        db.flush()

    db.add(CompanyMember(company_id=company.id, user_id=user.id, role=CompanyRole.OWNER.value))
    db.commit()
    db.refresh(company)

    logger.info(
        "Company onboarded via admin endpoint",
        extra={"company_id": company.id, "owner_email": email_lower, "owner_created": owner_created},
    )
    return AdminCreateCompanyResponse(
        company_id=company.id,
        company_name=company.company_name,
        owner_email=email_lower,
        owner_created=owner_created,
    )
