"""Pydantic schemas for API input/output."""

from app.schemas.client import ClientCreate, ClientRead, ClientUpdate
from app.schemas.machine_config import (
    MachineConfigCreate,
    MachineConfigRead,
    MachineConfigUpdate,
)
from app.schemas.material import MaterialCreate, MaterialRead, MaterialUpdate
from app.schemas.piece import PieceCreate, PieceRead, PieceUpdate
from app.schemas.quotation import QuotationCreate, QuotationRead
from app.schemas.quotation_item import QuotationItemCreate, QuotationItemRead

__all__ = [
    "ClientCreate",
    "ClientRead",
    "ClientUpdate",
    "MachineConfigCreate",
    "MachineConfigRead",
    "MachineConfigUpdate",
    "MaterialCreate",
    "MaterialRead",
    "MaterialUpdate",
    "PieceCreate",
    "PieceRead",
    "PieceUpdate",
    "QuotationCreate",
    "QuotationRead",
    "QuotationItemCreate",
    "QuotationItemRead",
]
