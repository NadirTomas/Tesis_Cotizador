from pathlib import Path

from fastapi.testclient import TestClient

from app.db.init_db import init_db
from app.db.session import SessionLocal, engine
from app.main import app
from app.models.material import Material

client = TestClient(app)


def _reset_db_file() -> None:
    engine.dispose()
    db_path = Path("cotizalaser.db")
    if db_path.exists():
        db_path.unlink()


def _headers():
    _reset_db_file()
    init_db()
    res = client.post("/auth/register", json={"email": "owner@test.com", "password": "Password1!"})
    token = res.json()["access_token"]
    res = client.post("/companies", json={"company_name": "Empresa Test"}, headers={"Authorization": f"Bearer {token}"})
    company_id = res.json()["id"]
    return {"Authorization": f"Bearer {token}", "X-Company-Id": str(company_id)}


_VALID_MATERIAL = {
    "name": "Acero",
    "material_type": "Acero al carbono",
    "thickness_mm": 3,
    "sheet_width_mm": 1500,
    "sheet_height_mm": 3000,
    "sheet_cost_ars": 85000,
}


def test_material_with_legitimate_technical_names_is_accepted():
    headers = _headers()
    for name, alloy in [
        ("AISI 304", "AISI 304"),
        ("SAE 1010", "SAE 1010"),
        ('Aluminio 6061-T6', "6061-T6"),
        ('Acero 1/8"', None),
    ]:
        payload = {**_VALID_MATERIAL, "name": name, "material_type": "Acero", "alloy": alloy}
        res = client.post("/materials", json=payload, headers=headers)
        assert res.status_code == 200, (name, res.text)


def test_material_name_cannot_be_blank():
    headers = _headers()
    res = client.post("/materials", json={**_VALID_MATERIAL, "name": "   "}, headers=headers)
    assert res.status_code == 422


def test_material_type_cannot_be_blank():
    headers = _headers()
    res = client.post("/materials", json={**_VALID_MATERIAL, "material_type": "   "}, headers=headers)
    assert res.status_code == 422


def test_material_name_too_long_is_rejected():
    headers = _headers()
    res = client.post("/materials", json={**_VALID_MATERIAL, "name": "A" * 201}, headers=headers)
    assert res.status_code == 422


def test_material_thickness_must_be_positive():
    headers = _headers()
    for bad_value in [0, -1, -0.001]:
        res = client.post("/materials", json={**_VALID_MATERIAL, "thickness_mm": bad_value}, headers=headers)
        assert res.status_code == 422, bad_value


def test_material_sheet_dimensions_must_be_positive():
    headers = _headers()
    res = client.post("/materials", json={**_VALID_MATERIAL, "sheet_width_mm": 0}, headers=headers)
    assert res.status_code == 422
    res = client.post("/materials", json={**_VALID_MATERIAL, "sheet_height_mm": -100}, headers=headers)
    assert res.status_code == 422


def test_material_sheet_cost_can_be_zero():
    """Caso real usado en test_quotation_calculator.py: material en 0 para
    aislar el costo de máquina. 0 no es un bug, es un valor de negocio válido."""
    headers = _headers()
    res = client.post("/materials", json={**_VALID_MATERIAL, "sheet_cost_ars": 0}, headers=headers)
    assert res.status_code == 200


def test_material_sheet_cost_cannot_be_negative():
    headers = _headers()
    res = client.post("/materials", json={**_VALID_MATERIAL, "sheet_cost_ars": -1}, headers=headers)
    assert res.status_code == 422


def test_material_thickness_absurdly_large_is_rejected():
    headers = _headers()
    res = client.post("/materials", json={**_VALID_MATERIAL, "thickness_mm": 999999}, headers=headers)
    assert res.status_code == 422


def test_material_update_rejects_blank_name():
    headers = _headers()
    res = client.post("/materials", json=_VALID_MATERIAL, headers=headers)
    material_id = res.json()["id"]

    res = client.put(f"/materials/{material_id}", json={"name": "   "}, headers=headers)
    assert res.status_code == 422


def test_material_update_rejects_negative_cost():
    headers = _headers()
    res = client.post("/materials", json=_VALID_MATERIAL, headers=headers)
    material_id = res.json()["id"]

    res = client.put(f"/materials/{material_id}", json={"sheet_cost_ars": -50}, headers=headers)
    assert res.status_code == 422


def test_reading_a_pre_existing_material_out_of_the_new_bounds_never_500s():
    """Regresión de incidente real en producción (2026-09-16): MaterialRead
    heredaba los mismos field_validators de MaterialCreate (via
    MaterialBase), así que una fila YA guardada con valores fuera de los
    límites nuevos (cargada antes de que existiera esta validación)
    rompía GET /materials con un 500 (ResponseValidationError) en vez de
    simplemente mostrarse. Los límites deben regir solo la escritura,
    nunca la lectura."""
    headers = _headers()
    res = client.post("/materials", json=_VALID_MATERIAL, headers=headers)
    material_id = res.json()["id"]

    db = SessionLocal()
    db.query(Material).filter(Material.id == material_id).update(
        {
            "thickness_mm": 4444444444.0,
            "sheet_width_mm": 444444444444.0,
            "sheet_height_mm": 44444444444444.0,
            "sheet_cost_ars": 4444444444444444.0,
        }
    )
    db.commit()
    db.close()

    res = client.get("/materials", headers=headers)
    assert res.status_code == 200
    assert res.json()[0]["thickness_mm"] == 4444444444.0

    res = client.get(f"/materials/{material_id}", headers=headers)
    assert res.status_code == 200
    assert res.json()["sheet_cost_ars"] == 4444444444444444.0
