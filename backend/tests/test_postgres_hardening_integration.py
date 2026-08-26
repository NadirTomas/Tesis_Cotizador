"""
Validación del hardening de integridad (DELETE cascade, SET NULL, aislamiento
multiempresa) contra PostgreSQL real — no SQLite. Complementa
test_quotation_delete.py y test_quotation_cancel_confirm_invariant.py
(que sí corren en la suite normal contra SQLite) con los mismos escenarios
verificados contra el motor real de producción.

## Cómo ejecutarlo

Requiere una base Postgres de test vacía o descartable, con las
migraciones ya aplicadas (`alembic upgrade head`). DATABASE_URL debe
apuntar a Postgres DESDE ANTES de invocar pytest -- conftest.py importa
app.db.session (vía routes_auth) al recolectar los tests, así que fijar la
env var dentro de este módulo llegaría tarde y seguiría bindeando contra
SQLite. Por eso corre en su propio proceso de pytest, con la env var ya
puesta en el shell:

    DATABASE_URL=postgresql://postgres:test@localhost:55433/cotizalaser_test \
        pytest backend/tests/test_postgres_hardening_integration.py -p no:cacheprovider

Sin DATABASE_URL apuntando a Postgres, este módulo se saltea por completo
(y la suite normal sigue corriendo contra SQLite sin verse afectada).
"""

import os

import pytest

_DATABASE_URL = os.environ.get("DATABASE_URL", "")

if not _DATABASE_URL.startswith("postgresql"):
    pytest.skip(
        "requiere DATABASE_URL apuntando a una base Postgres de test real (fijada "
        "en el shell ANTES de invocar pytest, no dentro de este módulo) con las "
        "migraciones ya aplicadas -- ver docstring de este archivo",
        allow_module_level=True,
    )

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


def setup_function(_fn):
    _reset_postgres_data()


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


def _create_client_record(headers, name="Cliente"):
    res = client.post("/clients", json={"name": name}, headers=headers)
    assert res.status_code == 200
    return res.json()["id"]


def _create_quotation(headers, client_id):
    res = client.post(
        "/quotations", json={"client_id": client_id, "issue_date": "2026-08-26T00:00:00"}, headers=headers
    )
    assert res.status_code == 200
    return res.json()["id"]


def _create_quotation_item(headers, quotation_id, piece_id, material_id):
    res = client.post(
        "/quotation-items",
        json={"quotation_id": quotation_id, "piece_id": piece_id, "material_id": material_id, "quantity": 2},
        headers=headers,
    )
    assert res.status_code == 200
    return res.json()["id"]


def _advance_to_accepted(headers, quotation_id):
    res = client.patch(f"/quotations/{quotation_id}/status", json={"status": "sent"}, headers=headers)
    assert res.status_code == 200
    res = client.patch(f"/quotations/{quotation_id}/status", json={"status": "accepted"}, headers=headers)
    assert res.status_code == 200


def _db_row_counts(quotation_id: int) -> tuple[int, int, int]:
    with engine.connect() as conn:
        q = conn.execute(sa.text("SELECT count(*) FROM quotations WHERE id = :id"), {"id": quotation_id}).scalar()
        items = conn.execute(
            sa.text("SELECT count(*) FROM quotation_items WHERE quotation_id = :id"), {"id": quotation_id}
        ).scalar()
        events = conn.execute(
            sa.text("SELECT count(*) FROM quotation_events WHERE quotation_id = :id"), {"id": quotation_id}
        ).scalar()
        return q, items, events


# ---------- Etapa 5: DELETE /quotations/{id} contra Postgres real ----------


def test_delete_draft_quotation_cascades_on_real_postgres():
    headers, _company_id = _register_and_create_company("owner_pg_del@test.com", "Empresa PgDel")
    material_id = _create_material(headers)
    _create_machine_config(headers, material_id)
    piece_id = _create_piece_with_dxf(headers, material_id)
    client_id = _create_client_record(headers)
    quotation_id = _create_quotation(headers, client_id)
    _create_quotation_item(headers, quotation_id, piece_id, material_id)

    q_before, items_before, events_before = _db_row_counts(quotation_id)
    assert q_before == 1 and items_before == 1 and events_before >= 1

    res = client.delete(f"/quotations/{quotation_id}", headers=headers)
    assert res.status_code == 204  # antes del fix, esto era un 500 (ForeignKeyViolation) en Postgres

    assert _db_row_counts(quotation_id) == (0, 0, 0)


def test_delete_rejected_outside_draft_on_real_postgres():
    for target_status, chain in [("sent", ["sent"]), ("accepted", ["sent", "accepted"]), ("cancelled", ["cancelled"])]:
        _reset_postgres_data()
        headers, _company_id = _register_and_create_company("owner_pg_del2@test.com", "Empresa PgDel2")
        client_id = _create_client_record(headers)
        quotation_id = _create_quotation(headers, client_id)
        for status in chain:
            assert client.patch(f"/quotations/{quotation_id}/status", json={"status": status}, headers=headers).status_code == 200

        res = client.delete(f"/quotations/{quotation_id}", headers=headers)
        assert res.status_code == 400, f"esperaba 400 en estado '{target_status}'"
        assert _db_row_counts(quotation_id)[0] == 1  # sigue existiendo


def test_delete_cross_tenant_rejected_on_real_postgres():
    headers_a, _ = _register_and_create_company("owner_pg_del_a@test.com", "Empresa PgDelA")
    client_id = _create_client_record(headers_a)
    quotation_id = _create_quotation(headers_a, client_id)
    headers_b, _ = _register_and_create_company("owner_pg_del_b@test.com", "Empresa PgDelB")

    res = client.delete(f"/quotations/{quotation_id}", headers=headers_b)
    assert res.status_code == 404
    assert _db_row_counts(quotation_id)[0] == 1  # empresa A no se vio afectada


# ---------- Etapa 6: SET NULL en stock_reservations.quotation_item_id ----------


def test_deleting_quotation_item_sets_reservation_fk_null_and_preserves_history():
    headers, _company_id = _register_and_create_company("owner_pg_sr@test.com", "Empresa PgSR")
    material_id = _create_material(headers)
    _create_machine_config(headers, material_id)
    piece_id = _create_piece_with_dxf(headers, material_id)
    stock = _create_stock(headers, material_id)
    client_id = _create_client_record(headers)
    quotation_id = _create_quotation(headers, client_id)
    item_id = _create_quotation_item(headers, quotation_id, piece_id, material_id)
    _advance_to_accepted(headers, quotation_id)

    res = client.post(
        f"/stock/{stock['id']}/reserve",
        json={"piece_id": piece_id, "material_id": material_id, "quotation_id": quotation_id, "quotation_item_id": item_id},
        headers=headers,
    )
    assert res.status_code == 200
    reservation_id = res.json()["id"]

    # Camino permitido: borrar el ítem de una cotización 'accepted' libera
    # la reserva activa primero (routes_quotation_items.py), y solo
    # entonces borra la fila del ítem.
    res = client.delete(f"/quotation-items/{item_id}", headers=headers)
    assert res.status_code == 204  # sin esto, FK violation antes del fix (ver hallazgo adicional)

    with engine.connect() as conn:
        row = conn.execute(
            sa.text("SELECT quotation_item_id, status FROM stock_reservations WHERE id = :id"),
            {"id": reservation_id},
        ).fetchone()
    assert row is not None, "la reserva debe sobrevivir al ítem — es historial, no se cascadea"
    assert row[0] is None, "quotation_item_id debe quedar NULL, no la reserva completa"
    assert row[1] == "RELEASED"

    # El historial de movimientos de stock también sigue intacto.
    res = client.get(f"/stock/{stock['id']}/movements", headers=headers)
    assert res.status_code == 200
    assert [m["movement_type"] for m in res.json()] == ["CREATED", "RESERVED", "RELEASED"]

    # La reserva sigue siendo consultable (con su vínculo a ítem ya nulo).
    res = client.get("/stock/reservations", params={"quotation_id": quotation_id}, headers=headers)
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["id"] == reservation_id
