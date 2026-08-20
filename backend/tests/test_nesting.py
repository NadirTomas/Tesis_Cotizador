from pathlib import Path

from fastapi.testclient import TestClient

from app.db.init_db import init_db
from app.db.session import engine
from app.main import app

client = TestClient(app)


def _rect_dxf(w: float, h: float) -> str:
    return f"""0
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


def _create_material(headers, name="Acero"):
    res = client.post(
        "/materials",
        json={"name": name, "thickness_mm": 3, "sheet_width_mm": 1500, "sheet_height_mm": 3000, "sheet_cost_ars": 85000},
        headers=headers,
    )
    return res.json()["id"]


def _create_piece(headers, material_id, w, h, name="Pieza"):
    res = client.post("/pieces", json={"name": name, "material_id": material_id}, headers=headers)
    piece_id = res.json()["id"]
    client.post(
        f"/pieces/{piece_id}/upload-dxf",
        files={"file": (f"{name}.dxf", _rect_dxf(w, h).encode("utf-8"), "application/dxf")},
        headers=headers,
    )
    return piece_id


def _rects_overlap(a, b) -> bool:
    return not (
        a["x"] + a["width_mm"] <= b["x"] + 1e-6
        or b["x"] + b["width_mm"] <= a["x"] + 1e-6
        or a["y"] + a["height_mm"] <= b["y"] + 1e-6
        or b["y"] + b["height_mm"] <= a["y"] + 1e-6
    )


def test_multi_piece_packing_has_no_overlaps():
    headers = _setup_owner()
    material_id = _create_material(headers)
    piece_a = _create_piece(headers, material_id, 100, 50, "PiezaA")
    piece_b = _create_piece(headers, material_id, 200, 80, "PiezaB")

    res = client.post(
        "/nesting/calculate",
        json={
            "items": [
                {"piece_id": piece_a, "quantity": 6},
                {"piece_id": piece_b, "quantity": 3},
            ],
            "sheet_width_mm": 1500,
            "sheet_height_mm": 3000,
            "margin_mm": 5,
        },
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total_pieces_placed"] == 9

    for sheet in data["sheets"]:
        placements = sheet["placements"]
        for i in range(len(placements)):
            for j in range(i + 1, len(placements)):
                assert not _rects_overlap(placements[i], placements[j])


def test_pieces_overflow_to_second_sheet():
    headers = _setup_owner()
    material_id = _create_material(headers)
    piece_id = _create_piece(headers, material_id, 400, 300)

    res = client.post(
        "/nesting/calculate",
        json={"items": [{"piece_id": piece_id, "quantity": 50}], "sheet_width_mm": 500, "sheet_height_mm": 500, "margin_mm": 0},
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total_sheets"] > 1
    assert data["total_pieces_placed"] == 50


def test_rotation_allows_piece_that_would_not_fit_otherwise():
    headers = _setup_owner()
    material_id = _create_material(headers)
    piece_id = _create_piece(headers, material_id, 90, 40)

    res_no_rotation = client.post(
        "/nesting/calculate",
        json={
            "items": [{"piece_id": piece_id, "quantity": 1}],
            "sheet_width_mm": 50,
            "sheet_height_mm": 100,
            "margin_mm": 0,
            "allow_rotation": False,
        },
        headers=headers,
    )
    assert res_no_rotation.json()["total_pieces_placed"] == 0

    res_rotation = client.post(
        "/nesting/calculate",
        json={
            "items": [{"piece_id": piece_id, "quantity": 1}],
            "sheet_width_mm": 50,
            "sheet_height_mm": 100,
            "margin_mm": 0,
            "allow_rotation": True,
        },
        headers=headers,
    )
    data = res_rotation.json()
    assert data["total_pieces_placed"] == 1
    assert data["sheets"][0]["placements"][0]["rotated"] is True


def test_mixed_materials_rejected():
    headers = _setup_owner()
    material_a = _create_material(headers, "Acero")
    material_b = _create_material(headers, "Inoxidable")
    piece_a = _create_piece(headers, material_a, 100, 50)
    piece_b = _create_piece(headers, material_b, 100, 50)

    res = client.post(
        "/nesting/calculate",
        json={
            "items": [{"piece_id": piece_a, "quantity": 1}, {"piece_id": piece_b, "quantity": 1}],
            "sheet_width_mm": 1500,
            "sheet_height_mm": 3000,
        },
        headers=headers,
    )
    assert res.status_code == 400


def test_piece_from_other_company_rejected():
    headers_a = _setup_owner()
    material_id = _create_material(headers_a)
    piece_id = _create_piece(headers_a, material_id, 100, 50)

    res = client.post("/auth/register", json={"email": "other@test.com", "password": "Password1!"})
    token_b = res.json()["access_token"]
    res = client.post(
        "/companies", json={"company_name": "Otra Empresa"}, headers={"Authorization": f"Bearer {token_b}"}
    )
    headers_b = {"Authorization": f"Bearer {token_b}", "X-Company-Id": str(res.json()["id"])}

    res = client.post(
        "/nesting/calculate",
        json={"items": [{"piece_id": piece_id, "quantity": 1}], "sheet_width_mm": 1500, "sheet_height_mm": 3000},
        headers=headers_b,
    )
    assert res.status_code == 404
