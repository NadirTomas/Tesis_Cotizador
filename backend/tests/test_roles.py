from pathlib import Path

from fastapi.testclient import TestClient

from app.db.init_db import init_db
from app.db.session import engine
from app.main import app

client = TestClient(app)


def _reset_db_file() -> None:
    engine.dispose()  # libera conexiones abiertas (Windows bloquea el archivo si no)
    db_path = Path("cotizalaser.db")
    if db_path.exists():
        db_path.unlink()


def _login(email: str, password: str = "Password1!") -> str:
    res = client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


def _setup_owner_and_employee():
    _reset_db_file()
    init_db()
    res = client.post("/auth/register", json={"email": "owner@test.com", "password": "Password1!"})
    owner_token = res.json()["access_token"]
    res = client.post(
        "/companies",
        json={"company_name": "Empresa Test"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    company_id = res.json()["id"]
    owner_headers = {"Authorization": f"Bearer {owner_token}", "X-Company-Id": str(company_id)}

    res = client.post(
        f"/companies/{company_id}/members",
        json={"email": "employee@test.com", "password": "Password1!", "role": "employee"},
        headers=owner_headers,
    )
    assert res.status_code == 201
    employee_token = _login("employee@test.com")
    employee_headers = {"Authorization": f"Bearer {employee_token}", "X-Company-Id": str(company_id)}

    return owner_headers, employee_headers, company_id


def test_owner_can_create_employee():
    owner_headers, _, company_id = _setup_owner_and_employee()
    res = client.post(
        f"/companies/{company_id}/members",
        json={"email": "otro@test.com", "password": "Password1!", "role": "employee"},
        headers=owner_headers,
    )
    assert res.status_code == 201


def test_employee_cannot_create_employee():
    _, employee_headers, company_id = _setup_owner_and_employee()
    res = client.post(
        f"/companies/{company_id}/members",
        json={"email": "otro@test.com", "password": "Password1!", "role": "employee"},
        headers=employee_headers,
    )
    assert res.status_code == 403


def test_owner_can_update_sensitive_config():
    owner_headers, _, _ = _setup_owner_and_employee()
    res = client.post(
        "/materials",
        json={"name": "Acero", "material_type": "Acero al carbono", "thickness_mm": 3, "sheet_width_mm": 1500, "sheet_height_mm": 3000, "sheet_cost_ars": 85000},
        headers=owner_headers,
    )
    assert res.status_code == 200


def test_employee_cannot_update_sensitive_config():
    _, employee_headers, _ = _setup_owner_and_employee()
    res = client.post(
        "/materials",
        json={"name": "Acero", "material_type": "Acero al carbono", "thickness_mm": 3, "sheet_width_mm": 1500, "sheet_height_mm": 3000, "sheet_cost_ars": 85000},
        headers=employee_headers,
    )
    assert res.status_code == 403

    res = client.post(
        "/machine-configs",
        json={"material_id": 1, "cut_speed_mm_min": 3000, "machine_cost_per_hour_ars": 18000, "setup_time_min": 10},
        headers=employee_headers,
    )
    assert res.status_code == 403


def test_employee_can_create_quotation():
    owner_headers, employee_headers, _ = _setup_owner_and_employee()
    res = client.post("/clients", json={"name": "Cliente"}, headers=owner_headers)
    client_id = res.json()["id"]

    res = client.post(
        "/quotations",
        json={"client_id": client_id, "issue_date": "2026-08-20T00:00:00"},
        headers=employee_headers,
    )
    assert res.status_code == 200


def test_cannot_leave_company_without_active_owner():
    owner_headers, _, company_id = _setup_owner_and_employee()
    res = client.get(f"/companies/{company_id}/members", headers=owner_headers)
    owner_member_id = [m for m in res.json() if m["role"] == "owner"][0]["id"]

    res = client.patch(
        f"/companies/{company_id}/members/{owner_member_id}",
        json={"is_active": False},
        headers=owner_headers,
    )
    assert res.status_code == 400

    res = client.patch(
        f"/companies/{company_id}/members/{owner_member_id}",
        json={"role": "employee"},
        headers=owner_headers,
    )
    assert res.status_code == 400


def test_cannot_duplicate_company_member():
    owner_headers, _, company_id = _setup_owner_and_employee()
    res = client.post(
        f"/companies/{company_id}/members",
        json={"email": "employee@test.com", "password": "Password1!", "role": "employee"},
        headers=owner_headers,
    )
    assert res.status_code == 409
