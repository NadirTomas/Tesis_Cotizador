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


def _register_and_create_company(email: str, company_name: str) -> dict:
    res = client.post("/auth/register", json={"email": email, "password": "Password1!"})
    assert res.status_code == 201
    token = res.json()["access_token"]
    res = client.post(
        "/companies",
        json={"company_name": company_name},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    company_id = res.json()["id"]
    return {"Authorization": f"Bearer {token}", "X-Company-Id": str(company_id)}, company_id


def _setup_two_companies():
    _reset_db_file()
    init_db()
    headers_a, company_a = _register_and_create_company("owner_a@test.com", "Empresa A")
    headers_b, company_b = _register_and_create_company("owner_b@test.com", "Empresa B")
    return headers_a, company_a, headers_b, company_b


def test_client_isolation_between_companies():
    headers_a, _, headers_b, _ = _setup_two_companies()

    res = client.post("/clients", json={"name": "Cliente A"}, headers=headers_a)
    assert res.status_code == 200
    client_a_id = res.json()["id"]

    res = client.get("/clients", headers=headers_b)
    assert res.status_code == 200
    assert res.json() == []

    res = client.get(f"/clients/{client_a_id}", headers=headers_b)
    assert res.status_code == 404


def test_cannot_force_company_id_not_a_member_of():
    headers_a, company_a, headers_b, _ = _setup_two_companies()

    forged_headers = {**headers_b, "X-Company-Id": str(company_a)}
    res = client.get("/clients", headers=forged_headers)
    assert res.status_code == 403


def test_cannot_create_quotation_with_client_from_other_company():
    headers_a, _, headers_b, _ = _setup_two_companies()

    res = client.post("/clients", json={"name": "Cliente A"}, headers=headers_a)
    client_a_id = res.json()["id"]

    res = client.post(
        "/quotations",
        json={"client_id": client_a_id, "issue_date": "2026-08-20T00:00:00"},
        headers=headers_b,
    )
    assert res.status_code == 404


def test_cannot_use_machine_config_from_other_company_in_quotation_item():
    headers_a, _, headers_b, _ = _setup_two_companies()

    res = client.post(
        "/materials",
        json={"name": "Acero A", "material_type": "Acero al carbono", "thickness_mm": 3, "sheet_width_mm": 1500, "sheet_height_mm": 3000, "sheet_cost_ars": 85000},
        headers=headers_a,
    )
    material_a = res.json()["id"]
    client.post(
        "/machine-configs",
        json={"material_id": material_a, "cut_speed_mm_min": 3000, "machine_cost_per_hour_ars": 18000, "setup_time_min": 10},
        headers=headers_a,
    )
    res = client.post("/pieces", json={"name": "Pieza A", "material_id": material_a}, headers=headers_a)
    piece_a = res.json()["id"]
    res = client.post("/clients", json={"name": "Cliente A"}, headers=headers_a)
    client_a_id = res.json()["id"]
    res = client.post(
        "/quotations",
        json={"client_id": client_a_id, "issue_date": "2026-08-20T00:00:00"},
        headers=headers_a,
    )
    quotation_a = res.json()["id"]

    # B intenta usar el material/pieza/quotation de A directamente por id
    res = client.post(
        "/quotation-items",
        json={
            "quotation_id": quotation_a,
            "piece_id": piece_a,
            "material_id": material_a,
            "quantity": 1,
            "margin_percent": 10,
        },
        headers=headers_b,
    )
    assert res.status_code == 404


def test_quotation_numbering_independent_per_company():
    headers_a, _, headers_b, _ = _setup_two_companies()

    res = client.post("/clients", json={"name": "Cliente A"}, headers=headers_a)
    client_a_id = res.json()["id"]
    res = client.post("/clients", json={"name": "Cliente B"}, headers=headers_b)
    client_b_id = res.json()["id"]

    res = client.post(
        "/quotations",
        json={"client_id": client_a_id, "issue_date": "2026-08-20T00:00:00"},
        headers=headers_a,
    )
    assert res.json()["number"] == "COT-0001"

    res = client.post(
        "/quotations",
        json={"client_id": client_b_id, "issue_date": "2026-08-20T00:00:00"},
        headers=headers_b,
    )
    assert res.json()["number"] == "COT-0001"


def test_deactivated_company_blocks_its_members():
    """
    No existe ningún endpoint hoy que ponga Company.is_active en False (no
    hay "dar de baja una empresa" implementado) -- se simula directo por
    DB para probar que get_current_company igual bloquea el acceso, de
    forma preventiva para el día que esa funcionalidad se agregue.
    """
    from app.db.session import SessionLocal
    from app.models.company import Company

    headers, company_id = _register_and_create_company("owner_deactivated@test.com", "Empresa Desactivada")

    res = client.get("/clients", headers=headers)
    assert res.status_code == 200

    db = SessionLocal()
    db.query(Company).filter(Company.id == company_id).update({"is_active": False})
    db.commit()
    db.close()

    res = client.get("/clients", headers=headers)
    assert res.status_code == 403
