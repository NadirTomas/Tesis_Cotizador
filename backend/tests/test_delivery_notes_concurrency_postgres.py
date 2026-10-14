"""
Remitos bajo concurrencia REAL (Postgres, READ COMMITTED): sobreentrega,
doble emisión, numeración, anulación vs. emisión y cancelación vs. emisión.

Igual que test_quotation_cancel_confirm_race_postgres.py, este módulo NO corre
con el resto del suite: SQLite serializa los threads de otra forma y no
representa el locking de filas de Postgres. Se saltea sin DATABASE_URL.

## Cómo ejecutarlo

1. Base Postgres descartable (la misma imagen que CI y Railway):

   docker run -d --rm --name cotizalaser-test-pg -p 55432:5432 \
       -e POSTGRES_PASSWORD=test -e POSTGRES_DB=cotizalaser_test postgres:18

2. Migraciones UNA vez:

   DATABASE_URL=postgresql://postgres:test@localhost:55432/cotizalaser_test alembic upgrade head

3. Este archivo SOLO, con DATABASE_URL y SECRET_KEY en el entorno ANTES de pytest:

   DATABASE_URL=postgresql://postgres:test@localhost:55432/cotizalaser_test \
       pytest tests/test_delivery_notes_concurrency_postgres.py -p no:cacheprovider

OJO: cada escenario hace TRUNCATE de las tablas de la app. Usar solo una base de test.
"""

import os

import pytest

_DATABASE_URL = os.environ.get("DATABASE_URL", "")

if not _DATABASE_URL.startswith("postgresql"):
    pytest.skip(
        "requiere DATABASE_URL apuntando a una base Postgres de test real (fijada en el shell "
        "ANTES de invocar pytest) con las migraciones ya aplicadas -- ver docstring",
        allow_module_level=True,
    )

import threading  # noqa: E402
from concurrent.futures import ThreadPoolExecutor  # noqa: E402

import sqlalchemy as sa  # noqa: E402

from app.api.v1.routes_auth import limiter as _auth_limiter  # noqa: E402
from app.api.v1.routes_client_errors import limiter as _client_errors_limiter  # noqa: E402
from app.api.v1.routes_companies import limiter as _companies_limiter  # noqa: E402
from app.api.v1.routes_pieces import limiter as _pieces_limiter  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.main import limiter as _main_limiter  # noqa: E402
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

_LIMITERS = (_main_limiter, _auth_limiter, _pieces_limiter, _companies_limiter, _client_errors_limiter)

_APP_TABLES = (
    "delivery_note_items", "delivery_notes", "document_sequences",
    "stock_movements", "stock_reservations", "stock_sheets",
    "quotation_events", "quotation_items", "quotations",
    "pieces", "machine_configs", "materials", "clients",
    "company_members", "companies", "users",
)

_REPEATS = 12


@pytest.fixture(autouse=True)
def _clean_state():
    for limiter in _LIMITERS:
        limiter.reset()
    with engine.begin() as conn:
        conn.execute(sa.text(f"TRUNCATE TABLE {', '.join(_APP_TABLES)} RESTART IDENTITY CASCADE"))
    yield


def _fresh_scenario(i: int):
    """Cada repetición parte de datos limpios (incluida la secuencia de numeración)."""
    for limiter in _LIMITERS:
        limiter.reset()
    with engine.begin() as conn:
        conn.execute(sa.text(f"TRUNCATE TABLE {', '.join(_APP_TABLES)} RESTART IDENTITY CASCADE"))
    headers, _ = register_company(f"owner{i}@pgremitos.com", f"Empresa {i}")
    return headers


def _race(calls):
    """Dispara todas las llamadas a la vez (barrera) y devuelve los status en orden."""
    barrier = threading.Barrier(len(calls))

    def run(call):
        barrier.wait()
        return call()

    with ThreadPoolExecutor(max_workers=len(calls)) as pool:
        futures = [pool.submit(run, c) for c in calls]
        return [f.result() for f in futures]


def _note(headers, note_id):
    return client.get(f"/delivery-notes/{note_id}", headers=headers).json()


def _delivered(headers, quotation_id):
    return client.get(f"/delivery-notes/quotation/{quotation_id}/status", headers=headers).json()["total_delivered"]


def test_two_concurrent_issues_cannot_over_deliver():
    """60 + 60 sobre 100 pendientes: exactamente una emisión gana, la otra recibe 409."""
    for i in range(_REPEATS):
        headers = _fresh_scenario(i)
        q = make_quotation(headers, quantities=(100,))
        a = create_note(headers, q["quotation_id"], [(q["item_ids"][0], 60)]).json()["id"]
        b = create_note(headers, q["quotation_id"], [(q["item_ids"][0], 60)]).json()["id"]
        order = [a, b] if i % 2 == 0 else [b, a]
        results = _race([lambda n=n: issue_note(headers, n).status_code for n in order])
        assert sorted(results) == [200, 409], (i, results)
        assert _delivered(headers, q["quotation_id"]) == 60, i


def test_same_draft_issued_twice_concurrently_is_issued_once():
    for i in range(_REPEATS):
        headers = _fresh_scenario(i)
        q = make_quotation(headers, quantities=(10,))
        note_id = create_note(headers, q["quotation_id"], [(q["item_ids"][0], 4)]).json()["id"]
        results = _race([lambda: issue_note(headers, note_id).status_code for _ in range(3)])
        assert sorted(results) == [200, 409, 409], (i, results)
        assert _note(headers, note_id)["number"] == "R-000001"
        assert _delivered(headers, q["quotation_id"]) == 4
        with engine.connect() as conn:
            assert conn.execute(sa.text("SELECT last_number FROM document_sequences")).scalar_one() == 1


def test_concurrent_issues_get_unique_consecutive_numbers_including_first_use():
    """Cada repetición arranca SIN fila de secuencia: se ejercita también la carrera de creación del contador."""
    for i in range(6):
        headers = _fresh_scenario(i)
        quotations = [make_quotation(headers, quantities=(5,)) for _ in range(6)]
        note_ids = [create_note(headers, q["quotation_id"], [(q["item_ids"][0], 1)]).json()["id"] for q in quotations]
        results = _race([lambda n=n: issue_note(headers, n) for n in note_ids])
        assert [r.status_code for r in results] == [200] * 6, (i, [r.text for r in results])
        numbers = sorted(r.json()["number"] for r in results)
        assert numbers == [f"R-{n:06d}" for n in range(1, 7)], (i, numbers)


def test_numbering_with_many_drafts_of_the_same_quotation():
    headers = _fresh_scenario(0)
    q = make_quotation(headers, quantities=(40,))
    note_ids = [create_note(headers, q["quotation_id"], [(q["item_ids"][0], 1)]).json()["id"] for _ in range(10)]
    results = _race([lambda n=n: issue_note(headers, n).status_code for n in note_ids])
    assert results == [200] * 10
    assert _delivered(headers, q["quotation_id"]) == 10
    with engine.connect() as conn:
        numbers = [r[0] for r in conn.execute(sa.text("SELECT number FROM delivery_notes ORDER BY number"))]
    assert numbers == [f"R-{n:06d}" for n in range(1, 11)]


def test_void_concurrent_with_issue_never_leaves_inconsistent_totals():
    """A (100/100) emitido. Se anula A mientras se intenta emitir B (100): nunca A y B emitidos a la vez."""
    outcomes = set()
    for i in range(_REPEATS):
        headers = _fresh_scenario(i)
        q = make_quotation(headers, quantities=(100,))
        item = q["item_ids"][0]
        draft_b = create_note(headers, q["quotation_id"], [(item, 100)]).json()["id"]
        a = create_note(headers, q["quotation_id"], [(item, 100)]).json()["id"]
        assert issue_note(headers, a).status_code == 200

        calls = [lambda: void_note(headers, a, "carrera").status_code, lambda: issue_note(headers, draft_b).status_code]
        if i % 2:
            calls.reverse()
        results = _race(calls)
        assert 500 not in results, (i, results)

        statuses = (_note(headers, a)["status"], _note(headers, draft_b)["status"])
        delivered = _delivered(headers, q["quotation_id"])
        assert statuses in {("VOIDED", "ISSUED"), ("VOIDED", "DRAFT")}, (i, statuses, results)
        assert delivered == (100 if statuses[1] == "ISSUED" else 0), (i, statuses, delivered)
        outcomes.add(statuses)
    assert outcomes  # ambos órdenes válidos; lo importante es que ninguno violó la invariante


def test_cancel_concurrent_with_issue_never_leaves_cancelled_with_issued_note():
    outcomes = set()
    for i in range(_REPEATS):
        headers = _fresh_scenario(i)
        q = make_quotation(headers, quantities=(10,))
        note_id = create_note(headers, q["quotation_id"], [(q["item_ids"][0], 5)]).json()["id"]
        calls = [lambda: set_status(headers, q["quotation_id"], "cancelled").status_code, lambda: issue_note(headers, note_id).status_code]
        if i % 2:
            calls.reverse()
        results = _race(calls)
        assert 500 not in results, (i, results)

        quotation_status = client.get(f"/quotations/{q['quotation_id']}", headers=headers).json()["status"]
        note_status = _note(headers, note_id)["status"]
        assert (quotation_status, note_status) in {("cancelled", "DRAFT"), ("accepted", "ISSUED")}, (i, quotation_status, note_status, results)
        outcomes.add((quotation_status, note_status))


def test_issue_concurrent_with_confirm_cut_never_issues_without_a_confirmed_cut():
    """Reserva ACTIVE + borrador; se confirma el corte a la vez que se intenta emitir.

    Resultados válidos: (emitido, corte CONSUMED) o (borrador sin número, 409). Nunca un remito emitido
    sin corte confirmado (CONSUMED no se revierte, por eso la lectura bajo lock es suficiente)."""
    outcomes = set()
    for i in range(_REPEATS):
        headers = _fresh_scenario(i)
        q = make_quotation(headers, quantities=(10,), confirm_cut_for_all=False)
        reservation_id = confirm_cut(headers, q, 0, confirm=False)
        note_id = create_note(headers, q["quotation_id"], [(q["item_ids"][0], 5)]).json()["id"]

        calls = [
            lambda: client.post(f"/stock/reservations/{reservation_id}/confirm-cut", headers=headers).status_code,
            lambda: issue_note(headers, note_id).status_code,
        ]
        if i % 2:
            calls.reverse()
        results = _race(calls)
        assert 500 not in results, (i, results)

        note = _note(headers, note_id)
        with engine.connect() as conn:
            consumed = conn.execute(sa.text("SELECT status FROM stock_reservations WHERE id = :id"), {"id": reservation_id}).scalar_one()
        assert consumed == "CONSUMED", (i, results)
        if note["status"] == "ISSUED":
            assert note["number"] == "R-000001", i
        else:
            assert (note["status"], note["number"]) == ("DRAFT", None), (i, note)
            assert issue_note(headers, note_id).status_code == 200  # ya con el corte confirmado se puede emitir
        outcomes.add(note["status"])
    assert outcomes


def test_concurrent_issues_without_confirmed_cut_are_all_rejected_and_use_no_number():
    headers = _fresh_scenario(0)
    q = make_quotation(headers, quantities=(10,), confirm_cut_for_all=False)
    note_ids = [create_note(headers, q["quotation_id"], [(q["item_ids"][0], 1)]).json()["id"] for _ in range(4)]
    results = _race([lambda n=n: issue_note(headers, n).status_code for n in note_ids])
    assert results == [409] * 4
    with engine.connect() as conn:
        assert conn.execute(sa.text("SELECT count(*) FROM document_sequences")).scalar_one() == 0
        assert conn.execute(sa.text("SELECT count(*) FROM delivery_notes WHERE number IS NOT NULL")).scalar_one() == 0
    assert _delivered(headers, q["quotation_id"]) == 0
