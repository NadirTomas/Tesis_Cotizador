from pathlib import Path

from fastapi.testclient import TestClient

from app.db.init_db import init_db
from app.db.session import engine
from app.main import app

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


def test_quotation_rejects_issue_date_with_absurd_year():
    headers, client_id = _setup()
    res = client.post(
        "/quotations",
        json={"client_id": client_id, "issue_date": "0001-05-01T00:00:00"},
        headers=headers,
    )
    assert res.status_code == 422


def test_quotation_rejects_due_date_with_absurd_year():
    """El bug reportado: un PDF mostrando 'Fecha de vencimiento: 01/05/1'."""
    headers, client_id = _setup()
    res = client.post(
        "/quotations",
        json={
            "client_id": client_id,
            "issue_date": "2026-08-20T00:00:00",
            "due_date": "0001-05-01T00:00:00",
        },
        headers=headers,
    )
    assert res.status_code == 422


def test_quotation_rejects_due_date_before_issue_date():
    headers, client_id = _setup()
    res = client.post(
        "/quotations",
        json={
            "client_id": client_id,
            "issue_date": "2026-08-20T00:00:00",
            "due_date": "2026-08-10T00:00:00",
        },
        headers=headers,
    )
    assert res.status_code == 422


def test_quotation_accepts_due_date_equal_to_issue_date():
    headers, client_id = _setup()
    res = client.post(
        "/quotations",
        json={
            "client_id": client_id,
            "issue_date": "2026-08-20T00:00:00",
            "due_date": "2026-08-20T00:00:00",
        },
        headers=headers,
    )
    assert res.status_code == 200


def test_quotation_accepts_due_date_after_issue_date():
    headers, client_id = _setup()
    res = client.post(
        "/quotations",
        json={
            "client_id": client_id,
            "issue_date": "2026-08-20T00:00:00",
            "due_date": "2026-09-20T00:00:00",
        },
        headers=headers,
    )
    assert res.status_code == 200


def test_quotation_without_due_date_still_works():
    headers, client_id = _setup()
    res = client.post(
        "/quotations",
        json={"client_id": client_id, "issue_date": "2026-08-20T00:00:00"},
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["due_date"] is None
