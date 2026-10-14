"""
Remitos: órdenes de ejecución concurrentes REPRODUCIDOS DE FORMA DETERMINISTA contra Postgres real.

A diferencia de test_delivery_notes_concurrency_postgres.py (dispara requests a la vez y valida la
invariante final), acá una operación se PAUSA a mitad de su transacción —con sus locks tomados— y la
segunda operación arranca mientras tanto; recién cuando Postgres confirma que la segunda quedó
BLOQUEADA esperando el lock se libera la primera. Cada test fuerza un orden concreto y siempre da el
mismo resultado, sin depender del scheduler. Ver tests/_pg_sync.py.

Ejecución: igual que los otros tests PG (DATABASE_URL y SECRET_KEY en el entorno antes de pytest,
base descartable con migraciones aplicadas; hace TRUNCATE).
"""

import os

import pytest

_DATABASE_URL = os.environ.get("DATABASE_URL", "")

if not _DATABASE_URL.startswith("postgresql"):
    pytest.skip(
        "requiere DATABASE_URL apuntando a una base Postgres de test real (fijada en el shell ANTES de "
        "invocar pytest) con las migraciones ya aplicadas -- ver docstring",
        allow_module_level=True,
    )

from concurrent.futures import ThreadPoolExecutor  # noqa: E402

import sqlalchemy as sa  # noqa: E402

from app.api.v1 import routes_quotations, routes_stock  # noqa: E402
from app.api.v1.routes_auth import limiter as _auth_limiter  # noqa: E402
from app.api.v1.routes_client_errors import limiter as _client_errors_limiter  # noqa: E402
from app.api.v1.routes_companies import limiter as _companies_limiter  # noqa: E402
from app.api.v1.routes_pieces import limiter as _pieces_limiter  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.main import limiter as _main_limiter  # noqa: E402
from app.services import delivery_notes as dn_service  # noqa: E402
from tests._delivery_helpers import (  # noqa: E402
    client,
    confirm_cut,
    create_note,
    issue_note,
    make_quotation,
    register_company,
    set_status,
    void_note,
)
from tests._pg_sync import Pause, assert_not_blocked_for, wait_until_blocked  # noqa: E402

_LIMITERS = (_main_limiter, _auth_limiter, _pieces_limiter, _companies_limiter, _client_errors_limiter)
_APP_TABLES = (
    "delivery_note_items", "delivery_notes", "document_sequences",
    "stock_movements", "stock_reservations", "stock_sheets",
    "quotation_events", "quotation_items", "quotations",
    "pieces", "machine_configs", "materials", "clients",
    "company_members", "companies", "users",
)


@pytest.fixture(autouse=True)
def _clean_state():
    for limiter in _LIMITERS:
        limiter.reset()
    with engine.begin() as conn:
        conn.execute(sa.text(f"TRUNCATE TABLE {', '.join(_APP_TABLES)} RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture
def owner():
    headers, company_id = register_company("owner@interleave.com", "Taller Interleave")
    return {"headers": headers, "company_id": company_id}


@pytest.fixture
def pool():
    with ThreadPoolExecutor(max_workers=4) as executor:
        yield executor


def _note(headers, note_id):
    return client.get(f"/delivery-notes/{note_id}", headers=headers).json()


def _delivered(headers, quotation_id):
    return client.get(f"/delivery-notes/quotation/{quotation_id}/status", headers=headers).json()["total_delivered"]


def _pause_issue(monkeypatch) -> Pause:
    """Pausa emitir justo después de tomar el número (con locks de cotización, remito y secuencia tomados)."""
    pause = Pause()
    monkeypatch.setattr(dn_service, "next_sequence_number", pause.wrap(dn_service.next_sequence_number))
    return pause


# ───────────────────────── emitir vs. emitir ─────────────────────────


def test_second_issue_for_the_last_balance_waits_and_is_rejected(owner, pool, monkeypatch):
    q = make_quotation(owner["headers"], quantities=(100,))
    item = q["item_ids"][0]
    a = create_note(owner["headers"], q["quotation_id"], [(item, 60)]).json()["id"]
    b = create_note(owner["headers"], q["quotation_id"], [(item, 60)]).json()["id"]

    pause = _pause_issue(monkeypatch)
    first = pool.submit(lambda: issue_note(owner["headers"], a))
    pause.wait_reached()
    second = pool.submit(lambda: issue_note(owner["headers"], b))
    wait_until_blocked(engine)  # B está esperando el lock de la cotización: no pudo validar con el saldo viejo
    pause.release()

    assert first.result().status_code == 200
    res = second.result()
    assert res.status_code == 409 and "pendientes" in res.json()["detail"]
    assert _delivered(owner["headers"], q["quotation_id"]) == 60
    assert (_note(owner["headers"], b)["status"], _note(owner["headers"], b)["number"]) == ("DRAFT", None)


def test_issuing_the_same_note_twice_waits_and_second_gets_409(owner, pool, monkeypatch):
    q = make_quotation(owner["headers"], quantities=(10,))
    note_id = create_note(owner["headers"], q["quotation_id"], [(q["item_ids"][0], 4)]).json()["id"]

    pause = _pause_issue(monkeypatch)
    first = pool.submit(lambda: issue_note(owner["headers"], note_id))
    pause.wait_reached()
    second = pool.submit(lambda: issue_note(owner["headers"], note_id))
    wait_until_blocked(engine)
    pause.release()

    assert (first.result().status_code, second.result().status_code) == (200, 409)
    assert _note(owner["headers"], note_id)["number"] == "R-000001"
    assert _delivered(owner["headers"], q["quotation_id"]) == 4


def test_numbering_waits_on_the_sequence_row_and_stays_consecutive(owner, pool, monkeypatch):
    """Dos remitos de cotizaciones distintas de la misma empresa: no comparten lock de cotización,
    sí la fila del contador. El segundo espera y recibe el número siguiente."""
    qa = make_quotation(owner["headers"], quantities=(5,))
    qb = make_quotation(owner["headers"], quantities=(5,))
    a = create_note(owner["headers"], qa["quotation_id"], [(qa["item_ids"][0], 1)]).json()["id"]
    b = create_note(owner["headers"], qb["quotation_id"], [(qb["item_ids"][0], 1)]).json()["id"]

    pause = _pause_issue(monkeypatch)
    first = pool.submit(lambda: issue_note(owner["headers"], a))
    pause.wait_reached()
    second = pool.submit(lambda: issue_note(owner["headers"], b))
    wait_until_blocked(engine)
    pause.release()

    assert first.result().json()["number"] == "R-000001"
    assert second.result().json()["number"] == "R-000002"


# ───────────────────────── emitir vs. anular ─────────────────────────


def test_issue_waits_for_an_in_flight_void_and_then_sees_the_restored_balance(owner, pool, monkeypatch):
    q = make_quotation(owner["headers"], quantities=(100,))
    item = q["item_ids"][0]
    a = create_note(owner["headers"], q["quotation_id"], [(item, 100)]).json()["id"]
    b = create_note(owner["headers"], q["quotation_id"], [(item, 100)]).json()["id"]
    assert issue_note(owner["headers"], a).status_code == 200

    pause = Pause()
    monkeypatch.setattr(dn_service, "log_event", pause.wrap(dn_service.log_event))
    voiding = pool.submit(lambda: void_note(owner["headers"], a, "anulación en curso"))
    pause.wait_reached()
    issuing = pool.submit(lambda: issue_note(owner["headers"], b))
    wait_until_blocked(engine)
    pause.release()

    assert voiding.result().status_code == 200
    assert issuing.result().status_code == 200  # el saldo liberado por la anulación ya es visible
    assert (_note(owner["headers"], a)["status"], _note(owner["headers"], b)["status"]) == ("VOIDED", "ISSUED")
    assert _delivered(owner["headers"], q["quotation_id"]) == 100


def test_void_waits_for_an_in_flight_issue_and_both_complete_consistently(owner, pool, monkeypatch):
    q = make_quotation(owner["headers"], quantities=(100,))
    item = q["item_ids"][0]
    a = create_note(owner["headers"], q["quotation_id"], [(item, 60)]).json()["id"]
    b = create_note(owner["headers"], q["quotation_id"], [(item, 40)]).json()["id"]
    assert issue_note(owner["headers"], a).status_code == 200

    pause = _pause_issue(monkeypatch)
    issuing = pool.submit(lambda: issue_note(owner["headers"], b))
    pause.wait_reached()
    voiding = pool.submit(lambda: void_note(owner["headers"], a, "anular mientras se emite otro"))
    wait_until_blocked(engine)
    pause.release()

    assert issuing.result().status_code == 200
    assert voiding.result().status_code == 200
    assert _delivered(owner["headers"], q["quotation_id"]) == 40
    assert (_note(owner["headers"], a)["status"], _note(owner["headers"], b)["number"]) == ("VOIDED", "R-000002")


# ───────────────────────── emitir vs. cancelar cotización ─────────────────────────


def test_cancel_waits_for_an_in_flight_issue_and_is_rejected(owner, pool, monkeypatch):
    q = make_quotation(owner["headers"], quantities=(10,))
    note_id = create_note(owner["headers"], q["quotation_id"], [(q["item_ids"][0], 5)]).json()["id"]

    pause = _pause_issue(monkeypatch)
    issuing = pool.submit(lambda: issue_note(owner["headers"], note_id))
    pause.wait_reached()
    cancelling = pool.submit(lambda: set_status(owner["headers"], q["quotation_id"], "cancelled"))
    wait_until_blocked(engine)
    pause.release()

    assert issuing.result().status_code == 200
    res = cancelling.result()
    assert res.status_code == 409 and "remitos emitidos" in res.json()["detail"]
    assert client.get(f"/quotations/{q['quotation_id']}", headers=owner["headers"]).json()["status"] == "accepted"


def test_issue_waits_for_an_in_flight_cancel_and_is_rejected(owner, pool, monkeypatch):
    q = make_quotation(owner["headers"], quantities=(10,), confirm_cut_for_all=False)
    note_id = create_note(owner["headers"], q["quotation_id"], [(q["item_ids"][0], 5)]).json()["id"]

    pause = Pause()
    monkeypatch.setattr(routes_quotations, "release_quotation_reservations", pause.wrap(routes_quotations.release_quotation_reservations))
    cancelling = pool.submit(lambda: set_status(owner["headers"], q["quotation_id"], "cancelled"))
    pause.wait_reached()
    issuing = pool.submit(lambda: issue_note(owner["headers"], note_id))
    wait_until_blocked(engine)
    pause.release()

    assert cancelling.result().status_code == 200
    res = issuing.result()
    assert res.status_code == 409 and "aceptadas" in res.json()["detail"]
    assert (_note(owner["headers"], note_id)["status"], _note(owner["headers"], note_id)["number"]) == ("DRAFT", None)


# ───────────────────────── emitir vs. confirmar corte ─────────────────────────


def test_issue_does_not_see_an_uncommitted_cut_confirmation_and_works_after_it_commits(owner, pool, monkeypatch):
    q = make_quotation(owner["headers"], quantities=(10,), confirm_cut_for_all=False)
    reservation_id = confirm_cut(owner["headers"], q, 0, confirm=False)
    note_id = create_note(owner["headers"], q["quotation_id"], [(q["item_ids"][0], 5)]).json()["id"]

    pause = Pause()
    monkeypatch.setattr(routes_stock, "_log_movement", pause.wrap(routes_stock._log_movement))
    confirming = pool.submit(lambda: client.post(f"/stock/reservations/{reservation_id}/confirm-cut", headers=owner["headers"]))
    pause.wait_reached()  # confirm-cut ya actualizó la reserva a CONSUMED pero todavía no comiteó

    res = issue_note(owner["headers"], note_id)  # no debe bloquearse ni ver el corte sin comitear
    assert res.status_code == 409 and "corte" in res.json()["detail"]
    assert_not_blocked_for(engine, 0.3)
    pause.release()
    assert confirming.result().status_code == 200

    res = issue_note(owner["headers"], note_id)
    assert res.status_code == 200 and res.json()["number"] == "R-000001"


# ───────────────────────── empresas distintas ─────────────────────────


def test_operations_of_different_companies_never_block_each_other(owner, pool, monkeypatch):
    q1 = make_quotation(owner["headers"], quantities=(10,))
    n1 = create_note(owner["headers"], q1["quotation_id"], [(q1["item_ids"][0], 5)]).json()["id"]
    other_headers, _ = register_company("otra@interleave.com", "Otro Taller")
    q2 = make_quotation(other_headers, quantities=(10,))
    n2 = create_note(other_headers, q2["quotation_id"], [(q2["item_ids"][0], 5)]).json()["id"]

    pause = _pause_issue(monkeypatch)
    first = pool.submit(lambda: issue_note(owner["headers"], n1))
    pause.wait_reached()  # la empresa 1 tiene tomados el lock de su cotización y de su contador

    res = issue_note(other_headers, n2)  # la empresa 2 emite sin esperar a la 1 (con el pause ya consumido no se frena)
    assert res.status_code == 200 and res.json()["number"] == "R-000001"
    assert_not_blocked_for(engine, 0.3)
    pause.release()

    assert first.result().status_code == 200
    assert first.result().json()["number"] == "R-000001"  # numeración independiente por empresa
