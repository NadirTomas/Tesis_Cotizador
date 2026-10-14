from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator, model_validator

from app.core import clock

_MIN_QUOTATION_YEAR = 2000


class QuotationCreate(BaseModel):
    client_id: int
    issue_date: datetime
    due_date: Optional[datetime] = None
    currency: str = "ARS"
    exchange_rate: Optional[float] = None
    notes: Optional[str] = None

    @field_validator("issue_date", "due_date")
    @classmethod
    def _validate_year(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is not None and v.year < _MIN_QUOTATION_YEAR:
            raise ValueError(f"La fecha no puede tener un año anterior a {_MIN_QUOTATION_YEAR}")
        return v

    @field_validator("issue_date")
    @classmethod
    def _validate_issue_date_not_in_past(cls, v: datetime) -> datetime:
        # issue_date llega como fecha de calendario (el front manda "YYYY-MM-DD" sin hora);
        # se compara contra "hoy" en la zona del negocio, no la del servidor.
        if v.date() < clock.business_today():
            raise ValueError("La fecha de emisión no puede ser anterior a hoy")
        return v

    @field_validator("exchange_rate")
    @classmethod
    def _validate_exchange_rate(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v <= 0:
            raise ValueError("El tipo de cambio debe ser mayor a 0")
        return v

    @model_validator(mode="after")
    def _validate_due_date_after_issue_date(self):
        if self.due_date is not None and self.due_date < self.issue_date:
            raise ValueError("La fecha de vencimiento no puede ser anterior a la fecha de emisión")
        return self


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
