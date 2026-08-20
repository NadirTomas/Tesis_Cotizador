from datetime import datetime
from typing import Optional

from pydantic import BaseModel, model_validator


class PieceBase(BaseModel):
    name: str
    description: Optional[str] = None
    material_id: Optional[int] = None


class PieceCreate(PieceBase):
    pass


class PieceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    material_id: Optional[int] = None
    active: Optional[bool] = None


class PieceRead(PieceBase):
    id: int
    company_id: int
    dxf_filename: Optional[str] = None
    has_dxf: bool = False
    has_preview: bool = False
    length_cut_mm: Optional[float] = None
    area_mm2: Optional[float] = None
    active: bool
    created_at: datetime
    updated_at: datetime
    created_by_id: Optional[int] = None

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def _compute_dxf_flags(cls, obj):
        if isinstance(obj, dict):
            return obj
        data = {k: v for k, v in vars(obj).items() if not k.startswith("_")}
        data["has_dxf"] = bool(getattr(obj, "dxf_data", None))
        data["has_preview"] = bool(getattr(obj, "preview_data", None))
        return data
