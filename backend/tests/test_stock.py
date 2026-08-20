from pathlib import Path

from fastapi.testclient import TestClient

from app.db.init_db import init_db
from app.db.session import engine
from app.main import app

client = TestClient(app)

TRIANGLE_GEOMETRY = {
    "type": "Polygon",
    "coordinates": [[[0, 0], [100, 0], [0, 50], [0, 0]]],
}

BOWTIE_GEOMETRY = {
    "type": "Polygon",
    "coordinates": [[[0, 0], [10, 10], [10, 0], [0, 10], [0, 0]]],
}


def _reset_db_file() -> None:
    engine.dispose()
    db_path = Path("cotizalaser.db")
    if db_path.exists():
        db_path.unlink()


def _login(email: str, password: str = "Password1!") -> str:
    res = client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


def _register_and_create_company(email: str, company_name: str) -> tuple[dict, int]:
    res = client.post("/auth/register", json={"email": email, "password": "Password1!"})
    assert res.status_code == 201
    token = res.json()["access_token"]
    res = client.post(
        "/companies", json={"company_name": company_name}, headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 201
    company_id = res.json()["id"]
    return {"Authorization": f"Bearer {token}", "X-Company-Id": str(company_id)}, company_id


def _setup_owner_and_employee():
    _reset_db_file()
    init_db()
    owner_headers, company_id = _register_and_create_company("owner@test.com", "Empresa Test")
    res = client.post(
        f"/companies/{company_id}/members",
        json={"email": "employee@test.com", "password": "Password1!", "role": "employee"},
        headers=owner_headers,
    )
    assert res.status_code == 201
    employee_token = _login("employee@test.com")
    employee_headers = {"Authorization": f"Bearer {employee_token}", "X-Company-Id": str(company_id)}
    return owner_headers, employee_headers, company_id


def _create_material(headers, thickness_mm=3, material_type="Acero al carbono", alloy="SAE 1010", name="Acero"):
    res = client.post(
        "/materials",
        json={
            "name": name,
            "material_type": material_type,
            "alloy": alloy,
            "thickness_mm": thickness_mm,
            "sheet_width_mm": 1500,
            "sheet_height_mm": 3000,
            "sheet_cost_ars": 85000,
        },
        headers=headers,
    )
    assert res.status_code == 200
    return res.json()["id"]


# ---------- Multiempresa ----------


def test_stock_isolated_between_companies():
    _reset_db_file()
    init_db()
    headers_a, company_a = _register_and_create_company("owner_a@test.com", "Empresa A")
    headers_b, _ = _register_and_create_company("owner_b@test.com", "Empresa B")

    material_a = _create_material(headers_a)
    res = client.post(
        "/stock",
        json={"material_id": material_a, "stock_type": "FULL_SHEET", "width_mm": 3000, "height_mm": 1500},
        headers=headers_a,
    )
    assert res.status_code == 200
    sheet_id = res.json()["id"]

    res = client.get("/stock", headers=headers_b)
    assert res.status_code == 200
    assert res.json() == []


def test_cannot_access_other_company_stock_by_forcing_id():
    _reset_db_file()
    init_db()
    headers_a, _ = _register_and_create_company("owner_a2@test.com", "Empresa A2")
    headers_b, _ = _register_and_create_company("owner_b2@test.com", "Empresa B2")

    material_a = _create_material(headers_a)
    res = client.post(
        "/stock",
        json={"material_id": material_a, "stock_type": "FULL_SHEET", "width_mm": 3000, "height_mm": 1500},
        headers=headers_a,
    )
    sheet_id = res.json()["id"]

    res = client.get(f"/stock/{sheet_id}", headers=headers_b)
    assert res.status_code == 404

    res = client.patch(f"/stock/{sheet_id}/discard", headers=headers_b)
    assert res.status_code == 404


# ---------- Materiales ----------


def test_different_thickness_creates_different_material_variant():
    _reset_db_file()
    init_db()
    headers, _ = _register_and_create_company("owner_thick@test.com", "Empresa Thick")
    thin_id = _create_material(headers, thickness_mm=3.2)
    thick_id = _create_material(headers, thickness_mm=4.75, name="Acero 4.75")
    assert thin_id != thick_id

    client.post("/stock", json={"material_id": thin_id, "stock_type": "FULL_SHEET", "width_mm": 1000, "height_mm": 1000}, headers=headers)
    client.post("/stock", json={"material_id": thick_id, "stock_type": "FULL_SHEET", "width_mm": 1000, "height_mm": 1000}, headers=headers)

    res = client.get("/stock", params={"thickness_mm": 3.2}, headers=headers)
    assert len(res.json()) == 1
    assert res.json()[0]["material_id"] == thin_id


def test_different_alloy_distinguished():
    _reset_db_file()
    init_db()
    headers, _ = _register_and_create_company("owner_alloy@test.com", "Empresa Alloy")
    sae_id = _create_material(headers, alloy="SAE 1010", name="Carbono SAE1010")
    aisi_id = _create_material(headers, material_type="Acero inoxidable", alloy="AISI 304", name="Inox AISI304")
    assert sae_id != aisi_id

    client.post("/stock", json={"material_id": sae_id, "stock_type": "FULL_SHEET", "width_mm": 1000, "height_mm": 1000}, headers=headers)
    client.post("/stock", json={"material_id": aisi_id, "stock_type": "FULL_SHEET", "width_mm": 1000, "height_mm": 1000}, headers=headers)

    res = client.get("/stock", params={"alloy": "AISI 304"}, headers=headers)
    assert len(res.json()) == 1
    assert res.json()[0]["material_id"] == aisi_id


# ---------- Stock ----------


def test_create_full_sheet():
    _reset_db_file()
    init_db()
    headers, _ = _register_and_create_company("owner_sheet@test.com", "Empresa Sheet")
    material_id = _create_material(headers)

    res = client.post(
        "/stock",
        json={"material_id": material_id, "stock_type": "FULL_SHEET", "width_mm": 3000, "height_mm": 1500},
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["code"] == "CH-0001"
    assert data["status"] == "AVAILABLE"
    assert data["original_area_mm2"] == 3000 * 1500
    assert data["remaining_area_mm2"] == 3000 * 1500
    assert data["original_width_mm"] == 3000
    assert data["original_height_mm"] == 1500


def test_create_remnant_with_irregular_geometry():
    _reset_db_file()
    init_db()
    headers, _ = _register_and_create_company("owner_remnant@test.com", "Empresa Remnant")
    material_id = _create_material(headers)

    res = client.post(
        "/stock",
        json={"material_id": material_id, "stock_type": "REMNANT", "geometry": TRIANGLE_GEOMETRY},
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["code"] == "R-0001"
    assert data["stock_type"] == "REMNANT"
    assert data["original_area_mm2"] == 2500.0  # 0.5 * 100 * 50
    assert data["original_width_mm"] == 100
    assert data["original_height_mm"] == 50


def test_invalid_geometry_rejected():
    _reset_db_file()
    init_db()
    headers, _ = _register_and_create_company("owner_invalid@test.com", "Empresa Invalid")
    material_id = _create_material(headers)

    res = client.post(
        "/stock",
        json={"material_id": material_id, "stock_type": "REMNANT", "geometry": BOWTIE_GEOMETRY},
        headers=headers,
    )
    assert res.status_code == 400


def test_stock_numbering_independent_per_company_and_type():
    _reset_db_file()
    init_db()
    headers_a, _ = _register_and_create_company("owner_num_a@test.com", "Empresa NumA")
    headers_b, _ = _register_and_create_company("owner_num_b@test.com", "Empresa NumB")
    material_a = _create_material(headers_a)
    material_b = _create_material(headers_b)

    for _ in range(2):
        res = client.post(
            "/stock",
            json={"material_id": material_a, "stock_type": "FULL_SHEET", "width_mm": 1000, "height_mm": 1000},
            headers=headers_a,
        )
    codes_a_sheets = res.json()["code"]
    res = client.post(
        "/stock",
        json={"material_id": material_a, "stock_type": "REMNANT", "geometry": TRIANGLE_GEOMETRY},
        headers=headers_a,
    )
    assert res.json()["code"] == "R-0001"  # contador de retazos independiente del de chapas

    res = client.post(
        "/stock",
        json={"material_id": material_b, "stock_type": "FULL_SHEET", "width_mm": 1000, "height_mm": 1000},
        headers=headers_b,
    )
    assert res.json()["code"] == "CH-0001"  # empresa B arranca su propio contador desde cero
    assert codes_a_sheets == "CH-0002"


# ---------- Roles ----------


def test_owner_can_administer_stock_employee_can_only_read():
    owner_headers, employee_headers, _ = _setup_owner_and_employee()
    material_id = _create_material(owner_headers)

    res = client.post(
        "/stock",
        json={"material_id": material_id, "stock_type": "FULL_SHEET", "width_mm": 1000, "height_mm": 1000},
        headers=owner_headers,
    )
    assert res.status_code == 200
    sheet_id = res.json()["id"]

    res = client.patch(f"/stock/{sheet_id}/discard", headers=owner_headers)
    assert res.status_code == 200
    assert res.json()["status"] == "DISCARDED"

    res = client.get("/stock", headers=employee_headers)
    assert res.status_code == 200
    assert len(res.json()) == 1

    res = client.get(f"/stock/{sheet_id}", headers=employee_headers)
    assert res.status_code == 200

    res = client.post(
        "/stock",
        json={"material_id": material_id, "stock_type": "FULL_SHEET", "width_mm": 500, "height_mm": 500},
        headers=employee_headers,
    )
    assert res.status_code == 403

    res = client.put(f"/stock/{sheet_id}", json={"material_id": material_id}, headers=employee_headers)
    assert res.status_code == 403

    res = client.patch(f"/stock/{sheet_id}/discard", headers=employee_headers)
    assert res.status_code == 403
