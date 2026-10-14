from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.core.config import get_settings


def business_now() -> datetime:
    """Hora actual en la zona horaria del negocio (no la del servidor)."""
    return datetime.now(ZoneInfo(get_settings().BUSINESS_TIMEZONE))


def business_today() -> date:
    """Fecha de hoy según el negocio. Única fuente de "hoy" para reglas de fechas."""
    return business_now().date()
