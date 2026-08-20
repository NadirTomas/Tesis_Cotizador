from datetime import datetime
from typing import Optional

from pydantic import BaseModel, model_validator


class CompanyCreate(BaseModel):
    company_name: str
    legal_name: Optional[str] = None
    cuit: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class CompanyUpdate(BaseModel):
    company_name: Optional[str] = None
    legal_name: Optional[str] = None
    cuit: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class CompanyRead(BaseModel):
    id: int
    company_name: str
    legal_name: Optional[str] = None
    cuit: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_active: bool
    has_logo: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def _compute_has_logo(cls, obj):
        if isinstance(obj, dict):
            return obj
        data = {k: v for k, v in vars(obj).items() if not k.startswith("_")}
        data["has_logo"] = bool(getattr(obj, "logo_data", None))
        return data


class MyCompanyRead(BaseModel):
    """Empresa + rol del usuario logueado dentro de ella (para el selector post-login)."""

    id: int
    company_name: str
    is_active: bool
    role: str
    member_is_active: bool
