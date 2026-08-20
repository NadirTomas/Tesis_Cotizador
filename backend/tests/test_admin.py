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


def test_create_company_requires_correct_secret(monkeypatch):
    _reset_db_file()
    init_db()
    monkeypatch.setattr("app.api.v1.routes_admin.settings.ADMIN_SECRET", "s3cret")

    res = client.post(
        "/admin/companies",
        json={"company_name": "Cliente Nuevo", "owner_email": "nuevo@test.com", "owner_password": "Password1!"},
        headers={"X-Admin-Secret": "wrong"},
    )
    assert res.status_code == 403


def test_create_company_disabled_without_configured_secret():
    _reset_db_file()
    init_db()
    # ADMIN_SECRET default is "" -> siempre 403, incluso mandando el string vacío
    res = client.post(
        "/admin/companies",
        json={"company_name": "Cliente Nuevo", "owner_email": "nuevo@test.com", "owner_password": "Password1!"},
        headers={"X-Admin-Secret": ""},
    )
    assert res.status_code == 403


def test_create_company_with_correct_secret(monkeypatch):
    _reset_db_file()
    init_db()
    monkeypatch.setattr("app.api.v1.routes_admin.settings.ADMIN_SECRET", "s3cret")

    res = client.post(
        "/admin/companies",
        json={"company_name": "Cliente Nuevo", "owner_email": "nuevo@test.com", "owner_password": "Password1!"},
        headers={"X-Admin-Secret": "s3cret"},
    )
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["company_name"] == "Cliente Nuevo"
    assert data["owner_created"] is True

    # el nuevo owner ya puede loguear y ve su empresa
    res = client.post("/auth/login", json={"email": "nuevo@test.com", "password": "Password1!"})
    assert res.status_code == 200
    token = res.json()["access_token"]

    res = client.get("/companies/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    companies = res.json()
    assert len(companies) == 1
    assert companies[0]["role"] == "owner"


def test_create_company_reuses_existing_user_email(monkeypatch):
    _reset_db_file()
    init_db()
    monkeypatch.setattr("app.api.v1.routes_admin.settings.ADMIN_SECRET", "s3cret")

    client.post("/auth/register", json={"email": "existente@test.com", "password": "Password1!"})

    res = client.post(
        "/admin/companies",
        json={"company_name": "Otra Empresa", "owner_email": "existente@test.com", "owner_password": "loquesea"},
        headers={"X-Admin-Secret": "s3cret"},
    )
    assert res.status_code == 201
    assert res.json()["owner_created"] is False
