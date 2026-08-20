from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class MachineConfigBase(BaseModel):
    material_id: int
    cut_speed_mm_min: float
    machine_cost_per_hour_ars: float
    setup_time_min: float
    labor_percent: float = 30.0


class MachineConfigCreate(MachineConfigBase):
    pass


class MachineConfigUpdate(BaseModel):
    cut_speed_mm_min: Optional[float] = None
    machine_cost_per_hour_ars: Optional[float] = None
    setup_time_min: Optional[float] = None
    labor_percent: Optional[float] = None
    active: Optional[bool] = None


class MachineConfigRead(MachineConfigBase):
    id: int
    company_id: int
    active: bool
    created_at: datetime
    updated_at: datetime
    created_by_id: Optional[int] = None

    model_config = {"from_attributes": True}
