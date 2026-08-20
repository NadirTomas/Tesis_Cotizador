from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr

from app.models.company_member import CompanyRole


class CompanyMemberCreate(BaseModel):
    email: EmailStr
    password: str
    role: CompanyRole = CompanyRole.EMPLOYEE


class CompanyMemberUpdate(BaseModel):
    role: Optional[CompanyRole] = None
    is_active: Optional[bool] = None


class CompanyMemberRead(BaseModel):
    id: int
    company_id: int
    user_id: int
    email: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
