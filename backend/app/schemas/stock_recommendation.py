from pydantic import BaseModel


class StockRecommendationRequest(BaseModel):
    piece_id: int
    material_id: int


class StockRecommendation(BaseModel):
    stock_sheet_id: int
    stock_code: str
    stock_type: str
    rotation: int
    x: float
    y: float
    piece_area_mm2: float
    stock_remaining_area_mm2: float
    utilization_percent: float
    score: float
    reason: str
