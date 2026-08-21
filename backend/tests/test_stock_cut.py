from pathlib import Path

from fastapi.testclient import TestClient
from shapely.geometry import Polygon
from sqlalchemy import text

from app.db.init_db import init_db
from app.db.session import engine
from app.main import app
from app.services.stock_cut import compute_remnants

client = TestClient(app)


def _rect(w: float, h: float, x: float = 0.0, y: float = 0.0) -> Polygon:
    return Polygon([(x, y), (x + w, y), (x + w, y + h), (x, y + h)])


# ---------- Unit tests: compute_remnants (sin DB, sin HTTP) ----------


def test_single_remnant_when_cutting_a_corner():
    stock = _rect(200, 200)
    occupied = _rect(100, 50)  # esquina inferior izquierda
    remnants = compute_remnants(stock, occupied, minimum_area_mm2=2500)
    assert len(remnants) == 1
    assert remnants[0].area_mm2 == 200 * 200 - 100 * 50


def test_multiple_remnants_when_cut_splits_stock_in_two():
    stock = _rect(300, 100)
    occupied = _rect(50, 100, x=125)  # franja vertical al medio, separa izquierda/derecha
    remnants = compute_remnants(stock, occupied, minimum_area_mm2=2500)
    assert len(remnants) == 2
    areas = sorted(r.area_mm2 for r in remnants)
    assert areas == [125 * 100, 125 * 100]


def test_fragment_below_minimum_is_discarded():
    stock = _rect(200, 200)
    occupied = _rect(190, 190)  # deja un borde angosto de muy poca área
    remnants = compute_remnants(stock, occupied, minimum_area_mm2=1_000_000)
    assert remnants == []


def test_nothing_left_when_occupied_covers_entire_stock():
    stock = _rect(100, 50)
    occupied = _rect(100, 50)
    remnants = compute_remnants(stock, occupied, minimum_area_mm2=1)
    assert remnants == []


def test_minimum_width_height_also_filter_fragments():
    stock = _rect(300, 100)
    occupied = _rect(295, 100)  # deja una tira angosta de 5x100 = 500mm2, área ok pero muy angosta
    remnants = compute_remnants(stock, occupied, minimum_area_mm2=100, minimum_width_mm=20)
    assert remnants == []


# ---------- Integration tests: endpoint completo (DB + HTTP) ----------


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


def _create_material(headers, thickness_mm=3.0):
    res = client.post(
        "/materials",
        json={
            "name": "Acero", "material_type": "Acero al carbono", "alloy": "SAE 1010", "thickness_mm": thickness_mm,
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


def _create_piece_with_dxf(headers, material_id, w, h):
    res = client.post("/pieces", json={"name": "Pieza", "material_id": material_id}, headers=headers)
    piece_id = res.json()["id"]
    files = {"file": ("pieza.dxf", _rect_dxf(w, h).encode("utf-8"), "application/dxf")}
    up = client.post(f"/pieces/{piece_id}/upload-dxf", files=files, headers=headers)
    assert up.status_code == 200
    return piece_id


def _create_stock(headers, material_id, width_mm, height_mm):
    res = client.post(
        "/stock", json={"material_id": material_id, "stock_type": "FULL_SHEET", "width_mm": width_mm, "height_mm": height_mm},
        headers=headers,
    )
    assert res.status_code == 200
    return res.json()


def _full_flow_to_reserved(stock_w=200, stock_h=200, piece_w=100, piece_h=50, min_remnant_area=None):
    _reset_db_file()
    init_db()
    headers, company_id = _register_and_create_company("owner_cut@test.com", "Empresa Cut")
    if min_remnant_area is not None:
        client.put(f"/companies/{company_id}", json={"minimum_remnant_area_mm2": min_remnant_area}, headers=headers)
    material_id = _create_material(headers)
    _create_machine_config(headers, material_id)
    piece_id = _create_piece_with_dxf(headers, material_id, piece_w, piece_h)
    stock = _create_stock(headers, material_id, stock_w, stock_h)

    res = client.post("/clients", json={"name": "Cliente"}, headers=headers)
    client_id = res.json()["id"]
    res = client.post("/quotations", json={"client_id": client_id, "issue_date": "2026-08-26T00:00:00"}, headers=headers)
    quotation_id = res.json()["id"]
    client.patch(f"/quotations/{quotation_id}/status", json={"status": "sent"}, headers=headers)
    client.patch(f"/quotations/{quotation_id}/status", json={"status": "accepted"}, headers=headers)

    res = client.post(
        f"/stock/{stock['id']}/reserve",
        json={"piece_id": piece_id, "material_id": material_id, "quotation_id": quotation_id},
        headers=headers,
    )
    assert res.status_code == 200
    reservation_id = res.json()["id"]
    return headers, stock, quotation_id, reservation_id


def test_confirm_cut_consumes_stock_and_creates_a_remnant():
    headers, stock, quotation_id, reservation_id = _full_flow_to_reserved()

    res = client.post(f"/stock/reservations/{reservation_id}/confirm-cut", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "CONSUMED"
    assert len(data["remnants"]) == 1
    remnant = data["remnants"][0]
    assert remnant["code"].startswith("R-")

    res = client.get(f"/stock/{stock['id']}", headers=headers)
    assert res.json()["status"] == "CONSUMED"

    res = client.get(f"/stock/{remnant['stock_sheet_id']}", headers=headers)
    remnant_data = res.json()
    assert remnant_data["source_sheet_id"] == stock["id"]
    assert remnant_data["source_quotation_id"] == quotation_id
    assert remnant_data["status"] == "AVAILABLE"


def test_confirm_cut_discards_fragments_below_configured_minimum():
    headers, stock, quotation_id, reservation_id = _full_flow_to_reserved(min_remnant_area=1_000_000)

    res = client.post(f"/stock/reservations/{reservation_id}/confirm-cut", headers=headers)
    assert res.status_code == 200
    assert res.json()["remnants"] == []

    res = client.get("/stock", params={"stock_type": "REMNANT"}, headers=headers)
    assert res.json() == []


def test_confirm_cut_is_idempotent():
    headers, stock, quotation_id, reservation_id = _full_flow_to_reserved()

    res1 = client.post(f"/stock/reservations/{reservation_id}/confirm-cut", headers=headers)
    res2 = client.post(f"/stock/reservations/{reservation_id}/confirm-cut", headers=headers)
    assert res1.status_code == 200
    assert res2.status_code == 200
    assert res1.json() == res2.json()

    res = client.get("/stock", params={"stock_type": "REMNANT"}, headers=headers)
    assert len(res.json()) == 1  # no se duplicó el retazo en la segunda confirmación


def test_full_integration_flow_quotation_to_new_stock():
    headers, stock, quotation_id, reservation_id = _full_flow_to_reserved()

    res = client.post(f"/stock/reservations/{reservation_id}/confirm-cut", headers=headers)
    remnant_id = res.json()["remnants"][0]["stock_sheet_id"]

    res = client.get(f"/stock/{stock['id']}/movements", headers=headers)
    movement_types = [m["movement_type"] for m in res.json()]
    assert movement_types == ["CREATED", "RESERVED", "CONSUMED"]

    res = client.get(f"/stock/{remnant_id}/movements", headers=headers)
    assert [m["movement_type"] for m in res.json()] == ["REMNANT_CREATED"]

    res = client.get("/stock", params={"status": "AVAILABLE", "stock_type": "REMNANT"}, headers=headers)
    assert any(s["id"] == remnant_id for s in res.json())


def test_confirm_cut_via_http_creates_two_remnants_when_cut_splits_the_stock():
    # find_placement (bottom-left) siempre ubica la pieza pegada a un borde,
    # nunca partiendo la chapa al medio por sí solo — para probar el camino
    # HTTP real de múltiples retazos (no solo compute_remnants como función
    # pura) se reserva normalmente y se reescribe la posición ya verificada
    # de la reserva a una franja central, tal como quedaría si el algoritmo
    # de colocación evolucionara a futuro. Mismas dimensiones que el test
    # unitario `test_multiple_remnants_when_cut_splits_stock_in_two`.
    headers, stock, quotation_id, reservation_id = _full_flow_to_reserved(
        stock_w=300, stock_h=100, piece_w=50, piece_h=100
    )

    with engine.connect() as conn:
        conn.execute(
            text("UPDATE stock_reservations SET x = 125, y = 0, rotation = 0 WHERE id = :id"),
            {"id": reservation_id},
        )
        conn.commit()

    res = client.post(f"/stock/reservations/{reservation_id}/confirm-cut", headers=headers)
    assert res.status_code == 200
    remnants = res.json()["remnants"]
    assert len(remnants) == 2
    areas = sorted(r["area_mm2"] for r in remnants)
    assert areas == [125 * 100, 125 * 100]

    res = client.get(f"/stock/{stock['id']}", headers=headers)
    assert res.json()["remaining_area_mm2"] == 0  # se limpia al consumir, ya no queda un valor obsoleto
