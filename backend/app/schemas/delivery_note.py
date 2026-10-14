from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.validators import clean_optional_text, clean_required_text

_MAX_LINE_QUANTITY = 1_000_000


class DeliveryNoteLineIn(BaseModel):
    quotation_item_id: int
    quantity: int = Field(gt=0, le=_MAX_LINE_QUANTITY)


def _no_duplicate_items(lines: list[DeliveryNoteLineIn]) -> list[DeliveryNoteLineIn]:
    ids = [line.quotation_item_id for line in lines]
    if len(ids) != len(set(ids)):
        raise ValueError("Un ítem de la cotización no puede repetirse en el mismo remito")
    return lines


class DeliveryNoteCreate(BaseModel):
    quotation_id: int
    notes: Optional[str] = None
    items: list[DeliveryNoteLineIn] = Field(min_length=1)

    @field_validator("notes")
    @classmethod
    def _validate_notes(cls, v: Optional[str]) -> Optional[str]:
        return clean_optional_text(v, max_length=1000)

    @field_validator("items")
    @classmethod
    def _validate_items(cls, v: list[DeliveryNoteLineIn]) -> list[DeliveryNoteLineIn]:
        return _no_duplicate_items(v)


class DeliveryNoteUpdate(BaseModel):
    """Solo borradores. Los campos omitidos no se tocan; `notes: null` borra las observaciones."""

    notes: Optional[str] = None
    items: Optional[list[DeliveryNoteLineIn]] = Field(default=None, min_length=1)

    @field_validator("notes")
    @classmethod
    def _validate_notes(cls, v: Optional[str]) -> Optional[str]:
        return clean_optional_text(v, max_length=1000)

    @field_validator("items")
    @classmethod
    def _validate_items(cls, v: Optional[list[DeliveryNoteLineIn]]) -> Optional[list[DeliveryNoteLineIn]]:
        return None if v is None else _no_duplicate_items(v)


class DeliveryNoteVoid(BaseModel):
    reason: str

    @field_validator("reason")
    @classmethod
    def _validate_reason(cls, v: str) -> str:
        cleaned = clean_required_text(v, field_name="El motivo", min_length=3, max_length=500)
        return cleaned


# ── lectura: sin validators a propósito (nunca debe rechazar una fila ya guardada) ──


class DeliveryNoteItemRead(BaseModel):
    id: int
    quotation_item_id: int
    piece_id: Optional[int] = None
    piece_name: str
    piece_description: Optional[str] = None
    quantity: int
    unit: str

    model_config = {"from_attributes": True}


class DeliveryNoteRead(BaseModel):
    id: int
    company_id: int
    quotation_id: int
    client_id: int
    number: Optional[str] = None
    status: str
    issue_date: Optional[datetime] = None
    notes: Optional[str] = None
    quotation_number: str
    client_name: str
    client_tax_id: Optional[str] = None
    client_address: Optional[str] = None
    issued_at: Optional[datetime] = None
    issued_by_id: Optional[int] = None
    voided_at: Optional[datetime] = None
    voided_by_id: Optional[int] = None
    void_reason: Optional[str] = None
    created_by_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    total_units: int = 0
    # Solo se calcula para borradores: ¿el corte de todas sus líneas está confirmado (condición para emitir)?
    cut_confirmed: Optional[bool] = None
    cut_pending_pieces: list[str] = []
    items: list[DeliveryNoteItemRead] = []

    model_config = {"from_attributes": True}


class DeliveryNoteSummary(BaseModel):
    id: int
    quotation_id: int
    number: Optional[str] = None
    status: str
    issue_date: Optional[datetime] = None
    quotation_number: str
    client_name: str
    total_units: int = 0
    created_at: datetime


class DeliveryStatusLine(BaseModel):
    quotation_item_id: int
    piece_id: Optional[int] = None
    piece_name: str
    piece_description: Optional[str] = None
    unit: str
    quoted: int
    delivered: int
    pending: int
    cut_confirmed: bool = False


class DeliveryStatusRead(BaseModel):
    quotation_id: int
    quotation_number: str
    quotation_status: str
    client_name: str
    cut_confirmed: bool = False
    eligible: bool
    ineligible_reason: Optional[str] = None
    state: str
    total_quoted: int
    total_delivered: int
    total_pending: int
    items: list[DeliveryStatusLine]
