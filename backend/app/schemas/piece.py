from datetime import datetime
from typing import Optional

from pydantic import BaseModel


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

    @classmethod
    def from_orm(cls, obj):
        data = obj.__dict__.copy()
        data["has_dxf"] = bool(obj.dxf_data)
        data["has_preview"] = bool(obj.preview_data)
        return cls(**data)
