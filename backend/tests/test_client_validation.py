from pathlib import Path

from fastapi.testclient import TestClient

from app.db.init_db import init_db
from app.db.session import SessionLocal, engine
from app.main import app
from app.models.client import Client

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


def test_client_with_only_required_fields_is_created():
    headers = _headers()
    res = client.post("/clients", json={"name": "Metalúrgica 3H S.R.L."}, headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["cuit_cuil"] is None
    assert body["phone"] is None
    assert body["email"] is None


def test_client_name_cannot_be_blank():
    headers = _headers()
    res = client.post("/clients", json={"name": "   "}, headers=headers)
    assert res.status_code == 422


def test_client_name_allows_commercial_names_with_numbers_and_punctuation():
    headers = _headers()
    res = client.post("/clients", json={"name": 'Metalúrgica 3H S.R.L. - Planta N°2'}, headers=headers)
    assert res.status_code == 200


def test_client_name_rejects_purely_numeric_values():
    headers = _headers()
    for bad_name in ["123456", "  42  ", "12-34", "1 2 3", "00.00", "#123"]:
        res = client.post("/clients", json={"name": bad_name}, headers=headers)
        assert res.status_code == 422, bad_name
        assert "letra" in res.json()["detail"][0]["msg"]


def test_client_name_accepts_valid_names_with_numbers():
    headers = _headers()
    for good_name in ["Metalúrgica 24", "Taller 3D", "Empresa ABC S.R.L.", "Juan Pérez", "3M", "A1"]:
        res = client.post("/clients", json={"name": good_name}, headers=headers)
        assert res.status_code == 200, good_name


def test_client_update_rejects_purely_numeric_name():
    headers = _headers()
    res = client.post("/clients", json={"name": "Cliente"}, headers=headers)
    client_id = res.json()["id"]

    res = client.put(f"/clients/{client_id}", json={"name": "123456"}, headers=headers)
    assert res.status_code == 422

    res = client.put(f"/clients/{client_id}", json={"name": "Taller 3D"}, headers=headers)
    assert res.status_code == 200


def test_existing_numeric_named_client_stays_readable_and_other_fields_editable():
    """No se tocan registros históricos: un cliente ya guardado con nombre
    numérico se sigue leyendo (ClientRead sin validators) y se puede editar
    otro campo sin reenviar el nombre."""
    headers = _headers()
    res = client.post("/clients", json={"name": "Cliente"}, headers=headers)
    client_id = res.json()["id"]
    db = SessionLocal()
    db.query(Client).filter(Client.id == client_id).update({"name": "123456"})
    db.commit()
    db.close()

    assert client.get(f"/clients/{client_id}", headers=headers).json()["name"] == "123456"
    res = client.put(f"/clients/{client_id}", json={"notes": "nota"}, headers=headers)
    assert res.status_code == 200
    assert res.json()["name"] == "123456"


def test_client_name_too_long_is_rejected():
    headers = _headers()
    res = client.post("/clients", json={"name": "A" * 201}, headers=headers)
    assert res.status_code == 422


def test_client_email_rejects_obviously_invalid_values():
    headers = _headers()
    for bad_email in ["aaa", "usuario@", "@gmail.com"]:
        res = client.post("/clients", json={"name": "Cliente", "email": bad_email}, headers=headers)
        assert res.status_code == 422, bad_email


def test_client_email_accepts_any_valid_domain():
    headers = _headers()
    for good_email in ["persona@gmail.com", "contacto@empresa.com.ar", "user.name@subdominio.co"]:
        res = client.post("/clients", json={"name": "Cliente", "email": good_email}, headers=headers)
        assert res.status_code == 200, good_email


def test_client_blank_email_is_treated_as_not_provided():
    headers = _headers()
    res = client.post("/clients", json={"name": "Cliente", "email": ""}, headers=headers)
    assert res.status_code == 200
    assert res.json()["email"] is None


def test_client_cuit_is_optional():
    headers = _headers()
    res = client.post("/clients", json={"name": "Cliente"}, headers=headers)
    assert res.status_code == 200
    assert res.json()["cuit_cuil"] is None


def test_client_cuit_must_have_11_digits_if_provided():
    headers = _headers()
    res = client.post("/clients", json={"name": "Cliente", "cuit_cuil": "123"}, headers=headers)
    assert res.status_code == 422


def test_client_cuit_accepts_dashed_format():
    headers = _headers()
    res = client.post("/clients", json={"name": "Cliente", "cuit_cuil": "20-12345678-9"}, headers=headers)
    assert res.status_code == 200
    assert res.json()["cuit_cuil"] == "20-12345678-9"


def test_client_phone_is_optional():
    headers = _headers()
    res = client.post("/clients", json={"name": "Cliente"}, headers=headers)
    assert res.status_code == 200
    assert res.json()["phone"] is None


def test_client_phone_rejects_letters():
    headers = _headers()
    res = client.post("/clients", json={"name": "Cliente", "phone": "abc123"}, headers=headers)
    assert res.status_code == 422


def test_client_phone_rejects_too_short_values():
    headers = _headers()
    res = client.post("/clients", json={"name": "Cliente", "phone": "12"}, headers=headers)
    assert res.status_code == 422


def test_client_phone_accepts_common_formats():
    headers = _headers()
    for good_phone in ["1123456789", "+54 11 2345-6789", "(011) 2345-6789"]:
        res = client.post("/clients", json={"name": "Cliente", "phone": good_phone}, headers=headers)
        assert res.status_code == 200, good_phone


def test_client_update_rejects_blank_name():
    headers = _headers()
    res = client.post("/clients", json={"name": "Cliente"}, headers=headers)
    client_id = res.json()["id"]

    res = client.put(f"/clients/{client_id}", json={"name": "   "}, headers=headers)
    assert res.status_code == 422


def test_reading_a_pre_existing_client_out_of_the_new_rules_never_500s():
    """Regresión del mismo incidente de material.py (2026-09-16):
    ClientRead heredaba los field_validators de ClientBase (pensados para
    escritura), así que un cliente YA guardado con un CUIT/teléfono/email
    que no cumple las reglas nuevas (cargado antes de que existieran)
    rompía GET /clients con 500 en vez de simplemente mostrarse."""
    headers = _headers()
    res = client.post("/clients", json={"name": "Cliente"}, headers=headers)
    client_id = res.json()["id"]

    db = SessionLocal()
    db.query(Client).filter(Client.id == client_id).update(
        {
            "cuit_cuil": "no-es-un-cuit",
            "phone": "abc",
            "email": "no-es-un-email",
        }
    )
    db.commit()
    db.close()

    res = client.get("/clients", headers=headers)
    assert res.status_code == 200
    assert res.json()[0]["cuit_cuil"] == "no-es-un-cuit"

    res = client.get(f"/clients/{client_id}", headers=headers)
    assert res.status_code == 200
    assert res.json()["email"] == "no-es-un-email"
