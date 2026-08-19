from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ClientBase(BaseModel):
    name: str
    cuit_cuil: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None


class ClientCreate(ClientBase):
    pass


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    cuit_cuil: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None


class ClientRead(ClientBase):
    id: int
    active: bool
    created_at: datetime
    updated_at: datetime
    created_by_id: Optional[int] = None

    model_config = {"from_attributes": True}
