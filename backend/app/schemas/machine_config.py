from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class MachineConfigBase(BaseModel):
    material_id: int
    cut_speed_mm_min: float = Field(gt=0)
    machine_cost_per_hour_ars: float = Field(gt=0)
    setup_time_min: float = Field(ge=0)
    labor_percent: float = Field(default=30.0, ge=0)
    kerf_mm: float = Field(default=0.0, ge=0)
    minimum_spacing_mm: float = Field(default=0.0, ge=0)


class MachineConfigCreate(MachineConfigBase):
    pass


class MachineConfigUpdate(BaseModel):
    cut_speed_mm_min: Optional[float] = Field(default=None, gt=0)
    machine_cost_per_hour_ars: Optional[float] = Field(default=None, gt=0)
    setup_time_min: Optional[float] = Field(default=None, ge=0)
    labor_percent: Optional[float] = Field(default=None, ge=0)
    kerf_mm: Optional[float] = Field(default=None, ge=0)
    minimum_spacing_mm: Optional[float] = Field(default=None, ge=0)
    active: Optional[bool] = None


class MachineConfigRead(MachineConfigBase):
    id: int
    company_id: int
    active: bool
    created_at: datetime
    updated_at: datetime
    created_by_id: Optional[int] = None

    model_config = {"from_attributes": True}
