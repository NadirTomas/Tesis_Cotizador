from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core import clock
from app.db.init_db import init_db
from app.db.session import engine
from app.main import app
from tests._dates import business_date, issue_iso

client = TestClient(app)


def _reset_db_file() -> None:
    engine.dispose()
    db_path = Path("cotizalaser.db")
    if db_path.exists():
        db_path.unlink()


def _setup():
    _reset_db_file()
    init_db()
    res = client.post("/auth/register", json={"email": "owner@test.com", "password": "Password1!"})
    token = res.json()["access_token"]
    res = client.post("/companies", json={"company_name": "Empresa Test"}, headers={"Authorization": f"Bearer {token}"})
    company_id = res.json()["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Company-Id": str(company_id)}
    res = client.post("/clients", json={"name": "Cliente"}, headers=headers)
    client_id = res.json()["id"]
    return headers, client_id


def _create(headers, client_id, issue, **extra):
    return client.post("/quotations", json={"client_id": client_id, "issue_date": issue, **extra}, headers=headers)


@pytest.fixture
def frozen_utc_now(monkeypatch):
    """Congela el instante actual SOLO para el test que lo pide. Se fija en UTC
    (como corre el servidor) y deja que clock.py haga la conversión a la zona
    del negocio, así se prueba la conversión real y no un mock de su resultado."""

    def _freeze(year, month, day, hour, minute, second=0):
        fixed = datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)

        class _FrozenDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return fixed.astimezone(tz) if tz else fixed

        monkeypatch.setattr(clock, "datetime", _FrozenDatetime)

    return _freeze


# ---------- año absurdo y orden emisión/vencimiento ----------


def test_quotation_rejects_issue_date_with_absurd_year():
    headers, client_id = _setup()
    assert _create(headers, client_id, "0001-05-01T00:00:00").status_code == 422


def test_quotation_rejects_due_date_with_absurd_year():
    """El bug reportado: un PDF mostrando 'Fecha de vencimiento: 01/05/1'."""
    headers, client_id = _setup()
    res = _create(headers, client_id, issue_iso(), due_date="0001-05-01T00:00:00")
    assert res.status_code == 422


def test_quotation_rejects_due_date_before_issue_date():
    headers, client_id = _setup()
    res = _create(headers, client_id, issue_iso(10), due_date=issue_iso(5))
    assert res.status_code == 422


def test_quotation_accepts_due_date_equal_to_issue_date():
    headers, client_id = _setup()
    assert _create(headers, client_id, issue_iso(), due_date=issue_iso()).status_code == 200


def test_quotation_accepts_due_date_after_issue_date():
    headers, client_id = _setup()
    assert _create(headers, client_id, issue_iso(), due_date=issue_iso(30)).status_code == 200


def test_quotation_without_due_date_still_works():
    headers, client_id = _setup()
    res = _create(headers, client_id, issue_iso())
    assert res.status_code == 200
    assert res.json()["due_date"] is None


# ---------- emisión: pasado / presente / futuro (reloj real) ----------


def test_issue_date_in_the_past_is_rejected():
    headers, client_id = _setup()
    for days_ago in (1, 3, 31, 150):
        res = _create(headers, client_id, issue_iso(-days_ago))
        assert res.status_code == 422, days_ago
        assert "anterior a hoy" in res.json()["detail"][0]["msg"]


def test_issue_date_today_and_future_are_accepted():
    headers, client_id = _setup()
    for days in (0, 1, 45, 400):
        assert _create(headers, client_id, issue_iso(days)).status_code == 200, days


def test_business_today_is_computed_in_the_business_timezone_not_the_server_zone():
    from zoneinfo import ZoneInfo

    assert clock.business_now().tzinfo == ZoneInfo("America/Argentina/Buenos_Aires")
    assert business_date(0) == datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).date()


# ---------- cerca de medianoche (servidor en UTC, usuarios en Argentina, UTC-3) ----------


def test_late_evening_argentina_still_accepts_todays_argentine_date(frozen_utc_now):
    """23:30 del 13/10 en Argentina = 02:30 UTC del 14/10. Para el usuario "hoy"
    sigue siendo el 13: debe aceptarse, aunque el reloj del servidor ya diga 14."""
    frozen_utc_now(2026, 10, 14, 2, 30)
    headers, client_id = _setup()
    assert _create(headers, client_id, "2026-10-13T00:00:00").status_code == 200
    assert _create(headers, client_id, "2026-10-14T00:00:00").status_code == 200
    assert _create(headers, client_id, "2026-10-12T00:00:00").status_code == 422


def test_last_second_before_argentine_midnight(frozen_utc_now):
    frozen_utc_now(2026, 10, 14, 2, 59, 59)  # 23:59:59 del 13/10 en Argentina
    headers, client_id = _setup()
    assert _create(headers, client_id, "2026-10-13T00:00:00").status_code == 200
    assert _create(headers, client_id, "2026-10-12T00:00:00").status_code == 422


def test_first_second_after_argentine_midnight_rejects_the_previous_day(frozen_utc_now):
    frozen_utc_now(2026, 10, 14, 3, 0, 0)  # 00:00:00 del 14/10 en Argentina
    headers, client_id = _setup()
    res = _create(headers, client_id, "2026-10-13T00:00:00")
    assert res.status_code == 422
    assert "anterior a hoy" in res.json()["detail"][0]["msg"]
    assert _create(headers, client_id, "2026-10-14T00:00:00").status_code == 200


def test_utc_midnight_does_not_move_the_argentine_date(frozen_utc_now):
    """00:30 UTC del 14/10 son las 21:30 del 13/10 en Argentina: "hoy" es el 13."""
    frozen_utc_now(2026, 10, 14, 0, 30)
    headers, client_id = _setup()
    assert _create(headers, client_id, "2026-10-13T00:00:00").status_code == 200
    assert _create(headers, client_id, "2026-10-12T00:00:00").status_code == 422


# ---------- tipo de cambio ----------


def test_exchange_rate_must_be_positive():
    headers, client_id = _setup()
    for bad in (0, -5):
        assert _create(headers, client_id, issue_iso(), exchange_rate=bad).status_code == 422, bad
    assert _create(headers, client_id, issue_iso(), exchange_rate=1050).status_code == 200
