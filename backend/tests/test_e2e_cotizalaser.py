import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db.init_db import init_db
from app.db.session import engine
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
    engine.dispose()  # libera conexiones abiertas (Windows bloquea el archivo si no)
    db_path = Path("cotizalaser.db")
    if db_path.exists():
        db_path.unlink()


def _register_and_create_company(email: str) -> tuple[dict, int]:
    res = client.post("/auth/register", json={"email": email, "password": "Password1!"})
    assert res.status_code == 201
    token = res.json()["access_token"]
    res = client.post(
        "/companies",
        json={"company_name": "Empresa Test"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    company_id = res.json()["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Company-Id": str(company_id)}
    return headers, company_id


def test_full_flow_rect_100x50():
    _reset_db_file()
    init_db()
    headers, _ = _register_and_create_company("e2e@test.com")

    response = client.post(
        "/materials",
        json={
            "name": "Acero Test",
            "material_type": "Acero al carbono",
            "thickness_mm": 2.0,
            "sheet_width_mm": 1000.0,
            "sheet_height_mm": 1000.0,
            "sheet_cost_ars": 1000.0,
        },
        headers=headers,
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
        headers=headers,
    )
    assert response.status_code == 200

    response = client.post(
        "/pieces",
        json={
            "name": "Rect 100x50",
            "description": "prueba e2e",
            "material_id": material_id,
        },
        headers=headers,
    )
    assert response.status_code == 200
    piece_id = response.json()["id"]

    response = client.post(
        f"/pieces/{piece_id}/upload-dxf",
        files={
            "file": ("rect_100x50.dxf", RECT_100x50_DXF.encode("utf-8"), "application/dxf")
        },
        headers=headers,
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
        headers=headers,
    )
    assert response.status_code == 200
    client_id = response.json()["id"]

    response = client.post(
        "/quotations",
        json={
            "client_id": client_id,
            "issue_date": "2026-02-06T00:00:00",
            "due_date": "2026-02-20T00:00:00",
            "currency": "ARS",
            "exchange_rate": 1.0,
            "notes": "Test e2e quotation",
        },
        headers=headers,
    )
    assert response.status_code == 200
    quotation = response.json()
    quotation_id = quotation["id"]
    assert quotation["number"] == "COT-0001"

    response = client.post(
        "/quotation-items",
        json={
            "quotation_id": quotation_id,
            "piece_id": piece_id,
            "material_id": material_id,
            "quantity": 2,
            "margin_percent": 20.0,
        },
        headers=headers,
    )
    assert response.status_code == 200
    item = response.json()

    assert item["cost_material_ars"] == pytest.approx(10.0, rel=1e-2)
    assert item["cost_machine_ars"] == pytest.approx(6.0, rel=1e-2)
    assert item["cost_labor_ars"] == pytest.approx(1.8, rel=1e-2)
    assert item["total_price_ars"] == pytest.approx(21.36, rel=1e-2)

    response = client.get(f"/quotations/{quotation_id}", headers=headers)
    assert response.status_code == 200
    quotation = response.json()
    assert quotation["total_ars"] == pytest.approx(21.36, rel=1e-2)
    assert quotation["total_usd"] == pytest.approx(21.36, rel=1e-2)

    response = client.get(f"/quotations/{quotation_id}/pdf", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"


def test_full_flow_including_stock_reservation_cut_and_traceability():
    """
    Continúa exactamente donde termina test_full_flow_rect_100x50 (esa
    prueba se queda en draft + PDF) hasta el final real del flujo de
    negocio: recomendación de stock, aceptación, reserva, confirmación de
    corte, retazo generado, trazabilidad (movimientos + eventos), y PDF
    de nuevo ya con la cotización aceptada -- etapa 20 de la auditoría
    (validación end-to-end completa).
    """
    _reset_db_file()
    init_db()
    headers, _ = _register_and_create_company("e2e_full@test.com")

    material_id = client.post(
        "/materials",
        json={
            "name": "Acero Test", "material_type": "Acero al carbono", "thickness_mm": 2.0,
            "sheet_width_mm": 1000.0, "sheet_height_mm": 1000.0, "sheet_cost_ars": 1000.0,
        },
        headers=headers,
    ).json()["id"]
    client.post(
        "/machine-configs",
        json={"material_id": material_id, "cut_speed_mm_min": 1000.0, "machine_cost_per_hour_ars": 600.0, "setup_time_min": 0.0},
        headers=headers,
    )
    piece_id = client.post(
        "/pieces", json={"name": "Rect 100x50", "material_id": material_id}, headers=headers
    ).json()["id"]
    piece = client.post(
        f"/pieces/{piece_id}/upload-dxf",
        files={"file": ("rect_100x50.dxf", RECT_100x50_DXF.encode("utf-8"), "application/dxf")},
        headers=headers,
    ).json()
    assert piece["area_mm2"] == pytest.approx(5000.0, rel=1e-2)

    client_id = client.post("/clients", json={"name": "Cliente Test"}, headers=headers).json()["id"]
    quotation_id = client.post(
        "/quotations", json={"client_id": client_id, "issue_date": "2026-02-06T00:00:00"}, headers=headers
    ).json()["id"]
    item_id = client.post(
        "/quotation-items",
        json={"quotation_id": quotation_id, "piece_id": piece_id, "material_id": material_id, "quantity": 1},
        headers=headers,
    ).json()["id"]

    # Cargar stock: una chapa bien más grande que la pieza (100x50).
    stock = client.post(
        "/stock", json={"material_id": material_id, "stock_type": "FULL_SHEET", "width_mm": 500.0, "height_mm": 500.0},
        headers=headers,
    ).json()
    assert stock["status"] == "AVAILABLE"

    # Recomendación de chapa para la pieza.
    res = client.post("/stock/recommendations", json={"piece_id": piece_id, "material_id": material_id}, headers=headers)
    assert res.status_code == 200
    recommendations = res.json()
    assert any(r["stock_sheet_id"] == stock["id"] for r in recommendations)

    # Aceptar la cotización (draft -> sent -> accepted) -- requisito para reservar.
    assert client.patch(f"/quotations/{quotation_id}/status", json={"status": "sent"}, headers=headers).status_code == 200
    assert client.patch(f"/quotations/{quotation_id}/status", json={"status": "accepted"}, headers=headers).status_code == 200

    # Reservar material.
    res = client.post(
        f"/stock/{stock['id']}/reserve",
        json={"piece_id": piece_id, "material_id": material_id, "quotation_id": quotation_id, "quotation_item_id": item_id},
        headers=headers,
    )
    assert res.status_code == 200
    reservation = res.json()
    assert reservation["status"] == "ACTIVE"
    assert client.get(f"/stock/{stock['id']}", headers=headers).json()["status"] == "RESERVED"

    # Confirmar corte -> genera retazo.
    res = client.post(f"/stock/reservations/{reservation['id']}/confirm-cut", headers=headers)
    assert res.status_code == 200
    confirm = res.json()
    assert confirm["status"] == "CONSUMED"
    assert len(confirm["remnants"]) == 1
    remnant = confirm["remnants"][0]
    assert remnant["code"].startswith("R-")

    # Trazabilidad: el retazo apunta a la chapa y a la cotización de origen.
    remnant_data = client.get(f"/stock/{remnant['stock_sheet_id']}", headers=headers).json()
    assert remnant_data["source_sheet_id"] == stock["id"]
    assert remnant_data["source_quotation_id"] == quotation_id
    assert remnant_data["status"] == "AVAILABLE"

    # Trazabilidad: movimientos de la chapa original, en orden cronológico.
    movements = client.get(f"/stock/{stock['id']}/movements", headers=headers).json()
    assert [m["movement_type"] for m in movements] == ["CREATED", "RESERVED", "CONSUMED"]

    # Trazabilidad: historial de eventos de la cotización.
    events = client.get(f"/quotations/{quotation_id}/events", headers=headers).json()
    event_types = {e["event_type"] for e in events}
    assert {"created", "item_added", "status_changed"} <= event_types

    # El PDF se sigue generando bien ya con la cotización accepted y el
    # material consumido -- no depende del estado del stock.
    res = client.get(f"/quotations/{quotation_id}/pdf", headers=headers)
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
