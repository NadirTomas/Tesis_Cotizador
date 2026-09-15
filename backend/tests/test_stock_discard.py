"""
Cobertura de PATCH /stock/{stock_id}/discard -- antes de este archivo, el
único caso probado era el 403 de employee (test_stock.py) y el 200 sobre
una chapa AVAILABLE recién creada. Ningún test cubría descartar una chapa
RESERVED/CONSUMED, ni las carreras discard-vs-reserve / discard-vs-
confirm-cut / discard-vs-discard.

Regla de negocio (P1 de la auditoría final, corregido 2026-09-14, ver
PROJECT_MEMORY.md): descartar solo puede pasar desde AVAILABLE.
RESERVED/CONSUMED/DISCARDED devuelven 409 -- una chapa RESERVED requiere
liberar su reserva explícitamente primero (Opción A: sin efectos
secundarios ocultos sobre una reserva/cotización activa; ver el fix de
PUT /stock/{id} en a7f25ca, mismo criterio). Antes del fix: se podía
descartar una chapa RESERVED dejando su StockReservation ACTIVE huérfana,
sin ninguna protección de carrera.
"""

from pathlib import Path

from fastapi.testclient import TestClient

from app.db.init_db import init_db
from app.db.session import SessionLocal, engine
from app.main import app
from app.models.stock_movement import StockMovement
from app.models.stock_reservation import StockReservation
from app.models.stock_sheet import StockSheet

client = TestClient(app)


# ---------- boilerplate (mismo patrón que test_stock_update.py) ----------


def _reset_db_file() -> None:
    engine.dispose()
    db_path = Path("cotizalaser.db")
    if db_path.exists():
        db_path.unlink()


def _register_and_create_company(email: str, company_name: str) -> tuple[dict, int]:
    res = client.post("/auth/register", json={"email": email, "password": "Password1!"})
    assert res.status_code == 201
    token = res.json()["access_token"]
    res = client.post("/companies", json={"company_name": company_name}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 201
    company_id = res.json()["id"]
    return {"Authorization": f"Bearer {token}", "X-Company-Id": str(company_id)}, company_id


def _login(email: str, password: str = "Password1!") -> str:
    res = client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


def _add_employee(owner_headers, company_id, email="employee_discard@test.com"):
    res = client.post(
        f"/companies/{company_id}/members",
        json={"email": email, "password": "Password1!", "role": "employee"},
        headers=owner_headers,
    )
    assert res.status_code == 201
    token = _login(email)
    return {"Authorization": f"Bearer {token}", "X-Company-Id": str(company_id)}


def _create_material(headers, material_type="Acero al carbono", alloy="SAE 1010", thickness_mm=3.0, name="Acero"):
    res = client.post(
        "/materials",
        json={
            "name": name, "material_type": material_type, "alloy": alloy, "thickness_mm": thickness_mm,
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
            "material_id": material_id, "cut_speed_mm_min": 3000, "machine_cost_per_hour_ars": 18000,
            "setup_time_min": 10,
        },
        headers=headers,
    )
    assert res.status_code == 200
    return res.json()["id"]


def _rect_dxf(w: float, h: float) -> str:
    return (
        "0\nSECTION\n2\nENTITIES\n0\nLWPOLYLINE\n8\n0\n90\n4\n70\n1\n"
        f"10\n0\n20\n0\n10\n{w}\n20\n0\n10\n{w}\n20\n{h}\n10\n0\n20\n{h}\n"
        "0\nENDSEC\n0\nEOF\n"
    )


def _create_piece_with_dxf(headers, material_id, w, h, name="Pieza"):
    files = {"file": (f"{name}.dxf", _rect_dxf(w, h).encode("utf-8"), "application/dxf")}
    res = client.post("/pieces", data={"name": name, "material_id": material_id}, files=files, headers=headers)
    assert res.status_code == 200
    return res.json()["id"]


def _create_stock(headers, material_id, width_mm=200, height_mm=200):
    res = client.post(
        "/stock",
        json={"material_id": material_id, "stock_type": "FULL_SHEET", "width_mm": width_mm, "height_mm": height_mm},
        headers=headers,
    )
    assert res.status_code == 200
    return res.json()


def _create_client_record(headers, name="Cliente"):
    res = client.post("/clients", json={"name": name}, headers=headers)
    assert res.status_code == 200
    return res.json()["id"]


def _create_quotation(headers, client_id):
    res = client.post("/quotations", json={"client_id": client_id, "issue_date": "2026-08-26T00:00:00"}, headers=headers)
    assert res.status_code == 200
    return res.json()["id"]


def _advance_to_accepted(headers, quotation_id):
    assert client.patch(f"/quotations/{quotation_id}/status", json={"status": "sent"}, headers=headers).status_code == 200
    assert client.patch(f"/quotations/{quotation_id}/status", json={"status": "accepted"}, headers=headers).status_code == 200


def _full_setup(email="owner_discard@test.com", company_name="Empresa Discard"):
    _reset_db_file()
    init_db()
    headers, company_id = _register_and_create_company(email, company_name)
    material_id = _create_material(headers)
    _create_machine_config(headers, material_id)
    return headers, company_id, material_id


def _reserve_stock(headers, stock_id, piece_id, material_id, quotation_id) -> int:
    res = client.post(
        f"/stock/{stock_id}/reserve",
        json={"piece_id": piece_id, "material_id": material_id, "quotation_id": quotation_id},
        headers=headers,
    )
    assert res.status_code == 200
    return res.json()["id"]


def _setup_reserved_stock():
    """Empresa + material + config + pieza + chapa RESERVED contra una cotización accepted."""
    headers, company_id, material_id = _full_setup()
    piece_id = _create_piece_with_dxf(headers, material_id, 100, 50)
    stock = _create_stock(headers, material_id)
    client_id = _create_client_record(headers)
    quotation_id = _create_quotation(headers, client_id)
    _advance_to_accepted(headers, quotation_id)
    reservation_id = _reserve_stock(headers, stock["id"], piece_id, material_id, quotation_id)
    return headers, company_id, material_id, piece_id, stock, quotation_id, reservation_id


def _movements(stock_id):
    db = SessionLocal()
    rows = db.query(StockMovement).filter(StockMovement.stock_sheet_id == stock_id).all()
    db.close()
    return rows


# ---------- máquina de estados ----------


def test_owner_can_discard_available_stock():
    headers, _company_id, material_id = _full_setup()
    stock = _create_stock(headers, material_id)

    res = client.patch(f"/stock/{stock['id']}/discard", headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "DISCARDED"

    movements = _movements(stock["id"])
    assert [m.movement_type for m in movements] == ["CREATED", "DISCARDED"]


def test_cannot_discard_reserved_stock():
    headers, _company_id, _material_id, _piece_id, stock, _quotation_id, reservation_id = _setup_reserved_stock()

    res = client.patch(f"/stock/{stock['id']}/discard", headers=headers)
    assert res.status_code == 409
    assert "RESERVED" in res.json()["detail"]

    stock_after = client.get(f"/stock/{stock['id']}", headers=headers).json()
    assert stock_after["status"] == "RESERVED"

    db = SessionLocal()
    reservation = db.query(StockReservation).filter(StockReservation.id == reservation_id).first()
    db.close()
    assert reservation.status == "ACTIVE"  # sigue activa, no quedó huérfana ni se tocó


def test_cannot_discard_consumed_stock():
    headers, _company_id, _material_id, _piece_id, stock, _quotation_id, reservation_id = _setup_reserved_stock()
    assert client.post(f"/stock/reservations/{reservation_id}/confirm-cut", headers=headers).status_code == 200

    res = client.patch(f"/stock/{stock['id']}/discard", headers=headers)
    assert res.status_code == 409
    assert "CONSUMED" in res.json()["detail"]

    stock_after = client.get(f"/stock/{stock['id']}", headers=headers).json()
    assert stock_after["status"] == "CONSUMED"


def test_cannot_discard_already_discarded_stock():
    headers, _company_id, material_id = _full_setup()
    stock = _create_stock(headers, material_id)
    assert client.patch(f"/stock/{stock['id']}/discard", headers=headers).status_code == 200

    res = client.patch(f"/stock/{stock['id']}/discard", headers=headers)
    assert res.status_code == 409
    assert "DISCARDED" in res.json()["detail"]

    # el segundo intento (fallido) no generó un movimiento DISCARDED extra
    movements = _movements(stock["id"])
    assert [m.movement_type for m in movements] == ["CREATED", "DISCARDED"]


# ---------- permisos / multi-tenant ----------


def test_employee_cannot_discard():
    headers, company_id, material_id = _full_setup()
    stock = _create_stock(headers, material_id)
    employee_headers = _add_employee(headers, company_id)

    res = client.patch(f"/stock/{stock['id']}/discard", headers=employee_headers)
    assert res.status_code == 403

    assert client.get(f"/stock/{stock['id']}", headers=headers).json()["status"] == "AVAILABLE"


def test_cannot_discard_stock_from_another_company():
    headers_a, _company_a, material_a = _full_setup("owner_discard_a@test.com", "Empresa Discard A")
    stock_a = _create_stock(headers_a, material_a)
    headers_b, _company_b = _register_and_create_company("owner_discard_b@test.com", "Empresa Discard B")

    res = client.patch(f"/stock/{stock_a['id']}/discard", headers=headers_b)
    assert res.status_code == 404

    assert client.get(f"/stock/{stock_a['id']}", headers=headers_a).json()["status"] == "AVAILABLE"


# ---------- carreras ----------


def test_race_discard_vs_reserve_never_leaves_orphaned_reservation(monkeypatch):
    """
    Simula un reserve concurrente que gana la carrera justo después de que
    discard leyó la chapa como AVAILABLE, pero antes de su propio UPDATE
    condicional. El resultado final debe ser coherente: nunca la
    combinación inválida que motivó este fix (chapa DISCARDED con una
    StockReservation ACTIVE apuntándole).
    """
    import sqlalchemy.orm as sa_orm

    headers, company_id, material_id = _full_setup()
    piece_id = _create_piece_with_dxf(headers, material_id, 100, 50)
    stock = _create_stock(headers, material_id)
    client_id = _create_client_record(headers)
    quotation_id = _create_quotation(headers, client_id)
    _advance_to_accepted(headers, quotation_id)

    real_first = sa_orm.Query.first
    triggered = {"done": False}

    def _first_with_race(self):
        result = real_first(self)
        if (
            not triggered["done"]
            and isinstance(result, StockSheet)
            and result.id == stock["id"]
            and result.status == "AVAILABLE"
        ):
            triggered["done"] = True
            other_db = SessionLocal()
            try:
                other_stock = other_db.query(StockSheet).filter(StockSheet.id == stock["id"]).first()
                other_stock.status = "RESERVED"
                other_db.add(
                    StockReservation(
                        company_id=company_id, stock_sheet_id=stock["id"], piece_id=piece_id,
                        quotation_id=quotation_id, quotation_item_id=None,
                        rotation=0, x=0, y=0, status="ACTIVE", created_by_id=None,
                    )
                )
                other_db.commit()
            finally:
                other_db.close()
        return result

    monkeypatch.setattr(sa_orm.Query, "first", _first_with_race)
    try:
        discard_res = client.patch(f"/stock/{stock['id']}/discard", headers=headers)
    finally:
        monkeypatch.setattr(sa_orm.Query, "first", real_first)

    final = client.get(f"/stock/{stock['id']}", headers=headers).json()
    db = SessionLocal()
    active_reservations = (
        db.query(StockReservation)
        .filter(StockReservation.stock_sheet_id == stock["id"], StockReservation.status == "ACTIVE")
        .count()
    )
    db.close()

    if discard_res.status_code == 200:
        # discard "ganó" -- entonces no debe existir ninguna reserva ACTIVE
        assert final["status"] == "DISCARDED"
        assert active_reservations == 0
    else:
        # reserve ganó la carrera -- discard debió fallar limpio
        assert discard_res.status_code == 409
        assert final["status"] == "RESERVED"
        assert active_reservations == 1

    engine.dispose()  # Windows + segunda sesión, mismo cuidado que en tests anteriores


def test_discard_deterministically_impossible_once_reserved_even_with_pending_confirm_cut():
    """
    El caso más grave encontrado en la auditoría: antes del fix, una
    carrera discard-vs-confirm-cut podía sobrescribir CONSUMED->DISCARDED
    después de generar retazos. Con el guard actual (discard solo actúa
    sobre AVAILABLE) esto queda estructuralmente imposible, no solo
    protegido por timing: una vez que la chapa deja de ser AVAILABLE
    (RESERVED), discard nunca puede tocarla, sin importar el orden de
    llegada. Se verifica de punta a punta: intentar descartar mientras
    está RESERVED falla, confirmar el corte sigue funcionando normal, y el
    resultado final nunca es un retazo generado sobre un padre DISCARDED.
    """
    headers, _company_id, _material_id, _piece_id, stock, _quotation_id, reservation_id = _setup_reserved_stock()

    # intento de descarte mientras está RESERVED -- debe fallar, siempre
    assert client.patch(f"/stock/{stock['id']}/discard", headers=headers).status_code == 409

    # el flujo normal de confirmar corte sigue intacto
    res = client.post(f"/stock/reservations/{reservation_id}/confirm-cut", headers=headers)
    assert res.status_code == 200
    result = res.json()

    parent = client.get(f"/stock/{stock['id']}", headers=headers).json()
    assert parent["status"] == "CONSUMED"  # nunca DISCARDED
    for remnant in result["remnants"]:
        remnant_data = client.get(f"/stock/{remnant['stock_sheet_id']}", headers=headers).json()
        assert remnant_data["source_sheet_id"] == stock["id"]
        assert remnant_data["status"] == "AVAILABLE"


def test_race_discard_vs_discard_only_one_movement_logged(monkeypatch):
    """Dos discards concurrentes sobre la misma chapa AVAILABLE -- solo uno
    debe tener éxito, y solo debe quedar un único movimiento DISCARDED."""
    import sqlalchemy.orm as sa_orm

    headers, company_id, material_id = _full_setup()
    stock = _create_stock(headers, material_id)

    real_first = sa_orm.Query.first
    triggered = {"done": False}

    def _first_with_race(self):
        result = real_first(self)
        if (
            not triggered["done"]
            and isinstance(result, StockSheet)
            and result.id == stock["id"]
            and result.status == "AVAILABLE"
        ):
            triggered["done"] = True
            other_db = SessionLocal()
            try:
                other_stock = other_db.query(StockSheet).filter(StockSheet.id == stock["id"]).first()
                other_stock.status = "DISCARDED"
                other_db.add(
                    StockMovement(company_id=company_id, stock_sheet_id=stock["id"], movement_type="DISCARDED")
                )
                other_db.commit()
            finally:
                other_db.close()
        return result

    monkeypatch.setattr(sa_orm.Query, "first", _first_with_race)
    try:
        res = client.patch(f"/stock/{stock['id']}/discard", headers=headers)
    finally:
        monkeypatch.setattr(sa_orm.Query, "first", real_first)

    assert res.status_code == 409  # el segundo discard (el de la request real) pierde la carrera

    movements = _movements(stock["id"])
    assert [m.movement_type for m in movements] == ["CREATED", "DISCARDED"]  # un solo DISCARDED, no dos

    engine.dispose()
