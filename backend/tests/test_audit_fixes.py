from pathlib import Path

from fastapi.testclient import TestClient

from app.db.init_db import init_db
from app.db.session import engine
from app.main import app

client = TestClient(app)

RECT_100x50_DXF = """0
SECTION
2
HEADER
9
$ACADVER
1
AC1027
0
ENDSEC
0
SECTION
2
ENTITIES
0
LWPOLYLINE
8
0
90
4
70
1
10
0
20
0
10
100
20
0
10
100
20
50
10
0
20
50
0
ENDSEC
0
EOF
"""


def _reset_db_file() -> None:
    engine.dispose()
    db_path = Path("cotizalaser.db")
    if db_path.exists():
        db_path.unlink()


def _setup_owner():
    _reset_db_file()
    init_db()
    res = client.post("/auth/register", json={"email": "owner@test.com", "password": "Password1!"})
    token = res.json()["access_token"]
    res = client.post(
        "/companies", json={"company_name": "Empresa Test"}, headers={"Authorization": f"Bearer {token}"}
    )
    company_id = res.json()["id"]
    return {"Authorization": f"Bearer {token}", "X-Company-Id": str(company_id)}


def _create_material(headers):
    res = client.post(
        "/materials",
        json={"name": "Acero", "material_type": "Acero al carbono", "thickness_mm": 3, "sheet_width_mm": 1500, "sheet_height_mm": 3000, "sheet_cost_ars": 85000},
        headers=headers,
    )
    return res.json()["id"]


def test_machine_config_rejects_zero_cut_speed():
    headers = _setup_owner()
    material_id = _create_material(headers)
    res = client.post(
        "/machine-configs",
        json={"material_id": material_id, "cut_speed_mm_min": 0, "machine_cost_per_hour_ars": 18000, "setup_time_min": 10},
        headers=headers,
    )
    assert res.status_code == 422


def test_machine_config_rejects_duplicate_active_for_same_material():
    headers = _setup_owner()
    material_id = _create_material(headers)
    payload = {"material_id": material_id, "cut_speed_mm_min": 3000, "machine_cost_per_hour_ars": 18000, "setup_time_min": 10}
    res = client.post("/machine-configs", json=payload, headers=headers)
    assert res.status_code == 200

    res = client.post("/machine-configs", json=payload, headers=headers)
    assert res.status_code == 400


def test_quotation_item_rejects_negative_quantity():
    headers = _setup_owner()
    material_id = _create_material(headers)
    client.post(
        "/machine-configs",
        json={"material_id": material_id, "cut_speed_mm_min": 3000, "machine_cost_per_hour_ars": 18000, "setup_time_min": 10},
        headers=headers,
    )
    res = client.post("/pieces", json={"name": "Pieza", "material_id": material_id}, headers=headers)
    piece_id = res.json()["id"]
    res = client.post("/clients", json={"name": "Cliente"}, headers=headers)
    client_id = res.json()["id"]
    res = client.post(
        "/quotations", json={"client_id": client_id, "issue_date": "2026-08-21T00:00:00"}, headers=headers
    )
    quotation_id = res.json()["id"]

    res = client.post(
        "/quotation-items",
        json={"quotation_id": quotation_id, "piece_id": piece_id, "material_id": material_id, "quantity": -5, "margin_percent": 20},
        headers=headers,
    )
    assert res.status_code == 422


def test_update_quotation_item_recalculates():
    headers = _setup_owner()
    material_id = _create_material(headers)
    client.post(
        "/machine-configs",
        json={"material_id": material_id, "cut_speed_mm_min": 3000, "machine_cost_per_hour_ars": 18000, "setup_time_min": 10},
        headers=headers,
    )
    res = client.post("/pieces", json={"name": "Pieza", "material_id": material_id}, headers=headers)
    piece_id = res.json()["id"]
    client.post(
        f"/pieces/{piece_id}/upload-dxf",
        files={"file": ("rect.dxf", RECT_100x50_DXF.encode("utf-8"), "application/dxf")},
        headers=headers,
    )
    res = client.post("/clients", json={"name": "Cliente"}, headers=headers)
    client_id = res.json()["id"]
    res = client.post(
        "/quotations", json={"client_id": client_id, "issue_date": "2026-08-21T00:00:00"}, headers=headers
    )
    quotation_id = res.json()["id"]
    res = client.post(
        "/quotation-items",
        json={"quotation_id": quotation_id, "piece_id": piece_id, "material_id": material_id, "quantity": 1, "margin_percent": 20},
        headers=headers,
    )
    item_id = res.json()["id"]
    original_total = res.json()["total_price_ars"]

    res = client.put(f"/quotation-items/{item_id}", json={"quantity": 3}, headers=headers)
    assert res.status_code == 200
    updated = res.json()
    assert updated["quantity"] == 3
    assert updated["id"] == item_id  # mismo id, no se recreó
    assert updated["total_price_ars"] != original_total

    res = client.get(f"/quotations/{quotation_id}", headers=headers)
    assert res.json()["total_ars"] == updated["total_price_ars"]
