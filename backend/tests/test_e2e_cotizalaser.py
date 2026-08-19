import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db.init_db import init_db
from app.main import app


# Paso 13: Test end-to-end del flujo principal de CotizaLaser
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

client = TestClient(app)


def _reset_db_file() -> None:
    db_path = Path("cotizalaser.db")
    if db_path.exists():
        db_path.unlink()


def test_full_flow_rect_100x50():
    _reset_db_file()
    init_db()

    response = client.post(
        "/materials",
        json={
            "name": "Acero Test",
            "thickness_mm": 2.0,
            "sheet_width_mm": 1000.0,
            "sheet_height_mm": 1000.0,
            "sheet_cost_ars": 1000.0,
        },
    )
    assert response.status_code == 200
    material_id = response.json()["id"]

    response = client.post(
        "/machine-configs",
        json={
            "material_id": material_id,
            "cut_speed_mm_min": 1000.0,
            "machine_cost_per_hour_ars": 600.0,
            "setup_time_min": 0.0,
        },
    )
    assert response.status_code == 200

    response = client.post(
        "/pieces",
        json={
            "name": "Rect 100x50",
            "description": "prueba e2e",
            "material_id": material_id,
        },
    )
    assert response.status_code == 200
    piece_id = response.json()["id"]

    response = client.post(
        f"/pieces/{piece_id}/upload-dxf",
        files={
            "file": ("rect_100x50.dxf", RECT_100x50_DXF.encode("utf-8"), "application/dxf")
        },
    )
    assert response.status_code == 200
    piece_data = response.json()
    assert piece_data["length_cut_mm"] == pytest.approx(300.0, rel=1e-2)
    assert piece_data["area_mm2"] == pytest.approx(5000.0, rel=1e-2)

    response = client.post(
        "/clients",
        json={
            "name": "Cliente Test",
            "cuit_cuil": "20-12345678-9",
            "phone": "123456",
            "email": "cliente@test.com",
            "address": "Calle Falsa 123",
            "notes": "Test e2e",
        },
    )
    assert response.status_code == 200
    client_id = response.json()["id"]

    response = client.post(
        "/quotations",
        json={
            "number": "TEST-0001",
            "client_id": client_id,
            "issue_date": "2026-02-06T00:00:00",
            "due_date": "2026-02-20T00:00:00",
            "currency": "ARS",
            "exchange_rate": 1.0,
            "notes": "Test e2e quotation",
            "status": "draft",
        },
    )
    assert response.status_code == 200
    quotation_id = response.json()["id"]

    response = client.post(
        "/quotation-items",
        json={
            "quotation_id": quotation_id,
            "piece_id": piece_id,
            "material_id": material_id,
            "quantity": 2,
            "margin_percent": 20.0,
        },
    )
    assert response.status_code == 200
    item = response.json()

    assert item["cost_material_ars"] == pytest.approx(10.0, rel=1e-2)
    assert item["cost_machine_ars"] == pytest.approx(6.0, rel=1e-2)
    assert item["cost_labor_ars"] == pytest.approx(1.8, rel=1e-2)
    assert item["total_price_ars"] == pytest.approx(21.36, rel=1e-2)

    response = client.get(f"/quotations/{quotation_id}")
    assert response.status_code == 200
    quotation = response.json()
    assert quotation["total_ars"] == pytest.approx(21.36, rel=1e-2)
    assert quotation["total_usd"] == pytest.approx(21.36, rel=1e-2)

    response = client.get(f"/quotations/{quotation_id}/pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
