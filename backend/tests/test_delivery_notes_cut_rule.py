"""Regla de negocio: un remito solo puede EMITIRSE si el corte de sus ítems está confirmado.

"Corte confirmado" = el ítem tiene una StockReservation CONSUMED de esa cotización (flujo real
reserve -> confirm-cut). Guardar borradores NO exige corte. No hay bandera aparte."""

from pathlib import Path

import pytest

from app.db.init_db import init_db
from app.db.session import SessionLocal, engine
from app.models.document_sequence import DocumentSequence
from tests._delivery_helpers import (
    add_employee,
    client,
    confirm_cut,
    create_note,
    delivery_status,
    issue_note,
    make_quotation,
    register_company,
    void_note,
)

CUT_MESSAGE = "No se puede emitir el remito porque el corte de la cotización todavía no fue confirmado"


@pytest.fixture(autouse=True)
def _fresh_db():
    engine.dispose()
    db_path = Path("cotizalaser.db")
    if db_path.exists():
        db_path.unlink()
    init_db()
    yield


@pytest.fixture
def owner():
    headers, company_id = register_company("owner@corte.com", "Taller Corte")
    return {"headers": headers, "company_id": company_id}


@pytest.fixture
def uncut(owner):
    """Cotización aceptada, SIN corte confirmado."""
    return make_quotation(owner["headers"], quantities=(100,), confirm_cut_for_all=False)


def _sequence_rows() -> int:
    db = SessionLocal()
    try:
        return db.query(DocumentSequence).count()
    finally:
        db.close()


# ───────────── sin corte: emitir se rechaza, borradores se permiten ─────────────


def test_issue_without_confirmed_cut_is_rejected_with_409(owner, uncut):
    draft = create_note(owner["headers"], uncut["quotation_id"], [(uncut["item_ids"][0], 10)]).json()
    res = issue_note(owner["headers"], draft["id"])
    assert res.status_code == 409
    assert res.json()["detail"].startswith(CUT_MESSAGE)
    assert "Pieza 1" in res.json()["detail"]


def test_draft_can_be_created_edited_read_and_deleted_without_confirmed_cut(owner, uncut):
    item = uncut["item_ids"][0]
    res = create_note(owner["headers"], uncut["quotation_id"], [(item, 10)], notes="sin corte todavía")
    assert res.status_code == 201
    note_id = res.json()["id"]
    assert res.json()["status"] == "DRAFT"

    assert client.get(f"/delivery-notes/{note_id}", headers=owner["headers"]).status_code == 200
    res = client.put(f"/delivery-notes/{note_id}", json={"notes": "editado", "items": [{"quotation_item_id": item, "quantity": 20}]}, headers=owner["headers"])
    assert res.status_code == 200 and res.json()["total_units"] == 20
    assert client.get(f"/delivery-notes/{note_id}/pdf", headers=owner["headers"]).status_code == 200
    assert client.delete(f"/delivery-notes/{note_id}", headers=owner["headers"]).status_code == 204


def test_rejected_issue_does_not_assign_a_number_nor_count_as_delivered(owner, uncut):
    draft = create_note(owner["headers"], uncut["quotation_id"], [(uncut["item_ids"][0], 30)]).json()
    assert issue_note(owner["headers"], draft["id"]).status_code == 409

    note = client.get(f"/delivery-notes/{draft['id']}", headers=owner["headers"]).json()
    assert note["status"] == "DRAFT" and note["number"] is None and note["issued_at"] is None
    assert _sequence_rows() == 0  # ni siquiera se creó el contador de numeración
    status = delivery_status(owner["headers"], uncut["quotation_id"])
    assert (status["total_delivered"], status["total_pending"], status["state"]) == (0, 100, "NONE")
    assert status["cut_confirmed"] is False and status["items"][0]["cut_confirmed"] is False


def test_issue_succeeds_after_the_cut_is_confirmed_and_first_number_is_still_one(owner, uncut):
    """Borrador creado ANTES de confirmar el corte; el rechazo no consumió numeración."""
    draft = create_note(owner["headers"], uncut["quotation_id"], [(uncut["item_ids"][0], 30)]).json()
    assert issue_note(owner["headers"], draft["id"]).status_code == 409

    confirm_cut(owner["headers"], uncut, 0)

    res = issue_note(owner["headers"], draft["id"])
    assert res.status_code == 200, res.text
    assert res.json()["number"] == "R-000001"
    status = delivery_status(owner["headers"], uncut["quotation_id"])
    assert (status["total_delivered"], status["cut_confirmed"]) == (30, True)


def test_draft_created_after_the_cut_is_confirmed_issues_normally(owner, uncut):
    confirm_cut(owner["headers"], uncut, 0)
    draft = create_note(owner["headers"], uncut["quotation_id"], [(uncut["item_ids"][0], 5)]).json()
    assert issue_note(owner["headers"], draft["id"]).status_code == 200


# ───────────── qué cuenta como "corte confirmado" ─────────────


def test_an_active_reservation_is_not_a_confirmed_cut(owner, uncut):
    confirm_cut(owner["headers"], uncut, 0, confirm=False)  # reservada, sin cortar
    draft = create_note(owner["headers"], uncut["quotation_id"], [(uncut["item_ids"][0], 5)]).json()
    assert issue_note(owner["headers"], draft["id"]).status_code == 409


def test_a_released_reservation_is_not_a_confirmed_cut(owner, uncut):
    reservation_id = confirm_cut(owner["headers"], uncut, 0, confirm=False)
    res = client.post(f"/stock/reservations/{reservation_id}/release", headers=owner["headers"])
    assert res.status_code == 200, res.text
    draft = create_note(owner["headers"], uncut["quotation_id"], [(uncut["item_ids"][0], 5)]).json()
    assert issue_note(owner["headers"], draft["id"]).status_code == 409


def test_a_confirmed_cut_not_linked_to_the_item_does_not_count(owner, uncut):
    """Una reserva consumida sin quotation_item_id no se puede atribuir a ningún ítem: no se asume."""
    confirm_cut(owner["headers"], uncut, 0, link_item=False)
    draft = create_note(owner["headers"], uncut["quotation_id"], [(uncut["item_ids"][0], 5)]).json()
    assert issue_note(owner["headers"], draft["id"]).status_code == 409


def test_a_confirmed_cut_of_another_quotation_does_not_count(owner, uncut):
    other = make_quotation(owner["headers"], quantities=(10,), confirm_cut_for_all=True)
    assert delivery_status(owner["headers"], other["quotation_id"])["cut_confirmed"] is True
    draft = create_note(owner["headers"], uncut["quotation_id"], [(uncut["item_ids"][0], 5)]).json()
    assert issue_note(owner["headers"], draft["id"]).status_code == 409


def test_cut_confirmation_of_another_company_does_not_count(owner, uncut):
    other_headers, _ = register_company("otra@corte.com", "Otro Taller")
    make_quotation(other_headers, quantities=(10,), confirm_cut_for_all=True)
    draft = create_note(owner["headers"], uncut["quotation_id"], [(uncut["item_ids"][0], 5)]).json()
    assert issue_note(owner["headers"], draft["id"]).status_code == 409


# ───────────── cobertura parcial: se verifica por ítem, no se asume "todo terminado" ─────────────


def test_partial_cut_only_covers_the_items_that_were_cut(owner):
    q = make_quotation(owner["headers"], quantities=(10, 10), confirm_cut_for_all=False)
    confirm_cut(owner["headers"], q, 0)  # solo la pieza 1
    a, b = q["item_ids"]

    status = delivery_status(owner["headers"], q["quotation_id"])
    assert status["cut_confirmed"] is False  # la cotización completa NO está cortada
    assert [l["cut_confirmed"] for l in status["items"]] == [True, False]

    mixed = create_note(owner["headers"], q["quotation_id"], [(a, 3), (b, 3)]).json()
    res = issue_note(owner["headers"], mixed["id"])
    assert res.status_code == 409
    assert "Pieza 2" in res.json()["detail"] and "Pieza 1" not in res.json()["detail"]
    note = client.get(f"/delivery-notes/{mixed['id']}", headers=owner["headers"]).json()
    assert (note["cut_confirmed"], note["cut_pending_pieces"]) == (False, ["Pieza 2"])

    only_cut = create_note(owner["headers"], q["quotation_id"], [(a, 3)]).json()
    assert issue_note(owner["headers"], only_cut["id"]).status_code == 200

    confirm_cut(owner["headers"], q, 1)
    assert issue_note(owner["headers"], mixed["id"]).status_code == 200


def test_draft_read_exposes_cut_state_and_issued_note_does_not(owner, uncut):
    draft = create_note(owner["headers"], uncut["quotation_id"], [(uncut["item_ids"][0], 5)]).json()
    assert (draft["cut_confirmed"], draft["cut_pending_pieces"]) == (False, ["Pieza 1"])
    confirm_cut(owner["headers"], uncut, 0)
    again = client.get(f"/delivery-notes/{draft['id']}", headers=owner["headers"]).json()
    assert (again["cut_confirmed"], again["cut_pending_pieces"]) == (True, [])
    issued = issue_note(owner["headers"], draft["id"]).json()
    assert issued["cut_confirmed"] is None


# ───────────── no se puede evitar la regla por la API ─────────────


def test_the_rule_cannot_be_bypassed_by_any_api_call(owner, uncut):
    item = uncut["item_ids"][0]
    qid = uncut["quotation_id"]

    # intentar crear directamente como emitido / con número
    res = client.post(
        "/delivery-notes",
        json={"quotation_id": qid, "status": "ISSUED", "number": "R-000999", "issued_at": "2026-01-01T00:00:00",
              "items": [{"quotation_item_id": item, "quantity": 5}]},
        headers=owner["headers"],
    )
    assert res.status_code == 201
    assert (res.json()["status"], res.json()["number"]) == ("DRAFT", None)
    note_id = res.json()["id"]

    # intentar cambiar el estado vía PUT
    res = client.put(f"/delivery-notes/{note_id}", json={"status": "ISSUED", "number": "R-000999"}, headers=owner["headers"])
    assert res.status_code == 200
    assert (res.json()["status"], res.json()["number"]) == ("DRAFT", None)

    # no hay otro endpoint de transición: emitir sigue siendo 409, y anular un borrador también
    assert issue_note(owner["headers"], note_id).status_code == 409
    assert void_note(owner["headers"], note_id).status_code == 409

    # un empleado tampoco puede evitarla
    employee = add_employee(owner["headers"], owner["company_id"], "empleado@corte.com")
    assert issue_note(employee, note_id).status_code == 409

    status = delivery_status(owner["headers"], qid)
    assert status["total_delivered"] == 0 and _sequence_rows() == 0


# ───────────── interacción con el resto de las reglas ─────────────


def test_cancelled_or_not_accepted_quotation_still_reports_the_eligibility_error_first(owner):
    q = make_quotation(owner["headers"], quantities=(10,), confirm_cut_for_all=False)
    draft = create_note(owner["headers"], q["quotation_id"], [(q["item_ids"][0], 1)]).json()
    from tests._delivery_helpers import set_status

    assert set_status(owner["headers"], q["quotation_id"], "cancelled").status_code == 200
    res = issue_note(owner["headers"], draft["id"])
    assert res.status_code == 409 and "aceptadas" in res.json()["detail"]


def test_cut_rule_does_not_affect_partial_deliveries_or_voiding(owner):
    q = make_quotation(owner["headers"], quantities=(100,))  # corte confirmado
    item = q["item_ids"][0]
    first = create_note(owner["headers"], q["quotation_id"], [(item, 60)]).json()
    second = create_note(owner["headers"], q["quotation_id"], [(item, 60)]).json()
    assert issue_note(owner["headers"], first["id"]).status_code == 200
    res = issue_note(owner["headers"], second["id"])
    assert res.status_code == 409 and "pendientes" in res.json()["detail"]  # sobreentrega sigue vigente
    assert void_note(owner["headers"], first["id"]).status_code == 200
    assert issue_note(owner["headers"], second["id"]).status_code == 200


def test_a_voided_note_cannot_be_reissued_and_confirmed_cut_stays_confirmed(owner):
    q = make_quotation(owner["headers"], quantities=(10,))
    issued = issue_note(owner["headers"], create_note(owner["headers"], q["quotation_id"], [(q["item_ids"][0], 5)]).json()["id"]).json()
    void_note(owner["headers"], issued["id"])
    assert issue_note(owner["headers"], issued["id"]).status_code == 409
    assert delivery_status(owner["headers"], q["quotation_id"])["cut_confirmed"] is True  # el corte no se "des-confirma"


# ───────────── regla definitiva: solo se exige el corte de los ítems INCLUIDOS en el remito ─────────────


def test_abc_example_only_the_items_included_need_a_confirmed_cut(owner):
    """A (100, cortada), B (50, sin cortar), C (20, cortada)."""
    q = make_quotation(owner["headers"], quantities=(100, 50, 20), confirm_cut_for_all=False)
    a, b, c = q["item_ids"]
    confirm_cut(owner["headers"], q, 0)
    confirm_cut(owner["headers"], q, 2)

    status = delivery_status(owner["headers"], q["quotation_id"])
    assert [l["cut_confirmed"] for l in status["items"]] == [True, False, True]

    # A + C: se puede emitir aunque B esté pendiente
    ac = create_note(owner["headers"], q["quotation_id"], [(a, 100), (c, 20)]).json()
    res = issue_note(owner["headers"], ac["id"])
    assert res.status_code == 200, res.text
    assert res.json()["number"] == "R-000001"

    # B sola, o B junto con otra pieza cortada: se rechaza y no consume número
    only_b = create_note(owner["headers"], q["quotation_id"], [(b, 10)]).json()
    res = issue_note(owner["headers"], only_b["id"])
    assert res.status_code == 409 and res.json()["detail"].startswith(CUT_MESSAGE) and "Pieza 2" in res.json()["detail"]
    assert client.get(f"/delivery-notes/{only_b['id']}", headers=owner["headers"]).json()["number"] is None

    # la cotización queda parcialmente entregada: 120 de 170
    status = delivery_status(owner["headers"], q["quotation_id"])
    assert (status["total_delivered"], status["total_pending"], status["state"]) == (120, 50, "PARTIAL")

    # cuando se corta B, el borrador de B se puede emitir y recibe el número siguiente
    confirm_cut(owner["headers"], q, 1)
    res = issue_note(owner["headers"], only_b["id"])
    assert res.status_code == 200 and res.json()["number"] == "R-000002"


def test_voiding_one_of_several_issued_notes_only_frees_its_own_quantity(owner):
    q = make_quotation(owner["headers"], quantities=(100,))
    item = q["item_ids"][0]
    notes = [issue_note(owner["headers"], create_note(owner["headers"], q["quotation_id"], [(item, n)]).json()["id"]).json() for n in (40, 35, 25)]
    assert [n["number"] for n in notes] == ["R-000001", "R-000002", "R-000003"]
    assert delivery_status(owner["headers"], q["quotation_id"])["state"] == "COMPLETE"

    assert void_note(owner["headers"], notes[1]["id"], "se entregó de menos").status_code == 200
    status = delivery_status(owner["headers"], q["quotation_id"])
    assert (status["total_delivered"], status["total_pending"], status["state"]) == (65, 35, "PARTIAL")
    states = {n["number"]: client.get(f"/delivery-notes/{n['id']}", headers=owner["headers"]).json()["status"] for n in notes}
    assert states == {"R-000001": "ISSUED", "R-000002": "VOIDED", "R-000003": "ISSUED"}

    # una anulación repetida no tiene efecto doble
    assert void_note(owner["headers"], notes[1]["id"], "otra vez").status_code == 409
    assert delivery_status(owner["headers"], q["quotation_id"])["total_delivered"] == 65
    # el saldo liberado se puede volver a entregar, con número nuevo
    again = issue_note(owner["headers"], create_note(owner["headers"], q["quotation_id"], [(item, 35)]).json()["id"]).json()
    assert again["number"] == "R-000004"


def test_a_concurrent_item_change_while_saving_a_draft_is_a_clean_409_not_a_500(owner):
    """update_draft atrapa el IntegrityError del flush (como create_draft)."""
    from sqlalchemy.exc import IntegrityError

    from app.services import delivery_notes as service

    q = make_quotation(owner["headers"], quantities=(10, 10), confirm_cut_for_all=False)
    note_id = create_note(owner["headers"], q["quotation_id"], [(q["item_ids"][0], 1)]).json()["id"]
    db = SessionLocal()
    try:
        def boom():
            raise IntegrityError("flush", {}, Exception("fk"))

        db.flush = boom  # type: ignore[method-assign]
        with pytest.raises(service.DeliveryNoteError) as caught:
            service.update_draft(
                db, company_id=owner["company_id"], note_id=note_id, notes=None, notes_provided=False,
                lines=[(q["item_ids"][0], 2), (q["item_ids"][1], 2)],
            )
        assert caught.value.kind == service.CONFLICT
    finally:
        db.close()
