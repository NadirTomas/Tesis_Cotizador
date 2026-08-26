from pathlib import Path

from fastapi.testclient import TestClient
from shapely.geometry import Polygon

from app.db.init_db import init_db
from app.db.session import engine
from app.main import app
from app.services.stock_placement import find_placement

client = TestClient(app)


# ---------- Unit tests: find_placement (sin DB, sin HTTP) ----------


def _rect(w: float, h: float, x: float = 0.0, y: float = 0.0) -> Polygon:
    return Polygon([(x, y), (x + w, y), (x + w, y + h), (x, y + h)])


def test_piece_fits_in_larger_stock():
    placement = find_placement(_rect(100, 50), _rect(200, 200))
    assert placement is not None
    assert placement.rotation == 0


def test_piece_does_not_fit_in_smaller_stock():
    assert find_placement(_rect(100, 50), _rect(50, 50)) is None


def test_piece_fits_only_when_rotated_90():
    placement = find_placement(_rect(100, 50), _rect(60, 110))
    assert placement is not None
    assert placement.rotation == 90


def test_kerf_can_make_a_borderline_piece_stop_fitting():
    piece, stock = _rect(100, 50), _rect(105, 55)
    assert find_placement(piece, stock, kerf_mm=0) is not None
    assert find_placement(piece, stock, kerf_mm=6) is None


def test_piece_fits_inside_irregular_l_shape():
    l_shape = Polygon([(0, 0), (200, 0), (200, 100), (100, 100), (100, 200), (0, 200)])
    assert find_placement(_rect(90, 90), l_shape) is not None


def test_piece_rejected_outside_irregular_shape_even_if_bbox_fits():
    l_shape = Polygon([(0, 0), (200, 0), (200, 100), (100, 100), (100, 200), (0, 200)])
    # 150x150 entra en el bounding box de 200x200 de la L, pero no en su forma real
    assert find_placement(_rect(150, 150), l_shape) is None


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


def _create_material(headers, material_type="Acero al carbono", alloy="SAE 1010", thickness_mm=3.0, name="Acero"):
    res = client.post(
        "/materials",
        json={
            "name": name,
            "material_type": material_type,
            "alloy": alloy,
            "thickness_mm": thickness_mm,
            "sheet_width_mm": 1500,
            "sheet_height_mm": 3000,
            "sheet_cost_ars": 85000,
        },
        headers=headers,
    )
    assert res.status_code == 200
    return res.json()["id"]


def _create_machine_config(headers, material_id, kerf_mm=0.0, minimum_spacing_mm=0.0):
    res = client.post(
        "/machine-configs",
        json={
            "material_id": material_id,
            "cut_speed_mm_min": 3000,
            "machine_cost_per_hour_ars": 18000,
            "setup_time_min": 10,
            "kerf_mm": kerf_mm,
            "minimum_spacing_mm": minimum_spacing_mm,
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


def test_ignores_incompatible_material_type_alloy_and_thickness():
    _reset_db_file()
    init_db()
    headers, _ = _register_and_create_company("owner_filter@test.com", "Empresa Filter")

    target_material = _create_material(headers, "Acero al carbono", "SAE 1010", 3.0)
    _create_machine_config(headers, target_material)
    piece_id = _create_piece_with_dxf(headers, target_material, 100, 50)

    other_type = _create_material(headers, "Aluminio", "SAE 1010", 3.0, name="Aluminio")
    other_alloy = _create_material(headers, "Acero al carbono", "AISI 304", 3.0, name="Inox")
    other_thickness = _create_material(headers, "Acero al carbono", "SAE 1010", 5.0, name="Acero 5mm")
    for mat_id in (other_type, other_alloy, other_thickness):
        _create_stock(headers, mat_id, "FULL_SHEET", width_mm=500, height_mm=500)

    res = client.post(
        "/stock/recommendations", json={"piece_id": piece_id, "material_id": target_material}, headers=headers
    )
    assert res.status_code == 404  # ningún stock de otro tipo/calidad/espesor debería matchear

    _create_stock(headers, target_material, "FULL_SHEET", width_mm=500, height_mm=500)
    res = client.post(
        "/stock/recommendations", json={"piece_id": piece_id, "material_id": target_material}, headers=headers
    )
    assert res.status_code == 200


def test_never_recommends_stock_from_another_company():
    _reset_db_file()
    init_db()
    headers_a, _ = _register_and_create_company("owner_reca@test.com", "Empresa RecA")
    headers_b, _ = _register_and_create_company("owner_recb@test.com", "Empresa RecB")

    material_a = _create_material(headers_a)
    _create_machine_config(headers_a, material_a)
    piece_a = _create_piece_with_dxf(headers_a, material_a, 100, 50)

    material_b = _create_material(headers_b)
    _create_stock(headers_b, material_b, "FULL_SHEET", width_mm=500, height_mm=500)

    res = client.post(
        "/stock/recommendations", json={"piece_id": piece_a, "material_id": material_a}, headers=headers_a
    )
    assert res.status_code == 404  # nunca ve el stock de la empresa B


def test_prioritizes_remnant_over_full_sheet():
    _reset_db_file()
    init_db()
    headers, _ = _register_and_create_company("owner_prio@test.com", "Empresa Prioridad")
    material_id = _create_material(headers)
    _create_machine_config(headers, material_id)
    piece_id = _create_piece_with_dxf(headers, material_id, 100, 50)

    _create_stock(headers, material_id, "FULL_SHEET", width_mm=500, height_mm=500)
    remnant = _create_stock(headers, material_id, "REMNANT", width_mm=150, height_mm=150)

    res = client.post(
        "/stock/recommendations", json={"piece_id": piece_id, "material_id": material_id}, headers=headers
    )
    assert res.status_code == 200
    data = res.json()[0]
    assert data["stock_type"] == "REMNANT"
    assert data["stock_sheet_id"] == remnant["id"]


def test_finds_placement_inside_irregular_remnant():
    _reset_db_file()
    init_db()
    headers, _ = _register_and_create_company("owner_lshape@test.com", "Empresa LShape")
    material_id = _create_material(headers)
    _create_machine_config(headers, material_id)
    piece_id = _create_piece_with_dxf(headers, material_id, 90, 90)

    l_shape = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [200, 0], [200, 100], [100, 100], [100, 200], [0, 200], [0, 0]]],
    }
    _create_stock(headers, material_id, "REMNANT", geometry=l_shape)

    res = client.post(
        "/stock/recommendations", json={"piece_id": piece_id, "material_id": material_id}, headers=headers
    )
    assert res.status_code == 200


def test_rejects_piece_too_big_for_irregular_remnant_shape():
    _reset_db_file()
    init_db()
    headers, _ = _register_and_create_company("owner_lshape2@test.com", "Empresa LShape2")
    material_id = _create_material(headers)
    _create_machine_config(headers, material_id)
    piece_id = _create_piece_with_dxf(headers, material_id, 150, 150)

    l_shape = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [200, 0], [200, 100], [100, 100], [100, 200], [0, 200], [0, 0]]],
    }
    _create_stock(headers, material_id, "REMNANT", geometry=l_shape)

    res = client.post(
        "/stock/recommendations", json={"piece_id": piece_id, "material_id": material_id}, headers=headers
    )
    assert res.status_code == 404


def test_selects_the_best_scoring_candidate_among_alternatives():
    _reset_db_file()
    init_db()
    headers, _ = _register_and_create_company("owner_score@test.com", "Empresa Score")
    material_id = _create_material(headers)
    _create_machine_config(headers, material_id)
    piece_id = _create_piece_with_dxf(headers, material_id, 100, 50)  # area 5000 mm2

    well_fitted = _create_stock(headers, material_id, "REMNANT", width_mm=110, height_mm=60)
    _create_stock(headers, material_id, "REMNANT", width_mm=1000, height_mm=1000)

    res = client.post(
        "/stock/recommendations", json={"piece_id": piece_id, "material_id": material_id}, headers=headers
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 2  # las dos alternativas se devuelven, ordenadas
    assert data[0]["stock_sheet_id"] == well_fitted["id"]  # mejor aprovechamiento gana, no el más grande


def test_does_not_prefer_an_inefficient_remnant_over_a_well_fitted_full_sheet():
    # Auditoría del score anterior (0.6*utilización + 0.4*bonus retazo): un
    # retazo enorme y mal aprovechado podía ganarle a una chapa que ajustaba
    # mucho mejor, solo por el bonus fijo de ser retazo. Con la jerarquía
    # actual (retazo "adecuado" >= 15% de aprovechamiento primero, después
    # mejor aprovechamiento entre todo lo demás) la chapa bien ajustada debe
    # ganar.
    _reset_db_file()
    init_db()
    headers, _ = _register_and_create_company("owner_noineff@test.com", "Empresa NoIneficiente")
    material_id = _create_material(headers)
    _create_machine_config(headers, material_id)
    piece_id = _create_piece_with_dxf(headers, material_id, 100, 50)  # area 5000 mm2

    huge_remnant = _create_stock(headers, material_id, "REMNANT", width_mm=1000, height_mm=1000)  # util. 0.5%
    good_sheet = _create_stock(headers, material_id, "FULL_SHEET", width_mm=110, height_mm=100)  # util. ~45%

    res = client.post(
        "/stock/recommendations", json={"piece_id": piece_id, "material_id": material_id}, headers=headers
    )
    assert res.status_code == 200
    data = res.json()
    assert data[0]["stock_sheet_id"] == good_sheet["id"]
    assert data[-1]["stock_sheet_id"] == huge_remnant["id"]
