from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class MaterialBase(BaseModel):
    name: str
    thickness_mm: float
    sheet_width_mm: float
    sheet_height_mm: float
    sheet_cost_ars: float


class MaterialCreate(MaterialBase):
    material_type: str
    alloy: Optional[str] = None


class MaterialUpdate(BaseModel):
    name: Optional[str] = None
    material_type: Optional[str] = None
    alloy: Optional[str] = None
    thickness_mm: Optional[float] = None
    sheet_width_mm: Optional[float] = None
    sheet_height_mm: Optional[float] = None
    sheet_cost_ars: Optional[float] = None


class MaterialRead(MaterialBase):
    id: int
    company_id: int
    material_type: Optional[str] = None
    alloy: Optional[str] = None
    active: bool
    created_at: datetime
    updated_at: datetime
    created_by_id: Optional[int] = None

    model_config = {"from_attributes": True}
