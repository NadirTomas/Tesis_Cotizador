"""
Invariante — hallazgo ALTO #2 del informe de auditoría:

    Una cotización nunca debe terminar 'cancelled' si alguna de sus
    reservas de stock ya fue (o es, concurrentemente) CONSUMED.

El resultado de una carrera cancelación-vs-confirmación-de-corte debe ser
siempre uno de estos dos, nunca un tercer estado intermedio:

    A) gana la cancelación: quotation=cancelled, reservation=RELEASED,
       stock=AVAILABLE, un confirm-cut posterior sobre esa reserva falla.
    B) gana el corte: quotation sigue 'accepted', reservation=CONSUMED,
       stock=CONSUMED, la cancelación devuelve 409 y no modifica nada.

Este archivo cubre el caso secuencial (confirm-cut ya comiteado antes de
intentar cancelar) contra SQLite, rápido y determinístico. El caso de
carrera real (dos requests genuinamente simultáneos) depende de locking a
nivel de fila de una base real — SQLite no lo reproduce de forma
confiable — así que ese escenario específico vive en un archivo aparte
contra Postgres real (ver test_quotation_cancel_confirm_race_postgres.py).
"""

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
            "name": "Acero", "material_type": "Acero al carbono", "alloy": "SAE 1010", "thickness_mm": 3,
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
    files = {"file": (f"{name}.dxf", _rect_dxf(w, h).encode("utf-8"), "application/dxf")}
    res = client.post("/pieces", data={"name": name, "material_id": material_id}, files=files, headers=headers)
    assert res.status_code == 200
    return res.json()["id"]


def _create_stock(headers, material_id, width_mm=200, height_mm=200):
    res = client.post(
        "/stock", json={"material_id": material_id, "stock_type": "FULL_SHEET", "width_mm": width_mm, "height_mm": height_mm},
        headers=headers,
    )
    assert res.status_code == 200
    return res.json()


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


def _advance_to_accepted(headers, quotation_id):
    res = client.patch(f"/quotations/{quotation_id}/status", json={"status": "sent"}, headers=headers)
    assert res.status_code == 200
    res = client.patch(f"/quotations/{quotation_id}/status", json={"status": "accepted"}, headers=headers)
    assert res.status_code == 200


def _full_setup_accepted(email="owner_race@test.com", company_name="Empresa Race"):
    _reset_db_file()
    init_db()
    headers, _ = _register_and_create_company(email, company_name)
    material_id = _create_material(headers)
    _create_machine_config(headers, material_id)
    piece_id = _create_piece_with_dxf(headers, material_id)
    stock = _create_stock(headers, material_id)
    client_id = _create_client_record(headers)
    quotation_id = _create_quotation(headers, client_id)
    _advance_to_accepted(headers, quotation_id)
    return headers, material_id, piece_id, stock, quotation_id


def _reserve(headers, stock_id, piece_id, material_id, quotation_id):
    res = client.post(
        f"/stock/{stock_id}/reserve",
        json={"piece_id": piece_id, "material_id": material_id, "quotation_id": quotation_id},
        headers=headers,
    )
    assert res.status_code == 200
    return res.json()["id"]


def _event_types(headers, quotation_id):
    res = client.get(f"/quotations/{quotation_id}/events", headers=headers)
    assert res.status_code == 200
    return [e["event_type"] for e in res.json()]  # más reciente primero


def _movement_types(headers, stock_id):
    res = client.get(f"/stock/{stock_id}/movements", headers=headers)
    assert res.status_code == 200
    return [m["movement_type"] for m in res.json()]


# 1. cancelación normal libera la reserva (cobertura base ya existe en
# test_stock_reservation.py::test_cancelling_accepted_quotation_releases_reservation;
# se repite acá en forma breve porque hace de línea base del resto del archivo).
def test_normal_cancellation_releases_reservation_and_returns_200():
    headers, material_id, piece_id, stock, quotation_id = _full_setup_accepted()
    reservation_id = _reserve(headers, stock["id"], piece_id, material_id, quotation_id)

    res = client.patch(f"/quotations/{quotation_id}/status", json={"status": "cancelled"}, headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "cancelled"

    res = client.get(f"/stock/{stock['id']}", headers=headers)
    assert res.json()["status"] == "AVAILABLE"

    assert _movement_types(headers, stock["id"]) == ["CREATED", "RESERVED", "RELEASED"]
    assert "status_changed" in _event_types(headers, quotation_id)

    # Confirmar el corte de una reserva ya liberada ya no es válido (400,
    # camino ya cubierto — solo confirma que no quedó en un limbo).
    res = client.post(f"/stock/reservations/{reservation_id}/confirm-cut", headers=headers)
    assert res.status_code == 400


# 2. cancelación de una cotización aceptada sin ninguna reserva
def test_cancellation_without_any_reservation_succeeds():
    headers, material_id, piece_id, stock, quotation_id = _full_setup_accepted()

    res = client.patch(f"/quotations/{quotation_id}/status", json={"status": "cancelled"}, headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "cancelled"


# 3. confirm-cut normal: reserva y stock quedan CONSUMED, se genera retazo
def test_normal_confirm_cut_consumes_reservation_and_stock():
    headers, material_id, piece_id, stock, quotation_id = _full_setup_accepted()
    reservation_id = _reserve(headers, stock["id"], piece_id, material_id, quotation_id)

    res = client.post(f"/stock/reservations/{reservation_id}/confirm-cut", headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "CONSUMED"

    res = client.get(f"/stock/{stock['id']}", headers=headers)
    assert res.json()["status"] == "CONSUMED"
    assert _movement_types(headers, stock["id"]) == ["CREATED", "RESERVED", "CONSUMED"]


# 4. doble confirm-cut sigue siendo idempotente (no se duplica nada)
def test_double_confirm_cut_is_idempotent():
    headers, material_id, piece_id, stock, quotation_id = _full_setup_accepted()
    reservation_id = _reserve(headers, stock["id"], piece_id, material_id, quotation_id)

    res1 = client.post(f"/stock/reservations/{reservation_id}/confirm-cut", headers=headers)
    res2 = client.post(f"/stock/reservations/{reservation_id}/confirm-cut", headers=headers)
    assert res1.status_code == 200
    assert res2.status_code == 200
    assert res1.json() == res2.json()

    res = client.get("/stock", params={"stock_type": "REMNANT"}, headers=headers)
    assert len(res.json()) == 1  # el retazo no se duplicó en la segunda llamada


# 5. cancelar DESPUÉS de un corte ya confirmado (caso secuencial, sin
# carrera real) debe devolver 409 y no tocar nada — antes del fix esto
# cancelaba silenciosamente, dejando 'cancelled' con material ya cortado.
def test_cancelling_after_confirmed_cut_returns_409_and_changes_nothing():
    headers, material_id, piece_id, stock, quotation_id = _full_setup_accepted()
    reservation_id = _reserve(headers, stock["id"], piece_id, material_id, quotation_id)

    res = client.post(f"/stock/reservations/{reservation_id}/confirm-cut", headers=headers)
    assert res.status_code == 200

    events_before = _event_types(headers, quotation_id)

    res = client.patch(f"/quotations/{quotation_id}/status", json={"status": "cancelled"}, headers=headers)
    assert res.status_code == 409

    # 7. no quedan commits parciales: la cotización sigue 'accepted', ...
    res = client.get(f"/quotations/{quotation_id}", headers=headers)
    assert res.json()["status"] == "accepted"

    # ... la reserva y el stock siguen CONSUMED (nadie los tocó), ...
    res = client.get(f"/stock/{stock['id']}", headers=headers)
    assert res.json()["status"] == "CONSUMED"

    # ... y no se registró un evento falso de "Aceptado → Cancelado".
    assert _event_types(headers, quotation_id) == events_before

    # 9. tampoco se agregó ningún StockMovement nuevo (ni RELEASED ni nada).
    assert _movement_types(headers, stock["id"]) == ["CREATED", "RESERVED", "CONSUMED"]
