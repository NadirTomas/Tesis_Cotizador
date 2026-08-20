from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ReserveStockRequest(BaseModel):
    piece_id: int
    material_id: int
    quotation_id: int
    quotation_item_id: Optional[int] = None


class StockReservationRead(BaseModel):
    id: int
    stock_sheet_id: int
    piece_id: int
    quotation_id: int
    quotation_item_id: Optional[int] = None
    rotation: int
    x: float
    y: float
    status: str
    created_by_id: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RemnantResult(BaseModel):
    stock_sheet_id: int
    code: str
    area_mm2: float


class ConfirmCutResult(BaseModel):
    reservation_id: int
    stock_sheet_id: int
    stock_code: str
    status: str
    remnants: list[RemnantResult]


class StockMovementRead(BaseModel):
    id: int
    stock_sheet_id: int
    movement_type: str
    quotation_id: Optional[int] = None
    created_by_id: Optional[int] = None
    created_at: datetime
    details: Optional[dict] = None

    model_config = {"from_attributes": True}
