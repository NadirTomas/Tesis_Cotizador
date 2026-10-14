"""Regresión Bug 2: la descripción de una pieza debe persistirse, devolverse
en todos los endpoints de lectura, sobrevivir a la edición de otros campos y
poder borrarse explícitamente."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.db.init_db import init_db
from app.db.session import engine
from app.main import app

client = TestClient(app)

_DXF = (
    "0\nSECTION\n2\nENTITIES\n"
    "0\nLWPOLYLINE\n8\n0\n90\n4\n70\n1\n10\n0\n20\n0\n10\n10\n20\n0\n10\n10\n20\n10\n10\n0\n20\n10\n"
    "0\nENDSEC\n0\nEOF\n"
).encode()


def _headers():
    engine.dispose()
    db_path = Path("cotizalaser.db")
    if db_path.exists():
        db_path.unlink()
    init_db()
    res = client.post("/auth/register", json={"email": "owner@test.com", "password": "Password1!"})
    token = res.json()["access_token"]
    res = client.post("/companies", json={"company_name": "Empresa Test"}, headers={"Authorization": f"Bearer {token}"})
    return {"Authorization": f"Bearer {token}", "X-Company-Id": str(res.json()["id"])}


def _create_piece(headers, description="Soporte con 4 agujeros"):
    data = {"name": "Pieza"}
    if description is not None:
        data["description"] = description
    res = client.post("/pieces", data=data, files={"file": ("p.dxf", _DXF, "application/dxf")}, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def test_description_is_returned_on_create_get_and_list():
    headers = _headers()
    created = _create_piece(headers)
    assert created["description"] == "Soporte con 4 agujeros"

    got = client.get(f"/pieces/{created['id']}", headers=headers).json()
    assert got["description"] == "Soporte con 4 agujeros"

    listed = client.get("/pieces", headers=headers).json()
    assert listed[0]["description"] == "Soporte con 4 agujeros"


def test_editing_other_fields_does_not_erase_description():
    headers = _headers()
    piece_id = _create_piece(headers)["id"]

    res = client.put(f"/pieces/{piece_id}", json={"name": "Nuevo nombre"}, headers=headers)
    assert res.status_code == 200
    assert res.json()["description"] == "Soporte con 4 agujeros"
    assert client.get(f"/pieces/{piece_id}", headers=headers).json()["description"] == "Soporte con 4 agujeros"


def test_description_can_be_updated_and_explicitly_cleared():
    headers = _headers()
    piece_id = _create_piece(headers)["id"]

    res = client.put(f"/pieces/{piece_id}", json={"description": "Otra"}, headers=headers)
    assert res.json()["description"] == "Otra"

    res = client.put(f"/pieces/{piece_id}", json={"description": None}, headers=headers)
    assert res.status_code == 200
    assert res.json()["description"] is None


def test_replacing_the_dxf_keeps_description():
    headers = _headers()
    piece_id = _create_piece(headers)["id"]
    res = client.post(f"/pieces/{piece_id}/upload-dxf", files={"file": ("q.dxf", _DXF, "application/dxf")}, headers=headers)
    assert res.status_code == 200
    assert res.json()["description"] == "Soporte con 4 agujeros"
