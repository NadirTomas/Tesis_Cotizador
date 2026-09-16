from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator

from app.schemas.validators import clean_optional_text, clean_required_text

_MAX_THICKNESS_MM = 1000.0
_MAX_SHEET_DIM_MM = 20000.0
_MAX_SHEET_COST_ARS = 1_000_000_000.0


def _validate_positive(value: Optional[float], *, field_name: str, max_value: float) -> Optional[float]:
    if value is None:
        return None
    if value <= 0:
        raise ValueError(f"{field_name} debe ser mayor a 0")
    if value > max_value:
        raise ValueError(f"{field_name} no puede superar {max_value}")
    return value


class MaterialCreate(BaseModel):
    """Estos límites (y los de MaterialUpdate) rigen SOLO al escribir.
    MaterialRead es un modelo separado y deliberadamente sin validadores:
    un material ya guardado en producción con valores fuera de este rango
    (cargado antes de que existiera esta regla) debe poder seguir
    leyéndose tal cual, nunca romper un GET. No compartir estos
    validators con MaterialRead vía herencia — eso fue justo el bug que
    tiró 500 en /materials para una empresa real (ver incidente
    2026-09-16)."""

    name: str
    material_type: str
    alloy: Optional[str] = None
    thickness_mm: float
    sheet_width_mm: float
    sheet_height_mm: float
    sheet_cost_ars: float

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        return clean_required_text(v, field_name="El nombre", min_length=1, max_length=200)

    @field_validator("material_type")
    @classmethod
    def _validate_material_type(cls, v: str) -> str:
        return clean_required_text(v, field_name="El tipo de material", min_length=1, max_length=100)

    @field_validator("alloy")
    @classmethod
    def _validate_alloy(cls, v: Optional[str]) -> Optional[str]:
        return clean_optional_text(v, max_length=100)

    @field_validator("thickness_mm")
    @classmethod
    def _validate_thickness(cls, v: float) -> float:
        return _validate_positive(v, field_name="El espesor", max_value=_MAX_THICKNESS_MM)

    @field_validator("sheet_width_mm")
    @classmethod
    def _validate_width(cls, v: float) -> float:
        return _validate_positive(v, field_name="El ancho de chapa", max_value=_MAX_SHEET_DIM_MM)

    @field_validator("sheet_height_mm")
    @classmethod
    def _validate_height(cls, v: float) -> float:
        return _validate_positive(v, field_name="El alto de chapa", max_value=_MAX_SHEET_DIM_MM)

    @field_validator("sheet_cost_ars")
    @classmethod
    def _validate_cost(cls, v: float) -> float:
        # 0 es un valor real y ya usado en tests/negocio (material provisto
        # sin costo de chapa para aislar el costo de máquina) — no puede
        # ser negativo, pero sí puede ser 0.
        if v is None:
            return None
        if v < 0:
            raise ValueError("El costo de chapa no puede ser negativo")
        if v > _MAX_SHEET_COST_ARS:
            raise ValueError(f"El costo de chapa no puede superar {_MAX_SHEET_COST_ARS}")
        return v


class MaterialUpdate(BaseModel):
    name: Optional[str] = None
    material_type: Optional[str] = None
    alloy: Optional[str] = None
    thickness_mm: Optional[float] = None
    sheet_width_mm: Optional[float] = None
    sheet_height_mm: Optional[float] = None
    sheet_cost_ars: Optional[float] = None

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return clean_required_text(v, field_name="El nombre", min_length=1, max_length=200)

    @field_validator("material_type")
    @classmethod
    def _validate_material_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return clean_required_text(v, field_name="El tipo de material", min_length=1, max_length=100)

    @field_validator("alloy")
    @classmethod
    def _validate_alloy(cls, v: Optional[str]) -> Optional[str]:
        return clean_optional_text(v, max_length=100)

    @field_validator("thickness_mm")
    @classmethod
    def _validate_thickness(cls, v: Optional[float]) -> Optional[float]:
        return _validate_positive(v, field_name="El espesor", max_value=_MAX_THICKNESS_MM)

    @field_validator("sheet_width_mm")
    @classmethod
    def _validate_width(cls, v: Optional[float]) -> Optional[float]:
        return _validate_positive(v, field_name="El ancho de chapa", max_value=_MAX_SHEET_DIM_MM)

    @field_validator("sheet_height_mm")
    @classmethod
    def _validate_height(cls, v: Optional[float]) -> Optional[float]:
        return _validate_positive(v, field_name="El alto de chapa", max_value=_MAX_SHEET_DIM_MM)

    @field_validator("sheet_cost_ars")
    @classmethod
    def _validate_cost(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return None
        if v < 0:
            raise ValueError("El costo de chapa no puede ser negativo")
        if v > _MAX_SHEET_COST_ARS:
            raise ValueError(f"El costo de chapa no puede superar {_MAX_SHEET_COST_ARS}")
        return v


class MaterialRead(BaseModel):
    """Sin validadores a propósito: es el modelo de LECTURA. Nunca debe
    rechazar una fila ya guardada, sin importar qué tan fuera de rango
    esté un valor cargado antes de que existieran los límites de arriba."""

    id: int
    name: str
    material_type: Optional[str] = None
    alloy: Optional[str] = None
    thickness_mm: float
    sheet_width_mm: float
    sheet_height_mm: float
    sheet_cost_ars: float
    company_id: int
    active: bool
    created_at: datetime
    updated_at: datetime
    created_by_id: Optional[int] = None

    model_config = {"from_attributes": True}
