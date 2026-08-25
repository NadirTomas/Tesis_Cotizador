"""
Escenario 6 del hallazgo ALTO #2: carrera REAL entre cancelar una cotización
y confirmar el corte de una de sus reservas, disparados lo más simultáneo
posible.

Este test NO corre con el resto del suite. SQLite no reproduce de forma
confiable el locking de fila a nivel de transacción que hace correcto el
fix (dos threads de Python contra el mismo archivo SQLite se serializan a
nivel de proceso/GIL de formas que no representan lo que pasa en Postgres
bajo READ COMMITTED real) — para probar la invariante bajo concurrencia
genuina hace falta una base Postgres real.

## Cómo ejecutarlo

1. Tené a mano una base Postgres de test (puede ser una BD nueva en tu
   instancia local de Postgres, o un contenedor descartable:
   `docker run --rm -p 55432:5432 -e POSTGRES_PASSWORD=test postgres:18`).

2. Corré las migraciones contra esa base UNA vez:

   ```
   DATABASE_URL=postgresql://postgres:test@localhost:55432/postgres alembic upgrade head
   ```

3. Corré este archivo SOLO (en su propio proceso de pytest, nunca junto al
   resto del suite — ver nota de imports diferidos más abajo):

   ```
   POSTGRES_TEST_DATABASE_URL=postgresql://postgres:test@localhost:55432/postgres \
       pytest backend/tests/test_quotation_cancel_confirm_race_postgres.py -p no:cacheprovider
   ```

Sin `POSTGRES_TEST_DATABASE_URL` seteada, este módulo se saltea por
completo (no intenta importar nada de la app, así que no interfiere con el
resto del suite corriendo contra SQLite).
"""

import os

import pytest

_POSTGRES_TEST_URL = os.environ.get("POSTGRES_TEST_DATABASE_URL")

if not _POSTGRES_TEST_URL:
    pytest.skip(
        "requiere POSTGRES_TEST_DATABASE_URL apuntando a una base Postgres de test "
        "real con las migraciones ya aplicadas -- ver docstring de este archivo",
        allow_module_level=True,
    )

# IMPORTANTE: hay que fijar DATABASE_URL ANTES de importar cualquier
# módulo de la app -- app.db.session lee la env var una sola vez al
# importarse y bindea el engine para todo el proceso. Por eso este test no
# puede compartir proceso de pytest con el resto del suite (que ya importó
# app.db.session contra SQLite).
os.environ["DATABASE_URL"] = _POSTGRES_TEST_URL

from concurrent.futures import ThreadPoolExecutor  # noqa: E402

import sqlalchemy as sa  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)

_APP_TABLES = (
    "stock_movements", "stock_reservations", "stock_sheets",
    "quotation_events", "quotation_items", "quotations",
    "pieces", "machine_configs", "materials", "clients",
    "company_members", "companies", "users",
)


def _reset_postgres_data() -> None:
    with engine.begin() as conn:
        conn.execute(sa.text(f"TRUNCATE TABLE {', '.join(_APP_TABLES)} RESTART IDENTITY CASCADE"))


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


def _create_material(headers):
    res = client.post(
        "/materials",
        json={
            "name": "Acero", "material_type": "Acero al carbono", "alloy": "SAE 1010", "thickness_mm": 3,
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
            "material_id": material_id, "cut_speed_mm_min": 3000,
            "machine_cost_per_hour_ars": 18000, "setup_time_min": 10,
        },
        headers=headers,
    )
    assert res.status_code == 200


def _rect_dxf(w: float, h: float) -> str:
    return (
        "0\nSECTION\n2\nENTITIES\n0\nLWPOLYLINE\n8\n0\n90\n4\n70\n1\n"
        f"10\n0\n20\n0\n10\n{w}\n20\n0\n10\n{w}\n20\n{h}\n10\n0\n20\n{h}\n"
        "0\nENDSEC\n0\nEOF\n"
    )


def _create_piece_with_dxf(headers, material_id, w=100, h=50, name="Pieza"):
    res = client.post("/pieces", json={"name": name, "material_id": material_id}, headers=headers)
    piece_id = res.json()["id"]
    files = {"file": (f"{name}.dxf", _rect_dxf(w, h).encode("utf-8"), "application/dxf")}
    up = client.post(f"/pieces/{piece_id}/upload-dxf", files=files, headers=headers)
    assert up.status_code == 200
    return piece_id


def _create_stock(headers, material_id, width_mm=200, height_mm=200):
    res = client.post(
        "/stock", json={"material_id": material_id, "stock_type": "FULL_SHEET", "width_mm": width_mm, "height_mm": height_mm},
        headers=headers,
    )
    assert res.status_code == 200
    return res.json()


def _setup_accepted_with_reservation():
    headers, _ = _register_and_create_company("owner_pgrace@test.com", "Empresa PgRace")
    material_id = _create_material(headers)
    _create_machine_config(headers, material_id)
    piece_id = _create_piece_with_dxf(headers, material_id)
    stock = _create_stock(headers, material_id)
    res = client.post("/clients", json={"name": "Cliente"}, headers=headers)
    client_id = res.json()["id"]
    res = client.post(
        "/quotations", json={"client_id": client_id, "issue_date": "2026-08-26T00:00:00"}, headers=headers
    )
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


def _run_n_times(n: int, fn):
    """Corre el escenario N veces para exponer la carrera pese a la variabilidad de timing entre threads."""
    results = []
    for _ in range(n):
        _reset_postgres_data()
        results.append(fn())
    return results


def test_concurrent_cancel_and_confirm_cut_never_produce_the_forbidden_state():
    def _one_race():
        headers, stock, quotation_id, reservation_id = _setup_accepted_with_reservation()

        with ThreadPoolExecutor(max_workers=2) as pool:
            cancel_future = pool.submit(
                client.patch, f"/quotations/{quotation_id}/status", json={"status": "cancelled"}, headers=headers,
            )
            confirm_future = pool.submit(
                client.post, f"/stock/reservations/{reservation_id}/confirm-cut", headers=headers,
            )
            cancel_res = cancel_future.result()
            confirm_res = confirm_future.result()

        quotation_status = client.get(f"/quotations/{quotation_id}", headers=headers).json()["status"]
        stock_status = client.get(f"/stock/{stock['id']}", headers=headers).json()["status"]

        cancel_won = cancel_res.status_code == 200
        confirm_won = confirm_res.status_code == 200

        # Exactamente uno de los dos gana. Si ambos devolvieran 200, o
        # ambos fallaran, la invariante ya estaría rota (indeterminación o
        # deadlock silencioso).
        assert cancel_won != confirm_won, (
            f"resultado ambiguo: cancel={cancel_res.status_code} confirm={confirm_res.status_code}"
        )

        if cancel_won:
            # Escenario A
            assert confirm_res.status_code == 409
            assert quotation_status == "cancelled"
            assert stock_status == "AVAILABLE"
        else:
            # Escenario B
            assert cancel_res.status_code == 409
            assert quotation_status == "accepted"
            assert stock_status == "CONSUMED"

        # El estado prohibido, en cualquier combinación: nunca 'cancelled'
        # con el stock ya consumido.
        assert not (quotation_status == "cancelled" and stock_status == "CONSUMED")

        return "cancel" if cancel_won else "confirm"

    # Corremos varias veces: el scheduler del SO decide qué thread llega
    # primero a Postgres, así que una sola corrida podría no ejercitar las
    # dos ramas. Diez intentos alcanzan para observar ambos ganadores en la
    # práctica sin hacer el test excesivamente lento.
    outcomes = _run_n_times(10, _one_race)
    assert set(outcomes) <= {"cancel", "confirm"}
