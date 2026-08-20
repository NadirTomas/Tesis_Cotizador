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


def test_refresh_returns_new_valid_token():
    _reset_db_file()
    init_db()
    res = client.post("/auth/register", json={"email": "refresh@test.com", "password": "Password1!"})
    token = res.json()["access_token"]

    res = client.post("/auth/refresh", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    new_token = res.json()["access_token"]
    assert new_token

    res = client.get("/companies/me", headers={"Authorization": f"Bearer {new_token}"})
    assert res.status_code == 200


def test_refresh_rejects_invalid_token():
    _reset_db_file()
    init_db()
    res = client.post("/auth/refresh", headers={"Authorization": "Bearer not-a-real-token"})
    assert res.status_code == 401


def test_refresh_requires_auth_header():
    _reset_db_file()
    init_db()
    res = client.post("/auth/refresh")
    assert res.status_code in (401, 403)
