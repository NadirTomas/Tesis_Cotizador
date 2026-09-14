"""
Cobertura de PUT /stock/{stock_id} (corregir material_id de una chapa) --
antes de este archivo, solo un test de permisos (test_stock.py::
test_owner_can_administer_stock_employee_can_only_read, que ejercita el
403 de employee, no el camino de éxito ni ningún estado no-AVAILABLE).

Regla de negocio (confirmada 2026-09-14, ver PROJECT_MEMORY.md): el
material de una chapa solo puede corregirse mientras sigue AVAILABLE --
una vez RESERVED, CONSUMED o DISCARDED, su identidad de material forma
parte de la trazabilidad histórica y no puede modificarse. 409, no 400,
porque es un conflicto de estado (la chapa existe y el request es
válido, pero el estado actual lo impide), consistente con el resto de
transiciones de stock (reserve/confirm-cut usan el mismo código ante
una carrera de estado).
"""

from pathlib import Path

from fastapi.testclient import TestClient

from app.db.init_db import init_db
from app.db.session import SessionLocal, engine
from app.main import app
from app.models.stock_movement import StockMovement
from app.models.stock_sheet import StockSheet

client = TestClient(app)


# ---------- boilerplate (mismo patrón que test_stock_reservation.py) ----------


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


def _add_employee(owner_headers, company_id, email="employee_upd@test.com"):
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


def _full_setup(email="owner_stockupd@test.com", company_name="Empresa StockUpdate"):
    _reset_db_file()
    init_db()
    headers, company_id = _register_and_create_company(email, company_name)
    material_id = _create_material(headers)
    other_material_id = _create_material(headers, alloy="SAE 1020", name="Acero inox")
    _create_machine_config(headers, material_id)
    return headers, company_id, material_id, other_material_id


def _reserve_stock(headers, stock_id, piece_id, material_id, quotation_id) -> int:
    res = client.post(
        f"/stock/{stock_id}/reserve",
        json={"piece_id": piece_id, "material_id": material_id, "quotation_id": quotation_id},
        headers=headers,
    )
    assert res.status_code == 200
    return res.json()["id"]


# ---------- caso feliz: AVAILABLE ----------


def test_owner_can_correct_material_while_available():
    headers, _company_id, material_id, other_material_id = _full_setup()
    stock = _create_stock(headers, material_id)

    res = client.put(f"/stock/{stock['id']}", json={"material_id": other_material_id}, headers=headers)
    assert res.status_code == 200
    assert res.json()["material_id"] == other_material_id
    assert res.json()["status"] == "AVAILABLE"


def test_employee_cannot_correct_material():
    headers, company_id, material_id, other_material_id = _full_setup()
    stock = _create_stock(headers, material_id)
    employee_headers = _add_employee(headers, company_id)

    res = client.put(f"/stock/{stock['id']}", json={"material_id": other_material_id}, headers=employee_headers)
    assert res.status_code == 403

    # y el material no cambió
    res = client.get(f"/stock/{stock['id']}", headers=headers)
    assert res.json()["material_id"] == material_id


# ---------- estados no-AVAILABLE: 409, material sin cambios ----------


def test_cannot_change_material_once_reserved():
    headers, _company_id, material_id, other_material_id = _full_setup()
    piece_id = _create_piece_with_dxf(headers, material_id, 100, 50)
    stock = _create_stock(headers, material_id)
    client_id = _create_client_record(headers)
    quotation_id = _create_quotation(headers, client_id)
    _advance_to_accepted(headers, quotation_id)
    _reserve_stock(headers, stock["id"], piece_id, material_id, quotation_id)

    res = client.put(f"/stock/{stock['id']}", json={"material_id": other_material_id}, headers=headers)
    assert res.status_code == 409
    assert "RESERVED" in res.json()["detail"]

    res = client.get(f"/stock/{stock['id']}", headers=headers)
    data = res.json()
    assert data["material_id"] == material_id
    assert data["status"] == "RESERVED"


def test_cannot_change_material_once_consumed():
    headers, _company_id, material_id, other_material_id = _full_setup()
    piece_id = _create_piece_with_dxf(headers, material_id, 100, 50)
    stock = _create_stock(headers, material_id)
    client_id = _create_client_record(headers)
    quotation_id = _create_quotation(headers, client_id)
    _advance_to_accepted(headers, quotation_id)
    reservation_id = _reserve_stock(headers, stock["id"], piece_id, material_id, quotation_id)
    assert client.post(f"/stock/reservations/{reservation_id}/confirm-cut", headers=headers).status_code == 200

    res = client.put(f"/stock/{stock['id']}", json={"material_id": other_material_id}, headers=headers)
    assert res.status_code == 409
    assert "CONSUMED" in res.json()["detail"]

    res = client.get(f"/stock/{stock['id']}", headers=headers)
    data = res.json()
    assert data["material_id"] == material_id
    assert data["status"] == "CONSUMED"


def test_cannot_change_material_once_discarded():
    headers, _company_id, material_id, other_material_id = _full_setup()
    stock = _create_stock(headers, material_id)
    assert client.patch(f"/stock/{stock['id']}/discard", headers=headers).status_code == 200

    res = client.put(f"/stock/{stock['id']}", json={"material_id": other_material_id}, headers=headers)
    assert res.status_code == 409
    assert "DISCARDED" in res.json()["detail"]

    res = client.get(f"/stock/{stock['id']}", headers=headers)
    assert res.json()["material_id"] == material_id


# ---------- validación del material nuevo ----------


def test_reject_material_from_another_company():
    headers, _company_id, material_id, _other = _full_setup()
    stock = _create_stock(headers, material_id)
    headers_b, _company_b = _register_and_create_company("owner_stockupd_b@test.com", "Empresa StockUpdate B")
    material_b = _create_material(headers_b)

    res = client.put(f"/stock/{stock['id']}", json={"material_id": material_b}, headers=headers)
    assert res.status_code == 404

    res = client.get(f"/stock/{stock['id']}", headers=headers)
    assert res.json()["material_id"] == material_id


def test_reject_nonexistent_material():
    headers, _company_id, material_id, _other = _full_setup()
    stock = _create_stock(headers, material_id)

    res = client.put(f"/stock/{stock['id']}", json={"material_id": 999999}, headers=headers)
    assert res.status_code == 404


def test_reject_inactive_material():
    headers, _company_id, material_id, other_material_id = _full_setup()
    stock = _create_stock(headers, material_id)
    assert client.delete(f"/materials/{other_material_id}", headers=headers).status_code == 200  # soft-delete

    res = client.put(f"/stock/{stock['id']}", json={"material_id": other_material_id}, headers=headers)
    assert res.status_code == 404

    res = client.get(f"/stock/{stock['id']}", headers=headers)
    assert res.json()["material_id"] == material_id


# ---------- carrera: AVAILABLE -> RESERVED entre la lectura y el UPDATE ----------


def test_race_available_to_reserved_blocks_material_change(monkeypatch):
    """
    Simula que otra request gana la carrera y reserva la chapa justo
    después de que update_stock_sheet la leyó como AVAILABLE, pero antes
    de que su propio UPDATE condicional se ejecute. El guard
    (WHERE status='AVAILABLE') debe detectarlo y no modificar nada.
    """
    import app.api.v1.routes_stock as routes_stock

    headers, _company_id, material_id, other_material_id = _full_setup()
    piece_id = _create_piece_with_dxf(headers, material_id, 100, 50)
    stock = _create_stock(headers, material_id)
    client_id = _create_client_record(headers)
    quotation_id = _create_quotation(headers, client_id)
    _advance_to_accepted(headers, quotation_id)

    real_get_active_material = routes_stock._get_active_material

    def _reserve_then_check(db, mid, company_id):
        result = real_get_active_material(db, mid, company_id)
        # Simula la reserva ganando la carrera, en una sesión aparte --
        # commitea de verdad, como haría un segundo request real.
        other_db = SessionLocal()
        try:
            other_stock = other_db.query(StockSheet).filter(StockSheet.id == stock["id"]).first()
            other_stock.status = "RESERVED"
            other_db.commit()
        finally:
            other_db.close()
        return result

    monkeypatch.setattr(routes_stock, "_get_active_material", _reserve_then_check)

    res = client.put(f"/stock/{stock['id']}", json={"material_id": other_material_id}, headers=headers)
    assert res.status_code == 409

    res = client.get(f"/stock/{stock['id']}", headers=headers)
    data = res.json()
    assert data["material_id"] == material_id  # no cambió pese a la carrera
    assert data["status"] == "RESERVED"

    engine.dispose()  # misma precaución que en test_recalculate_piece_geometry.py (Windows + segunda sesión)


# ---------- efectos colaterales: solo material_id cambia ----------


def test_material_change_does_not_touch_other_fields():
    headers, _company_id, material_id, other_material_id = _full_setup()
    stock = _create_stock(headers, material_id, width_mm=321, height_mm=654)
    before = client.get(f"/stock/{stock['id']}", headers=headers).json()

    res = client.put(f"/stock/{stock['id']}", json={"material_id": other_material_id}, headers=headers)
    assert res.status_code == 200
    after = res.json()

    assert after["material_id"] == other_material_id  # esto sí cambió
    for field in (
        "id", "company_id", "code", "stock_type", "status",
        "original_width_mm", "original_height_mm", "original_area_mm2", "remaining_area_mm2",
        "geometry", "source_sheet_id", "source_quotation_id", "created_at",
    ):
        assert after[field] == before[field], f"{field} cambió inesperadamente"

    # se logueó un único movimiento ADJUSTED, nada más
    db = SessionLocal()
    movements = db.query(StockMovement).filter(StockMovement.stock_sheet_id == stock["id"]).all()
    db.close()
    types = [m.movement_type for m in movements]
    assert types == ["CREATED", "ADJUSTED"]
    assert movements[-1].details == {"material_id": other_material_id}
