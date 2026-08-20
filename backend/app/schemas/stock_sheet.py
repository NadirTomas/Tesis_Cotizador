from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

STOCK_TYPES = ("FULL_SHEET", "REMNANT")
STOCK_STATUSES = ("AVAILABLE", "RESERVED", "CONSUMED", "DISCARDED")


class StockSheetCreate(BaseModel):
    material_id: int
    stock_type: Literal["FULL_SHEET", "REMNANT"]
    width_mm: Optional[float] = Field(default=None, gt=0)
    height_mm: Optional[float] = Field(default=None, gt=0)
    geometry: Optional[dict] = None
    source_sheet_id: Optional[int] = None
    source_quotation_id: Optional[int] = None

    @model_validator(mode="after")
    def _require_dimensions_or_geometry(self):
        has_dims = self.width_mm is not None and self.height_mm is not None
        if not has_dims and self.geometry is None:
            raise ValueError("Debe enviarse 'geometry' o bien 'width_mm' + 'height_mm'")
        return self


class StockSheetUpdate(BaseModel):
    material_id: Optional[int] = None


class StockSheetRead(BaseModel):
    id: int
    company_id: int
    material_id: int
    code: str
    stock_type: str
    status: str
    original_width_mm: Optional[float] = None
    original_height_mm: Optional[float] = None
    original_area_mm2: float
    remaining_area_mm2: float
    geometry: dict
    source_sheet_id: Optional[int] = None
    source_quotation_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    created_by_id: Optional[int] = None

    model_config = {"from_attributes": True}
