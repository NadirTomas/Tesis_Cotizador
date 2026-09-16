from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator

from app.schemas.validators import clean_optional_text, clean_required_text, validate_cuit, validate_phone


class ClientBase(BaseModel):
    """Solo para escritura (ClientCreate la hereda). ClientRead es un
    modelo aparte y deliberadamente sin estos validators: un cliente ya
    guardado en producción con un CUIT/email/nombre que no cumple estas
    reglas (cargado antes de que existieran) debe poder seguir
    leyéndose tal cual — nunca romper un GET. Ver el incidente de
    material.py del 2026-09-16: el mismo error de heredar validators de
    escritura en el modelo de lectura tiró 500 en /materials."""

    name: str
    cuit_cuil: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        return clean_required_text(v, field_name="El nombre", min_length=2, max_length=200)

    @field_validator("cuit_cuil")
    @classmethod
    def _validate_cuit(cls, v: Optional[str]) -> Optional[str]:
        return validate_cuit(v)

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, v: Optional[str]) -> Optional[str]:
        return validate_phone(v)

    @field_validator("email", mode="before")
    @classmethod
    def _blank_email_to_none(cls, v):
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator("address")
    @classmethod
    def _validate_address(cls, v: Optional[str]) -> Optional[str]:
        return clean_optional_text(v, max_length=300)

    @field_validator("notes")
    @classmethod
    def _validate_notes(cls, v: Optional[str]) -> Optional[str]:
        return clean_optional_text(v, max_length=1000)


class ClientCreate(ClientBase):
    pass


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    cuit_cuil: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return clean_required_text(v, field_name="El nombre", min_length=2, max_length=200)

    @field_validator("cuit_cuil")
    @classmethod
    def _validate_cuit(cls, v: Optional[str]) -> Optional[str]:
        return validate_cuit(v)

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, v: Optional[str]) -> Optional[str]:
        return validate_phone(v)

    @field_validator("address")
    @classmethod
    def _validate_address(cls, v: Optional[str]) -> Optional[str]:
        return clean_optional_text(v, max_length=300)

    @field_validator("notes")
    @classmethod
    def _validate_notes(cls, v: Optional[str]) -> Optional[str]:
        return clean_optional_text(v, max_length=1000)

    @field_validator("email", mode="before")
    @classmethod
    def _blank_email_to_none(cls, v):
        if isinstance(v, str) and not v.strip():
            return None
        return v


class ClientRead(BaseModel):
    """Sin validators a propósito: es el modelo de LECTURA, nunca debe
    rechazar una fila ya guardada por no cumplir una regla agregada
    después de que ese dato ya existía."""

    id: int
    name: str
    cuit_cuil: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    company_id: int
    active: bool
    created_at: datetime
    updated_at: datetime
    created_by_id: Optional[int] = None

    model_config = {"from_attributes": True}
