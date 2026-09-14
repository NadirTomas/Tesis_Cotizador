from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class QuotationCreate(BaseModel):
    client_id: int
    issue_date: datetime
    due_date: Optional[datetime] = None
    currency: str = "ARS"
    exchange_rate: Optional[float] = None
    notes: Optional[str] = None


class QuotationRead(BaseModel):
    id: int
    number: str
    company_id: int
    client_id: int
    issue_date: datetime
    due_date: Optional[datetime] = None
    currency: str
    exchange_rate: Optional[float] = None
    notes: Optional[str] = None
    status: str
    total_ars: float
    total_usd: float
    created_at: datetime
    updated_at: datetime
    created_by_id: Optional[int] = None

    model_config = {"from_attributes": True}
