from pathlib import Path

from fastapi.testclient import TestClient

from app.db.init_db import init_db
from app.db.session import SessionLocal, engine
from app.main import app
from app.models.company_member import CompanyMember
from app.models.user import User

client = TestClient(app)


def _reset_db_file() -> None:
    engine.dispose()  # libera conexiones abiertas (Windows bloquea el archivo si no)
    db_path = Path("cotizalaser.db")
    if db_path.exists():
        db_path.unlink()


def _register(email: str, password: str = "Password1!") -> str:
    res = client.post("/auth/register", json={"email": email, "password": password})
    assert res.status_code == 201
    return res.json()["access_token"]


def _setup_owner_and_employee():
    _reset_db_file()
    init_db()
    owner_token = _register("owner@test.com")
    res = client.post(
        "/companies",
        json={"company_name": "Empresa Test"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    company_id = res.json()["id"]
    owner_headers = {"Authorization": f"Bearer {owner_token}", "X-Company-Id": str(company_id)}

    res = client.post(
        f"/companies/{company_id}/members",
        json={"email": "employee@test.com", "password": "Password1!", "role": "employee"},
        headers=owner_headers,
    )
    member_id = res.json()["id"]
    return owner_headers, company_id, member_id


def test_globally_inactive_user_cannot_login():
    """User.is_active=False (baja global) debe rechazar el login, aunque las
    credenciales sean correctas."""
    _register("baja@test.com")
    db = SessionLocal()
    db.query(User).filter(User.email == "baja@test.com").update({"is_active": False})
    db.commit()
    db.close()

    res = client.post("/auth/login", json={"email": "baja@test.com", "password": "Password1!"})
    assert res.status_code == 403


def test_globally_inactive_user_cannot_refresh_existing_token():
    """Un token emitido antes de la baja global no debe seguir sirviendo para
    refrescar la sesión."""
    token = _register("baja_refresh@test.com")
    db = SessionLocal()
    db.query(User).filter(User.email == "baja_refresh@test.com").update({"is_active": False})
    db.commit()
    db.close()

    res = client.post("/auth/refresh", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401


def test_globally_inactive_user_old_token_still_works_until_it_expires():
    """LIMITACIÓN CONOCIDA Y ACEPTADA (no corregida en este pase): no existe
    revocación de tokens. Un access_token emitido ANTES de la baja global
    sigue siendo un JWT válido hasta que expira por su propio `exp` -- ni
    get_current_user ni get_current_company re-consultan User.is_active en
    cada request, solo /auth/login y /auth/refresh lo hacen. Cerrar esto del
    todo requeriría una blacklist/versión de token, que es infraestructura
    nueva fuera del alcance de este fix puntual. Este test documenta el
    comportamiento actual para que no se asuma que ya está cerrado."""
    owner_headers, company_id, _ = _setup_owner_and_employee()
    employee_res = client.post("/auth/login", json={"email": "employee@test.com", "password": "Password1!"})
    employee_token = employee_res.json()["access_token"]
    employee_headers = {"Authorization": f"Bearer {employee_token}", "X-Company-Id": str(company_id)}

    res = client.get("/clients", headers=employee_headers)
    assert res.status_code == 200

    db = SessionLocal()
    db.query(User).filter(User.email == "employee@test.com").update({"is_active": False})
    db.commit()
    db.close()

    # El token viejo sigue funcionando para requests normales (comportamiento
    # actual, no un bug nuevo introducido acá) porque CompanyMember.is_active
    # sigue en True.
    res = client.get("/clients", headers=employee_headers)
    assert res.status_code == 200

    # Pero ya no puede renovarlo ni volver a loguearse.
    res = client.post("/auth/refresh", headers={"Authorization": f"Bearer {employee_token}"})
    assert res.status_code == 401
    res = client.post("/auth/login", json={"email": "employee@test.com", "password": "Password1!"})
    assert res.status_code == 403


def test_deactivated_employee_cannot_login_to_select_company_but_can_still_authenticate_globally():
    """Documenta la separación de conceptos: User.is_active (global) sigue en
    True para un empleado dado de baja de UNA empresa -- /auth/login sigue
    aceptando sus credenciales (a propósito: podría pertenecer a otras
    empresas). Lo que debe bloquearse es el acceso a ESA empresa."""
    owner_headers, company_id, member_id = _setup_owner_and_employee()

    res = client.patch(
        f"/companies/{company_id}/members/{member_id}",
        json={"is_active": False},
        headers=owner_headers,
    )
    assert res.status_code == 200

    res = client.post("/auth/login", json={"email": "employee@test.com", "password": "Password1!"})
    assert res.status_code == 200
    employee_token = res.json()["access_token"]

    res = client.get(
        "/companies/me",
        headers={"Authorization": f"Bearer {employee_token}"},
    )
    assert res.status_code == 200
    my_companies = res.json()
    assert len(my_companies) == 1
    assert my_companies[0]["member_is_active"] is False


def test_deactivated_membership_blocks_company_scoped_access():
    """El corazón del bug reportado: aunque el login global funcione, un
    membership inactivo no debe permitir OPERAR dentro de esa empresa."""
    owner_headers, company_id, member_id = _setup_owner_and_employee()
    employee_res = client.post("/auth/login", json={"email": "employee@test.com", "password": "Password1!"})
    employee_headers = {
        "Authorization": f"Bearer {employee_res.json()['access_token']}",
        "X-Company-Id": str(company_id),
    }

    res = client.get("/clients", headers=employee_headers)
    assert res.status_code == 200

    client.patch(
        f"/companies/{company_id}/members/{member_id}",
        json={"is_active": False},
        headers=owner_headers,
    )

    res = client.get("/clients", headers=employee_headers)
    assert res.status_code == 403

    res = client.post("/clients", json={"name": "Cliente Nuevo"}, headers=employee_headers)
    assert res.status_code == 403
