from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class QuotationBase(BaseModel):
    number: str
    client_id: int
    issue_date: datetime
    due_date: Optional[datetime] = None
    currency: str = "ARS"
    exchange_rate: Optional[float] = None
    notes: Optional[str] = None
    status: str = "draft"


class QuotationCreate(QuotationBase):
    pass


class QuotationRead(QuotationBase):
    id: int
    total_ars: float
    total_usd: float
    has_pdf: bool = False
    created_at: datetime
    updated_at: datetime
    created_by_id: Optional[int] = None

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm(cls, obj):
        data = obj.__dict__.copy()
        data["has_pdf"] = bool(obj.pdf_data)
        return cls(**data)
