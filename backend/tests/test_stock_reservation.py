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


def _create_machine_config(headers, material_id, kerf_mm=0.0, minimum_spacing_mm=0.0):
    res = client.post(
        "/machine-configs",
        json={
            "material_id": material_id, "cut_speed_mm_min": 3000, "machine_cost_per_hour_ars": 18000,
            "setup_time_min": 10, "kerf_mm": kerf_mm, "minimum_spacing_mm": minimum_spacing_mm,
        },
        headers=headers,
    )
    assert res.status_code == 200
    return res.json()["id"]


def _rect_dxf(w: float, h: float) -> str:
    return f"""0
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
{w}
20
0
10
{w}
20
{h}
10
0
20
{h}
0
ENDSEC
0
EOF
"""


def _create_piece_with_dxf(headers, material_id, w, h, name="Pieza"):
    files = {"file": (f"{name}.dxf", _rect_dxf(w, h).encode("utf-8"), "application/dxf")}
    res = client.post("/pieces", data={"name": name, "material_id": material_id}, files=files, headers=headers)
    assert res.status_code == 200
    return res.json()["id"]


def _create_stock(headers, material_id, stock_type, width_mm=None, height_mm=None, geometry=None):
    payload = {"material_id": material_id, "stock_type": stock_type}
    if geometry is not None:
        payload["geometry"] = geometry
    else:
        payload["width_mm"] = width_mm
        payload["height_mm"] = height_mm
    res = client.post("/stock", json=payload, headers=headers)
    assert res.status_code == 200
    return res.json()


def _create_client(headers, name="Cliente"):
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


def _login(email: str, password: str = "Password1!") -> str:
    res = client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


def _add_employee(owner_headers, company_id, email="employee_res@test.com"):
    res = client.post(
        f"/companies/{company_id}/members",
        json={"email": email, "password": "Password1!", "role": "employee"},
        headers=owner_headers,
    )
    assert res.status_code == 201
    token = _login(email)
    return {"Authorization": f"Bearer {token}", "X-Company-Id": str(company_id)}


def _create_quotation_item(headers, quotation_id, piece_id, material_id, quantity=1):
    res = client.post(
        "/quotation-items",
        json={"quotation_id": quotation_id, "piece_id": piece_id, "material_id": material_id, "quantity": quantity},
        headers=headers,
    )
    assert res.status_code == 200
    return res.json()["id"]


def _full_setup(email="owner@test.com", company_name="Empresa Reserva", piece_w=100, piece_h=50, stock_w=200, stock_h=200):
    _reset_db_file()
    init_db()
    headers, _ = _register_and_create_company(email, company_name)
    material_id = _create_material(headers)
    _create_machine_config(headers, material_id)
    piece_id = _create_piece_with_dxf(headers, material_id, piece_w, piece_h)
    stock = _create_stock(headers, material_id, "FULL_SHEET", width_mm=stock_w, height_mm=stock_h)
    client_id = _create_client(headers)
    quotation_id = _create_quotation(headers, client_id)
    return headers, material_id, piece_id, stock, quotation_id


def test_reserve_available_stock_succeeds_once_accepted():
    headers, material_id, piece_id, stock, quotation_id = _full_setup()
    _advance_to_accepted(headers, quotation_id)

    res = client.post(
        f"/stock/{stock['id']}/reserve",
        json={"piece_id": piece_id, "material_id": material_id, "quotation_id": quotation_id},
        headers=headers,
    )
    assert res.status_code == 200
    reservation = res.json()
    assert reservation["status"] == "ACTIVE"
    assert reservation["stock_sheet_id"] == stock["id"]

    res = client.get(f"/stock/{stock['id']}", headers=headers)
    assert res.json()["status"] == "RESERVED"


def test_reserve_requires_accepted_quotation():
    headers, material_id, piece_id, stock, quotation_id = _full_setup()
    # Todavía en "draft" — nunca se avanzó el estado.
    res = client.post(
        f"/stock/{stock['id']}/reserve",
        json={"piece_id": piece_id, "material_id": material_id, "quotation_id": quotation_id},
        headers=headers,
    )
    assert res.status_code == 400


def test_cannot_reserve_stock_that_is_already_reserved():
    headers, material_id, piece_id, stock, quotation_id = _full_setup()
    _advance_to_accepted(headers, quotation_id)
    res = client.post(
        f"/stock/{stock['id']}/reserve",
        json={"piece_id": piece_id, "material_id": material_id, "quotation_id": quotation_id},
        headers=headers,
    )
    assert res.status_code == 200

    # Segunda cotización intentando usar el mismo stock — mismo camino que
    # tomaría una segunda request concurrente: el UPDATE condicional ya
    # encuentra el stock fuera de AVAILABLE y rechaza, sin importar el orden.
    client_id_2 = _create_client(headers, "Cliente 2")
    quotation_id_2 = _create_quotation(headers, client_id_2)
    _advance_to_accepted(headers, quotation_id_2)
    res = client.post(
        f"/stock/{stock['id']}/reserve",
        json={"piece_id": piece_id, "material_id": material_id, "quotation_id": quotation_id_2},
        headers=headers,
    )
    assert res.status_code == 409


def test_cancelling_accepted_quotation_releases_reservation():
    headers, material_id, piece_id, stock, quotation_id = _full_setup()
    _advance_to_accepted(headers, quotation_id)
    client.post(
        f"/stock/{stock['id']}/reserve",
        json={"piece_id": piece_id, "material_id": material_id, "quotation_id": quotation_id},
        headers=headers,
    )

    res = client.patch(f"/quotations/{quotation_id}/status", json={"status": "cancelled"}, headers=headers)
    assert res.status_code == 200

    res = client.get(f"/stock/{stock['id']}", headers=headers)
    data = res.json()
    assert data["status"] == "AVAILABLE"
    assert data["geometry"] == stock["geometry"]  # la geometría no se toca al liberar


def test_manual_release_endpoint():
    headers, material_id, piece_id, stock, quotation_id = _full_setup()
    _advance_to_accepted(headers, quotation_id)
    res = client.post(
        f"/stock/{stock['id']}/reserve",
        json={"piece_id": piece_id, "material_id": material_id, "quotation_id": quotation_id},
        headers=headers,
    )
    reservation_id = res.json()["id"]

    res = client.post(f"/stock/reservations/{reservation_id}/release", headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "RELEASED"

    res = client.get(f"/stock/{stock['id']}", headers=headers)
    assert res.json()["status"] == "AVAILABLE"

    # Liberar de nuevo ya no es válido.
    res = client.post(f"/stock/reservations/{reservation_id}/release", headers=headers)
    assert res.status_code == 400


def test_other_company_cannot_reserve_or_release_stock():
    headers_a, material_id, piece_id, stock, quotation_id = _full_setup("owner_sec_a@test.com", "Empresa SecA")
    headers_b, _ = _register_and_create_company("owner_sec_b@test.com", "Empresa SecB")

    res = client.post(
        f"/stock/{stock['id']}/reserve",
        json={"piece_id": piece_id, "material_id": material_id, "quotation_id": quotation_id},
        headers=headers_b,
    )
    assert res.status_code == 404

    _advance_to_accepted(headers_a, quotation_id)
    res = client.post(
        f"/stock/{stock['id']}/reserve",
        json={"piece_id": piece_id, "material_id": material_id, "quotation_id": quotation_id},
        headers=headers_a,
    )
    reservation_id = res.json()["id"]

    res = client.post(f"/stock/reservations/{reservation_id}/release", headers=headers_b)
    assert res.status_code == 404


def test_movements_logged_for_reserve_and_release():
    headers, material_id, piece_id, stock, quotation_id = _full_setup()
    _advance_to_accepted(headers, quotation_id)
    res = client.post(
        f"/stock/{stock['id']}/reserve",
        json={"piece_id": piece_id, "material_id": material_id, "quotation_id": quotation_id},
        headers=headers,
    )
    reservation_id = res.json()["id"]
    client.post(f"/stock/reservations/{reservation_id}/release", headers=headers)

    res = client.get(f"/stock/{stock['id']}/movements", headers=headers)
    assert res.status_code == 200
    movement_types = [m["movement_type"] for m in res.json()]
    assert movement_types == ["CREATED", "RESERVED", "RELEASED"]  # orden cronológico


def test_employee_can_reserve_but_not_view_movements():
    headers, material_id, piece_id, stock, quotation_id = _full_setup()
    employee_headers = _add_employee(headers, stock["company_id"])
    _advance_to_accepted(headers, quotation_id)

    # Reservar/liberar es un uso del día a día, permitido a EMPLOYEE.
    res = client.post(
        f"/stock/{stock['id']}/reserve",
        json={"piece_id": piece_id, "material_id": material_id, "quotation_id": quotation_id},
        headers=employee_headers,
    )
    assert res.status_code == 200

    # El historial de movimientos es administración de inventario, exclusiva del OWNER.
    res = client.get(f"/stock/{stock['id']}/movements", headers=employee_headers)
    assert res.status_code == 403


def test_deleting_quotation_item_releases_its_active_reservation():
    headers, material_id, piece_id, stock, quotation_id = _full_setup()
    item_id = _create_quotation_item(headers, quotation_id, piece_id, material_id)
    _advance_to_accepted(headers, quotation_id)

    res = client.post(
        f"/stock/{stock['id']}/reserve",
        json={"piece_id": piece_id, "material_id": material_id, "quotation_id": quotation_id, "quotation_item_id": item_id},
        headers=headers,
    )
    assert res.status_code == 200
    reservation_id = res.json()["id"]

    res = client.delete(f"/quotation-items/{item_id}", headers=headers)
    assert res.status_code == 204

    res = client.get(f"/stock/{stock['id']}", headers=headers)
    assert res.json()["status"] == "AVAILABLE"  # la reserva se liberó al borrar el ítem, no quedó huérfana

    res = client.post(f"/stock/reservations/{reservation_id}/release", headers=headers)
    assert res.status_code == 400  # ya estaba RELEASED, no ACTIVE


def test_list_reservations_by_quotation_includes_stock_code_and_is_company_scoped():
    headers, material_id, piece_id, stock, quotation_id = _full_setup()
    headers_b, _ = _register_and_create_company("owner_reslist_b@test.com", "Empresa ResListB")
    _advance_to_accepted(headers, quotation_id)
    res = client.post(
        f"/stock/{stock['id']}/reserve",
        json={"piece_id": piece_id, "material_id": material_id, "quotation_id": quotation_id},
        headers=headers,
    )
    reservation_id = res.json()["id"]

    res = client.get("/stock/reservations", params={"quotation_id": quotation_id}, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["id"] == reservation_id
    assert data[0]["stock_code"] == stock["code"]

    # La empresa B no ve reservas de la empresa A aunque conozca el quotation_id.
    res = client.get("/stock/reservations", params={"quotation_id": quotation_id}, headers=headers_b)
    assert res.json() == []
