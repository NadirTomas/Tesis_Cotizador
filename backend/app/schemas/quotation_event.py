from datetime import datetime

from pydantic import BaseModel


class QuotationEventRead(BaseModel):
    id: int
    event_type: str
    description: str
    created_by_id: int | None = None
    created_by_email: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
