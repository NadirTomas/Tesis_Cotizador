"""Fechas relativas al "hoy" del negocio para tests que crean cotizaciones.

La validación de emisión depende del reloj, así que los tests no pueden usar
fechas fijas (envejecen). Por defecto se usa MAÑANA: es válida siempre y no
queda expuesta a que el día cambie entre que el test arma la fecha y el backend
la valida.
"""

from datetime import date, timedelta

from app.core.clock import business_today


def business_date(days: int = 1) -> date:
    return business_today() + timedelta(days=days)


def issue_iso(days: int = 1) -> str:
    return f"{business_date(days).isoformat()}T00:00:00"
