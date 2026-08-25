"""
DELETE /quotations/{id} — hallazgo CRÍTICO #1 del informe de auditoría.

Toda cotización tiene al menos un QuotationEvent "created" desde su alta
(routes_quotations.create_quotation). La FK original de
quotation_events.quotation_id no tenía ON DELETE CASCADE, así que este
endpoint fallaba siempre en PostgreSQL para cotizaciones en draft
(ForeignKeyViolation) — invisible en este mismo test suite hasta ahora
porque SQLite no enforce foreign keys por defecto. app/db/session.py ahora
activa PRAGMA foreign_keys=ON para SQLite, así que estos tests corren con
el mismo enforcement de integridad referencial que Postgres siempre tuvo.
"""

from pathlib import Path

from fastapi.testclient import TestClient

from app.db.init_db import init_db
from app.db.session import SessionLocal, engine
from app.main import app
from app.models.quotation import Quotation
from app.models.quotation_event import QuotationEvent
from app.models.quotation_item import QuotationItem

client = TestClient(app)


def _reset_db_file() -> None:
    engine.dispose()
    db_path = Path("cotizalaser.db")
    if db_path.exists():
        db_path.unlink()


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


def _create_material(headers):
    res = client.post(
        "/materials",
        json={
            "name": "Acero", "material_type": "Acero al carbono", "thickness_mm": 3,
            "sheet_width_mm": 1500, "sheet_height_mm": 3000, "sheet_cost_ars": 85000,
        },
        headers=headers,
    )
    assert res.status_code == 200
    return res.json()["id"]


def _create_machine_config(headers, material_id):
    res = client.post(
        "/machine-configs",
        json={
            "material_id": material_id, "cut_speed_mm_min": 3000,
            "machine_cost_per_hour_ars": 18000, "setup_time_min": 10,
        },
        headers=headers,
    )
    assert res.status_code == 200


def _rect_dxf(w: float, h: float) -> str:
    return (
        "0\nSECTION\n2\nENTITIES\n0\nLWPOLYLINE\n8\n0\n90\n4\n70\n1\n"
        f"10\n0\n20\n0\n10\n{w}\n20\n0\n10\n{w}\n20\n{h}\n10\n0\n20\n{h}\n"
        "0\nENDSEC\n0\nEOF\n"
    )


def _create_piece_with_dxf(headers, material_id, w=100, h=50, name="Pieza"):
    res = client.post("/pieces", json={"name": name, "material_id": material_id}, headers=headers)
    piece_id = res.json()["id"]
    files = {"file": (f"{name}.dxf", _rect_dxf(w, h).encode("utf-8"), "application/dxf")}
    up = client.post(f"/pieces/{piece_id}/upload-dxf", files=files, headers=headers)
    assert up.status_code == 200
    return piece_id


def _create_client_record(headers, name="Cliente"):
    res = client.post("/clients", json={"name": name}, headers=headers)
    assert res.status_code == 200
    return res.json()["id"]


def _create_quotation(headers, client_id):
    res = client.post(
        "/quotations", json={"client_id": client_id, "issue_date": "2026-08-26T00:00:00"}, headers=headers
    )
    assert res.status_code == 200
    return res.json()["id"]


def _create_quotation_item(headers, quotation_id, piece_id, material_id):
    res = client.post(
        "/quotation-items",
        json={"quotation_id": quotation_id, "piece_id": piece_id, "material_id": material_id, "quantity": 2},
        headers=headers,
    )
    assert res.status_code == 200
    return res.json()["id"]


def _setup_draft_quotation_with_item(email="owner_del@test.com", company_name="Empresa Delete"):
    _reset_db_file()
    init_db()
    headers, _ = _register_and_create_company(email, company_name)
    material_id = _create_material(headers)
    _create_machine_config(headers, material_id)
    piece_id = _create_piece_with_dxf(headers, material_id)
    client_id = _create_client_record(headers)
    quotation_id = _create_quotation(headers, client_id)
    item_id = _create_quotation_item(headers, quotation_id, piece_id, material_id)
    return headers, quotation_id, item_id


def _db_counts(quotation_id: int) -> tuple[int, int, int]:
    """(cotizaciones, items, events) restantes para ese quotation_id — consulta directa a la DB."""
    db = SessionLocal()
    try:
        q = db.query(Quotation).filter(Quotation.id == quotation_id).count()
        items = db.query(QuotationItem).filter(QuotationItem.quotation_id == quotation_id).count()
        events = db.query(QuotationEvent).filter(QuotationEvent.quotation_id == quotation_id).count()
        return q, items, events
    finally:
        db.close()


# A. crear draft → tiene evento "created" → DELETE → 204
def test_draft_quotation_has_created_event_and_deletes_with_204():
    headers, quotation_id, _item_id = _setup_draft_quotation_with_item()

    res = client.get(f"/quotations/{quotation_id}/events", headers=headers)
    assert res.status_code == 200
    event_types = [e["event_type"] for e in res.json()]
    assert "created" in event_types

    res = client.delete(f"/quotations/{quotation_id}", headers=headers)
    assert res.status_code == 204


# B. quotation, items y events asociados desaparecen (antes del fix esto
# ni siquiera llegaba a devolver 204 en Postgres — ver docstring del módulo)
def test_delete_cascades_items_and_events():
    headers, quotation_id, item_id = _setup_draft_quotation_with_item()

    q_before, items_before, events_before = _db_counts(quotation_id)
    assert q_before == 1
    assert items_before == 1
    assert events_before >= 1  # al menos "created"; también hay "item_added"

    res = client.delete(f"/quotations/{quotation_id}", headers=headers)
    assert res.status_code == 204

    q_after, items_after, events_after = _db_counts(quotation_id)
    assert (q_after, items_after, events_after) == (0, 0, 0)

    # También por API: la cotización ya no existe.
    res = client.get(f"/quotations/{quotation_id}", headers=headers)
    assert res.status_code == 404


# C. sent/accepted/cancelled no se pueden borrar — la regla funcional
# existente ("solo se elimina en draft") se preserva sin cambios.
def test_cannot_delete_quotation_outside_draft():
    for target_status, chain in [
        ("sent", ["sent"]),
        ("accepted", ["sent", "accepted"]),
        ("cancelled", ["cancelled"]),
    ]:
        headers, quotation_id, _item_id = _setup_draft_quotation_with_item()
        for status in chain:
            res = client.patch(f"/quotations/{quotation_id}/status", json={"status": status}, headers=headers)
            assert res.status_code == 200

        res = client.delete(f"/quotations/{quotation_id}", headers=headers)
        assert res.status_code == 400, f"esperaba 400 al intentar borrar en estado '{target_status}'"

        # sigue existiendo, nada se tocó
        res = client.get(f"/quotations/{quotation_id}", headers=headers)
        assert res.status_code == 200
        assert res.json()["status"] == target_status


# D. cross-tenant: empresa B no puede borrar una cotización de empresa A
def test_other_company_cannot_delete_quotation():
    headers_a, quotation_id, _item_id = _setup_draft_quotation_with_item("owner_del_a@test.com", "Empresa DelA")
    headers_b, _ = _register_and_create_company("owner_del_b@test.com", "Empresa DelB")

    res = client.delete(f"/quotations/{quotation_id}", headers=headers_b)
    assert res.status_code == 404

    res = client.get(f"/quotations/{quotation_id}", headers=headers_a)
    assert res.status_code == 200  # sigue existiendo, la empresa A no se vio afectada
