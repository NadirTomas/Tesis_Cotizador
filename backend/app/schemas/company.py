from typing import Optional
from pydantic import BaseModel


class CompanyConfigUpdate(BaseModel):
    company_name: Optional[str] = None
    legal_name: Optional[str] = None
    cuit: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class CompanyConfigRead(BaseModel):
    id: int
    company_name: str
    legal_name: Optional[str] = None
    cuit: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    has_logo: bool = False  # True si hay logo_data

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm(cls, obj):
        data = obj.__dict__.copy()
        data["has_logo"] = bool(obj.logo_data)
        return cls(**data)
