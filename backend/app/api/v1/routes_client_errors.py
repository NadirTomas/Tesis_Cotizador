import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

router = APIRouter(prefix="/client-errors", tags=["client-errors"])
logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)


class ClientErrorReport(BaseModel):
    message: str = Field(..., max_length=2000)
    stack: str | None = Field(default=None, max_length=8000)
    url: str | None = Field(default=None, max_length=2000)


@router.post("", status_code=204)
@limiter.limit("20/minute")
def report_client_error(request: Request, payload: ClientErrorReport):
    logger.error(
        "Unhandled frontend error",
        extra={"source": "frontend", "url": payload.url, "stack": payload.stack},
    )
    return None
