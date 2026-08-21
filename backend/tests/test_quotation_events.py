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


def test_quotation_lifecycle_generates_expected_events():
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
        json={"quotation_id": quotation_id, "piece_id": piece_id, "material_id": material_id, "quantity": 2, "margin_percent": 10},
        headers=headers,
    )
    item_id = res.json()["id"]

    client.put(f"/quotation-items/{item_id}", json={"quantity": 5}, headers=headers)
    client.patch(f"/quotations/{quotation_id}/status", json={"status": "sent"}, headers=headers)

    # Una vez "sent" el contenido queda fijo hasta que se acepte o cancele —
    # ni editar ni eliminar ítems está permitido en este estado.
    res = client.delete(f"/quotation-items/{item_id}", headers=headers)
    assert res.status_code == 400

    client.patch(f"/quotations/{quotation_id}/status", json={"status": "accepted"}, headers=headers)
    # "accepted" sí permite eliminar (da de baja una pieza puntual y libera
    # su reserva de stock si tenía una — ver routes_quotation_items.py).
    res = client.delete(f"/quotation-items/{item_id}", headers=headers)
    assert res.status_code == 204

    res = client.get(f"/quotations/{quotation_id}/events", headers=headers)
    assert res.status_code == 200
    events = res.json()
    event_types = [e["event_type"] for e in events]
    # más reciente primero
    assert event_types == [
        "item_removed", "status_changed", "status_changed", "item_updated", "item_added", "created",
    ]
    assert all(e["created_by_email"] == "owner@test.com" for e in events)
    assert "Borrador → Enviado" in events[2]["description"]
    assert "Enviado → Aceptado" in events[1]["description"]
    assert "Pieza eliminada" in events[0]["description"]


def test_events_scoped_to_company():
    headers_a = _setup_owner()
    material_id = _create_material(headers_a)
    res = client.post("/clients", json={"name": "Cliente"}, headers=headers_a)
    client_id = res.json()["id"]
    res = client.post(
        "/quotations", json={"client_id": client_id, "issue_date": "2026-08-21T00:00:00"}, headers=headers_a
    )
    quotation_id = res.json()["id"]

    res = client.post("/auth/register", json={"email": "other@test.com", "password": "Password1!"})
    token_b = res.json()["access_token"]
    res = client.post(
        "/companies", json={"company_name": "Otra Empresa"}, headers={"Authorization": f"Bearer {token_b}"}
    )
    headers_b = {"Authorization": f"Bearer {token_b}", "X-Company-Id": str(res.json()["id"])}

    res = client.get(f"/quotations/{quotation_id}/events", headers=headers_b)
    assert res.status_code == 404
