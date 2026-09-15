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


def test_globally_inactive_user_old_access_token_is_rejected_by_protected_endpoints():
    """Corregido: get_current_user revalida contra la DB en cada request. Un
    access_token emitido ANTES de la baja global (User.is_active=False) deja
    de servir para endpoints protegidos, aunque el JWT en sí siga siendo
    criptográficamente válido y no vencido. Esto NO es revocación de tokens
    (no hay blacklist ni versión de token) -- es revalidación del estado del
    usuario en cada request autenticado."""
    owner_headers, company_id, _ = _setup_owner_and_employee()

    # 1. Token emitido mientras el usuario está activo.
    employee_res = client.post("/auth/login", json={"email": "employee@test.com", "password": "Password1!"})
    employee_token = employee_res.json()["access_token"]
    employee_headers = {"Authorization": f"Bearer {employee_token}", "X-Company-Id": str(company_id)}

    res = client.get("/clients", headers=employee_headers)
    assert res.status_code == 200

    # 2. Se desactiva el usuario en DB (sin tocar el token para nada).
    db = SessionLocal()
    db.query(User).filter(User.email == "employee@test.com").update({"is_active": False})
    db.commit()
    db.close()

    # 3. El mismo token viejo, contra un endpoint protegido -> rechazado.
    res = client.get("/clients", headers=employee_headers)
    assert res.status_code == 401

    # También se corta en endpoints que solo dependen de get_current_user
    # (sin pasar por get_current_company), como /companies/me.
    res = client.get("/companies/me", headers={"Authorization": f"Bearer {employee_token}"})
    assert res.status_code == 401

    # 4. Refresh con usuario inactivo -> rechazado (ya cubierto también por
    # test_globally_inactive_user_cannot_refresh_existing_token).
    res = client.post("/auth/refresh", headers={"Authorization": f"Bearer {employee_token}"})
    assert res.status_code == 401

    # Y tampoco puede volver a loguearse desde cero.
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


def test_deactivated_membership_in_one_company_does_not_affect_another():
    """CompanyMember.is_active=False es por-empresa: si el usuario pertenece
    a otra empresa donde sigue activo, conserva su sesión global y puede
    seguir operando ahí -- solo pierde acceso a la empresa donde fue dado de
    baja."""
    owner_a_headers, company_a, member_a_id = _setup_owner_and_employee()

    owner_b_token = _register("owner_b@test.com")
    res = client.post(
        "/companies",
        json={"company_name": "Empresa B"},
        headers={"Authorization": f"Bearer {owner_b_token}"},
    )
    company_b = res.json()["id"]
    owner_b_headers = {"Authorization": f"Bearer {owner_b_token}", "X-Company-Id": str(company_b)}
    client.post(
        f"/companies/{company_b}/members",
        json={"email": "employee@test.com", "password": "Password1!", "role": "employee"},
        headers=owner_b_headers,
    )

    client.patch(
        f"/companies/{company_a}/members/{member_a_id}",
        json={"is_active": False},
        headers=owner_a_headers,
    )

    employee_res = client.post("/auth/login", json={"email": "employee@test.com", "password": "Password1!"})
    assert employee_res.status_code == 200
    employee_token = employee_res.json()["access_token"]

    res = client.get("/clients", headers={"Authorization": f"Bearer {employee_token}", "X-Company-Id": str(company_a)})
    assert res.status_code == 403

    res = client.get("/clients", headers={"Authorization": f"Bearer {employee_token}", "X-Company-Id": str(company_b)})
    assert res.status_code == 200
