from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class QuotationItemBase(BaseModel):
    quotation_id: int
    piece_id: int
    material_id: int
    quantity: int = Field(gt=0)
    margin_percent: float = Field(default=0.0, ge=0)


class QuotationItemCreate(QuotationItemBase):
    pass


class QuotationItemUpdate(BaseModel):
    quantity: Optional[int] = Field(default=None, gt=0)
    margin_percent: Optional[float] = Field(default=None, ge=0)


class QuotationItemRead(QuotationItemBase):
    id: int
    cost_material_ars: float
    cost_machine_ars: float
    cost_labor_ars: float
    unit_price_ars: float
    total_price_ars: float
    created_at: datetime
    updated_at: datetime
    created_by_id: Optional[int] = None

    model_config = {"from_attributes": True}
