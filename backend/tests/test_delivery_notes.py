"""Módulo de remitos: funcionalidad, seguridad e integridad (SQLite).

La concurrencia real (carreras entre transacciones) se prueba contra Postgres
en test_delivery_notes_concurrency_postgres.py."""

import re
from pathlib import Path

import pytest
from reportlab import rl_config
from sqlalchemy.exc import IntegrityError

from app.db.init_db import init_db
from app.db.session import SessionLocal, engine
from app.models.delivery_note import DeliveryNote, DeliveryNoteItem
from tests._delivery_helpers import (
    add_employee,
    client,
    create_note,
    delivery_status,
    issue_new,
    issue_note,
    make_quotation,
    register_company,
    set_status,
    void_note,
)


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
    headers, company_id = register_company("owner@remitos.com", "Taller Uno")
    return {"headers": headers, "company_id": company_id}


@pytest.fixture
def quote(owner):
    return make_quotation(owner["headers"], quantities=(100,))


# ───────────────────────── funcionalidad ─────────────────────────


def test_create_valid_draft_snapshots_client_and_lines(owner, quote):
    res = create_note(owner["headers"], quote["quotation_id"], [(quote["item_ids"][0], 40)], notes="Retira Juan")
    assert res.status_code == 201, res.text
    note = res.json()
    assert note["status"] == "DRAFT"
    assert note["number"] is None
    assert note["client_name"] == "Cliente Remitos"
    assert note["quotation_number"].startswith("COT-")
    assert note["notes"] == "Retira Juan"
    assert note["total_units"] == 40
    line = note["items"][0]
    assert (line["piece_name"], line["quantity"], line["unit"]) == ("Pieza 1", 40, "un")


def test_get_list_and_quotation_history(owner, quote):
    note_id = create_note(owner["headers"], quote["quotation_id"], [(quote["item_ids"][0], 10)]).json()["id"]

    res = client.get(f"/delivery-notes/{note_id}", headers=owner["headers"])
    assert res.status_code == 200 and res.json()["id"] == note_id

    listed = client.get("/delivery-notes", headers=owner["headers"]).json()
    assert [n["id"] for n in listed] == [note_id]
    assert listed[0]["client_name"] == "Cliente Remitos" and listed[0]["total_units"] == 10

    assert client.get("/delivery-notes?status=ISSUED", headers=owner["headers"]).json() == []
    assert client.get("/delivery-notes?status=BOGUS", headers=owner["headers"]).status_code == 400

    history = client.get(f"/delivery-notes/quotation/{quote['quotation_id']}", headers=owner["headers"]).json()
    assert [n["id"] for n in history] == [note_id]


def test_issue_assigns_number_date_and_user(owner, quote):
    note_id = create_note(owner["headers"], quote["quotation_id"], [(quote["item_ids"][0], 40)]).json()["id"]
    res = issue_note(owner["headers"], note_id)
    assert res.status_code == 200, res.text
    note = res.json()
    assert note["status"] == "ISSUED"
    assert note["number"] == "R-000001"
    assert note["issue_date"] is not None and note["issued_at"] is not None
    assert note["issued_by_id"] is not None


def test_draft_does_not_count_as_delivered(owner, quote):
    create_note(owner["headers"], quote["quotation_id"], [(quote["item_ids"][0], 40)])
    status = delivery_status(owner["headers"], quote["quotation_id"])
    assert (status["total_quoted"], status["total_delivered"], status["total_pending"], status["state"]) == (100, 0, 100, "NONE")
    assert status["client_name"] == "Cliente Remitos"


def test_partial_then_complete_delivery_100_40_35_25(owner, quote):
    item = quote["item_ids"][0]
    qid = quote["quotation_id"]

    issue_new(owner["headers"], qid, [(item, 40)])
    s = delivery_status(owner["headers"], qid)
    assert (s["total_delivered"], s["total_pending"], s["state"]) == (40, 60, "PARTIAL")

    issue_new(owner["headers"], qid, [(item, 35)])
    s = delivery_status(owner["headers"], qid)
    assert (s["total_delivered"], s["total_pending"], s["state"]) == (75, 25, "PARTIAL")
    assert s["items"][0]["quoted"] == 100 and s["items"][0]["pending"] == 25

    third = issue_new(owner["headers"], qid, [(item, 25)])
    assert third["number"] == "R-000003"
    s = delivery_status(owner["headers"], qid)
    assert (s["total_delivered"], s["total_pending"], s["state"]) == (100, 0, "COMPLETE")

    history = client.get(f"/delivery-notes/quotation/{qid}", headers=owner["headers"]).json()
    assert sorted(n["number"] for n in history) == ["R-000001", "R-000002", "R-000003"]

    res = create_note(owner["headers"], qid, [(item, 1)])
    assert res.status_code == 400


def test_multiple_items_keep_reference_to_each_line(owner):
    q = make_quotation(owner["headers"], quantities=(10, 10, 5))
    note = issue_new(owner["headers"], q["quotation_id"], [(q["item_ids"][0], 4), (q["item_ids"][2], 5)])
    assert {l["quotation_item_id"]: l["quantity"] for l in note["items"]} == {q["item_ids"][0]: 4, q["item_ids"][2]: 5}
    s = {l["quotation_item_id"]: l for l in delivery_status(owner["headers"], q["quotation_id"])["items"]}
    assert s[q["item_ids"][0]]["pending"] == 6
    assert s[q["item_ids"][1]]["pending"] == 10
    assert s[q["item_ids"][2]]["pending"] == 0


def test_update_draft_changes_lines_and_notes(owner):
    q = make_quotation(owner["headers"], quantities=(10, 10))
    note_id = create_note(owner["headers"], q["quotation_id"], [(q["item_ids"][0], 3)]).json()["id"]
    res = client.put(
        f"/delivery-notes/{note_id}",
        json={"notes": "Nuevo", "items": [{"quotation_item_id": q["item_ids"][0], "quantity": 7}, {"quotation_item_id": q["item_ids"][1], "quantity": 2}]},
        headers=owner["headers"],
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["notes"] == "Nuevo" and body["total_units"] == 9 and len(body["items"]) == 2

    res = client.put(f"/delivery-notes/{note_id}", json={"notes": None}, headers=owner["headers"])
    assert res.json()["notes"] is None and res.json()["total_units"] == 9

    res = client.put(f"/delivery-notes/{note_id}", json={"items": [{"quotation_item_id": q["item_ids"][1], "quantity": 1}]}, headers=owner["headers"])
    assert [l["quotation_item_id"] for l in res.json()["items"]] == [q["item_ids"][1]]


def test_delete_draft_and_cannot_delete_issued(owner, quote):
    item = quote["item_ids"][0]
    draft_id = create_note(owner["headers"], quote["quotation_id"], [(item, 1)]).json()["id"]
    assert client.delete(f"/delivery-notes/{draft_id}", headers=owner["headers"]).status_code == 204
    assert client.get(f"/delivery-notes/{draft_id}", headers=owner["headers"]).status_code == 404

    issued = issue_new(owner["headers"], quote["quotation_id"], [(item, 1)])
    res = client.delete(f"/delivery-notes/{issued['id']}", headers=owner["headers"])
    assert res.status_code == 409
    assert client.get(f"/delivery-notes/{issued['id']}", headers=owner["headers"]).status_code == 200


def test_void_restores_pending_and_keeps_the_document(owner, quote):
    item = quote["item_ids"][0]
    qid = quote["quotation_id"]
    first = issue_new(owner["headers"], qid, [(item, 60)])
    assert delivery_status(owner["headers"], qid)["total_pending"] == 40

    res = void_note(owner["headers"], first["id"], "Se cargó mal la cantidad")
    assert res.status_code == 200, res.text
    voided = res.json()
    assert voided["status"] == "VOIDED"
    assert voided["void_reason"] == "Se cargó mal la cantidad"
    assert voided["voided_at"] is not None and voided["voided_by_id"] is not None
    assert voided["number"] == "R-000001" and voided["items"][0]["quantity"] == 60

    s = delivery_status(owner["headers"], qid)
    assert (s["total_delivered"], s["total_pending"], s["state"]) == (0, 100, "NONE")

    again = issue_new(owner["headers"], qid, [(item, 100)])
    assert again["number"] == "R-000002"  # el número anulado no se reutiliza
    assert client.get(f"/delivery-notes/{first['id']}", headers=owner["headers"]).json()["status"] == "VOIDED"


def test_void_requires_a_reason(owner, quote):
    issued = issue_new(owner["headers"], quote["quotation_id"], [(quote["item_ids"][0], 5)])
    for body in ({}, {"reason": ""}, {"reason": "  "}, {"reason": "ab"}):
        res = client.post(f"/delivery-notes/{issued['id']}/void", json=body, headers=owner["headers"])
        assert res.status_code == 422, body
    assert client.get(f"/delivery-notes/{issued['id']}", headers=owner["headers"]).json()["status"] == "ISSUED"


def test_void_events_are_logged_in_the_quotation_history(owner, quote):
    issued = issue_new(owner["headers"], quote["quotation_id"], [(quote["item_ids"][0], 5)])
    void_note(owner["headers"], issued["id"], "Motivo de prueba")
    events = client.get(f"/quotations/{quote['quotation_id']}/events", headers=owner["headers"]).json()
    descriptions = " | ".join(e["description"] for e in events)
    assert "R-000001 emitido" in descriptions and "R-000001 anulado: Motivo de prueba" in descriptions


# ───────────────────────── PDF ─────────────────────────


@pytest.fixture
def readable_pdf(monkeypatch):
    monkeypatch.setattr(rl_config, "pageCompression", 0)


def test_pdf_of_issued_note_has_data_signatures_and_no_costs(owner, quote, readable_pdf):
    note_id = create_note(owner["headers"], quote["quotation_id"], [(quote["item_ids"][0], 12)], notes="Entregar en portería").json()["id"]
    issue_note(owner["headers"], note_id)
    res = client.get(f"/delivery-notes/{note_id}/pdf", headers=owner["headers"])
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert "remito_R-000001.pdf" in res.headers["content-disposition"]
    body = res.content
    assert body.startswith(b"%PDF")
    for expected in (b"REMITO", b"R-000001", b"Cliente Remitos", b"Pieza 1", b"Entregar en porter", b"Firma", b"Aclaraci", b"Fecha de recepci"):
        assert expected in body, expected
    assert b"BORRADOR" not in body and b"ANULADO" not in body
    lowered = body.lower()
    for forbidden in (b"costo", b"margen", b"precio", b"total ars", b"$"):
        assert forbidden not in lowered, forbidden


def test_pdf_of_draft_is_clearly_marked(owner, quote, readable_pdf):
    note_id = create_note(owner["headers"], quote["quotation_id"], [(quote["item_ids"][0], 3)]).json()["id"]
    res = client.get(f"/delivery-notes/{note_id}/pdf", headers=owner["headers"])
    assert res.status_code == 200
    assert b"BORRADOR" in res.content and b"SIN N" in res.content
    assert "remito_borrador_" in res.headers["content-disposition"]


def test_pdf_of_voided_note_is_marked_and_shows_reason(owner, quote, readable_pdf):
    issued = issue_new(owner["headers"], quote["quotation_id"], [(quote["item_ids"][0], 3)])
    void_note(owner["headers"], issued["id"], "Remito duplicado")
    res = client.get(f"/delivery-notes/{issued['id']}/pdf", headers=owner["headers"])
    assert b"ANULADO" in res.content and b"Remito duplicado" in res.content


def test_pdf_with_many_lines_spans_pages_and_every_sheet_identifies_the_document(owner, readable_pdf):
    """Regresión de la auditoría visual: las hojas siguientes quedaban sin número de remito (y el encabezado
    de la tabla era invisible). Cada hoja debe llevar identificación y "Hoja i de n"."""
    from app.models.quotation_item import QuotationItem

    q = make_quotation(owner["headers"], quantities=(5,), confirm_cut_for_all=False)
    db = SessionLocal()
    try:
        base = db.query(QuotationItem).filter(QuotationItem.id == q["item_ids"][0]).one()
        for _ in range(50):
            db.add(QuotationItem(quotation_id=base.quotation_id, piece_id=base.piece_id, material_id=base.material_id, quantity=3))
        db.commit()
        item_ids = [i.id for i in db.query(QuotationItem).filter(QuotationItem.quotation_id == base.quotation_id).all()]
    finally:
        db.close()
    note_id = create_note(owner["headers"], q["quotation_id"], [(i, 1) for i in item_ids]).json()["id"]

    body = client.get(f"/delivery-notes/{note_id}/pdf", headers=owner["headers"]).content
    pages = len(re.findall(rb"/Type\s*/Page[^s]", body))  # páginas (no el nodo /Pages)
    assert pages >= 2
    for n in range(1, pages + 1):
        assert f"Hoja {n} de {pages}".encode() in body
    assert body.count(rb"Remito \(borrador\)") >= pages  # pie de cada hoja (+ el título del documento)
    assert body.count(b"Descripci") >= 2  # el encabezado de la tabla se repite en cada hoja que contiene filas


def test_pdf_renders_with_default_compression(owner, quote):
    note_id = create_note(owner["headers"], quote["quotation_id"], [(quote["item_ids"][0], 3)]).json()["id"]
    res = client.get(f"/delivery-notes/{note_id}/pdf", headers=owner["headers"])
    assert res.status_code == 200 and res.content.startswith(b"%PDF") and len(res.content) > 1500


# ───────────────────────── snapshot histórico ─────────────────────────


def test_issued_note_keeps_snapshot_when_client_or_piece_change(owner, quote):
    issued = issue_new(owner["headers"], quote["quotation_id"], [(quote["item_ids"][0], 5)])
    client.put(f"/clients/{quote['client_id']}", json={"name": "Nombre Nuevo SA", "address": "Otra 123"}, headers=owner["headers"])
    client.put(f"/pieces/{quote['piece_ids'][0]}", json={"name": "Renombrada", "description": "Otra"}, headers=owner["headers"])
    note = client.get(f"/delivery-notes/{issued['id']}", headers=owner["headers"]).json()
    assert note["client_name"] == "Cliente Remitos"
    assert note["items"][0]["piece_name"] == "Pieza 1"
    assert note["client_address"] != "Otra 123"


def test_draft_is_resnapshotted_at_issue_time(owner, quote):
    note_id = create_note(owner["headers"], quote["quotation_id"], [(quote["item_ids"][0], 5)]).json()["id"]
    client.put(f"/clients/{quote['client_id']}", json={"name": "Cliente Renombrado"}, headers=owner["headers"])
    assert issue_note(owner["headers"], note_id).json()["client_name"] == "Cliente Renombrado"


# ───────────────────────── seguridad ─────────────────────────


def test_requires_authentication(owner, quote):
    assert client.get("/delivery-notes").status_code in (401, 403)
    assert client.post("/delivery-notes", json={}).status_code in (401, 403)


_ALL_ENDPOINTS = [
    ("get", "/delivery-notes", None),
    ("post", "/delivery-notes", {"quotation_id": 1, "items": [{"quotation_item_id": 1, "quantity": 1}]}),
    ("get", "/delivery-notes/1", None),
    ("put", "/delivery-notes/1", {"notes": "x"}),
    ("delete", "/delivery-notes/1", None),
    ("post", "/delivery-notes/1/issue", None),
    ("post", "/delivery-notes/1/void", {"reason": "sin sesión"}),
    ("get", "/delivery-notes/1/pdf", None),
    ("get", "/delivery-notes/quotation/1", None),
    ("get", "/delivery-notes/quotation/1/status", None),
]


@pytest.mark.parametrize("method,path,body", _ALL_ENDPOINTS)
def test_every_endpoint_rejects_unauthenticated_requests(owner, quote, method, path, body):
    kwargs = {"json": body} if body is not None else {}
    assert getattr(client, method)(path, **kwargs).status_code in (401, 403)


@pytest.mark.parametrize("method,path,body", _ALL_ENDPOINTS)
def test_every_endpoint_rejects_a_company_header_the_user_does_not_belong_to(owner, quote, method, path, body):
    other_headers, other_company_id = register_company("ajena@empresa.com", "Taller Ajeno")
    hijack = {"Authorization": other_headers["Authorization"], "X-Company-Id": str(owner["company_id"])}
    kwargs = {"json": body, "headers": hijack} if body is not None else {"headers": hijack}
    assert getattr(client, method)(path, **kwargs).status_code == 403


@pytest.mark.parametrize("method,path,body", [
    ("get", "/delivery-notes/99999", None),
    ("put", "/delivery-notes/99999", {"notes": "x"}),
    ("delete", "/delivery-notes/99999", None),
    ("post", "/delivery-notes/99999/issue", None),
    ("post", "/delivery-notes/99999/void", {"reason": "no existe"}),
    ("get", "/delivery-notes/99999/pdf", None),
    ("get", "/delivery-notes/quotation/99999", None),
    ("get", "/delivery-notes/quotation/99999/status", None),
])
def test_nonexistent_ids_return_404(owner, method, path, body):
    kwargs = {"json": body} if body is not None else {}
    assert getattr(client, method)(path, headers=owner["headers"], **kwargs).status_code == 404


def test_nonexistent_quotation_on_create_is_404(owner):
    res = client.post("/delivery-notes", json={"quotation_id": 99999, "items": [{"quotation_item_id": 1, "quantity": 1}]}, headers=owner["headers"])
    assert res.status_code == 404


def test_employee_can_create_and_issue_but_not_void(owner, quote):
    employee = add_employee(owner["headers"], owner["company_id"], "empleado@remitos.com")
    item = quote["item_ids"][0]
    res = create_note(employee, quote["quotation_id"], [(item, 5)])
    assert res.status_code == 201
    issued = issue_note(employee, res.json()["id"])
    assert issued.status_code == 200
    assert void_note(employee, issued.json()["id"]).status_code == 403
    assert client.get(f"/delivery-notes/{issued.json()['id']}", headers=employee).json()["status"] == "ISSUED"
    assert void_note(owner["headers"], issued.json()["id"]).status_code == 200


def test_cannot_use_a_quotation_or_note_from_another_company(owner, quote):
    other_headers, _ = register_company("otra@empresa.com", "Taller Dos")
    other_quote = make_quotation(other_headers, quantities=(10,))
    mine = issue_new(owner["headers"], quote["quotation_id"], [(quote["item_ids"][0], 5)])
    draft = create_note(owner["headers"], quote["quotation_id"], [(quote["item_ids"][0], 1)]).json()

    # crear sobre una cotización ajena
    assert create_note(other_headers, quote["quotation_id"], [(quote["item_ids"][0], 1)]).status_code == 404
    assert create_note(owner["headers"], other_quote["quotation_id"], [(other_quote["item_ids"][0], 1)]).status_code == 404

    # acceder / operar sobre remitos ajenos
    for method, path, body in (
        ("get", f"/delivery-notes/{mine['id']}", None),
        ("get", f"/delivery-notes/{mine['id']}/pdf", None),
        ("put", f"/delivery-notes/{draft['id']}", {"notes": "x"}),
        ("delete", f"/delivery-notes/{draft['id']}", None),
        ("post", f"/delivery-notes/{draft['id']}/issue", None),
        ("post", f"/delivery-notes/{mine['id']}/void", {"reason": "intento ajeno"}),
        ("get", f"/delivery-notes/quotation/{quote['quotation_id']}", None),
        ("get", f"/delivery-notes/quotation/{quote['quotation_id']}/status", None),
    ):
        kwargs = {"headers": other_headers}
        if body is not None:
            kwargs["json"] = body
        res = getattr(client, method)(path, **kwargs)
        assert res.status_code == 404, (method, path, res.status_code)

    assert client.get("/delivery-notes", headers=other_headers).json() == []
    assert client.get(f"/delivery-notes/{mine['id']}", headers=owner["headers"]).json()["status"] == "ISSUED"


def test_company_id_in_the_payload_is_ignored(owner, quote):
    other_headers, other_company_id = register_company("otra2@empresa.com", "Taller Tres")
    res = client.post(
        "/delivery-notes",
        json={"quotation_id": quote["quotation_id"], "company_id": other_company_id, "client_id": 9999,
              "items": [{"quotation_item_id": quote["item_ids"][0], "quantity": 1}]},
        headers=owner["headers"],
    )
    assert res.status_code == 201
    assert res.json()["company_id"] == owner["company_id"]
    assert res.json()["client_id"] == quote["client_id"]


def test_items_from_another_quotation_or_company_are_rejected(owner, quote):
    other_quote_same_company = make_quotation(owner["headers"], quantities=(10,))
    res = create_note(owner["headers"], quote["quotation_id"], [(other_quote_same_company["item_ids"][0], 1)])
    assert res.status_code == 400 and "no pertenece" in res.json()["detail"]

    other_headers, _ = register_company("otra3@empresa.com", "Taller Cuatro")
    foreign = make_quotation(other_headers, quantities=(10,))
    res = create_note(owner["headers"], quote["quotation_id"], [(foreign["item_ids"][0], 1)])
    assert res.status_code == 400

    res = create_note(owner["headers"], quote["quotation_id"], [(999999, 1)])
    assert res.status_code == 400


def test_numbering_is_independent_per_company(owner, quote):
    other_headers, _ = register_company("otra4@empresa.com", "Taller Cinco")
    other = make_quotation(other_headers, quantities=(10,))
    a = issue_new(owner["headers"], quote["quotation_id"], [(quote["item_ids"][0], 1)])
    b = issue_new(other_headers, other["quotation_id"], [(other["item_ids"][0], 1)])
    assert a["number"] == "R-000001" and b["number"] == "R-000001"
    assert issue_new(owner["headers"], quote["quotation_id"], [(quote["item_ids"][0], 1)])["number"] == "R-000002"


# ───────────────────────── integridad ─────────────────────────


@pytest.mark.parametrize("bad", [-5, 0, "abc", 1.5, None])
def test_invalid_quantities_are_rejected(owner, quote, bad):
    res = client.post(
        "/delivery-notes",
        json={"quotation_id": quote["quotation_id"], "items": [{"quotation_item_id": quote["item_ids"][0], "quantity": bad}]},
        headers=owner["headers"],
    )
    assert res.status_code == 422, bad


def test_empty_or_duplicate_lines_are_rejected(owner, quote):
    item = quote["item_ids"][0]
    assert client.post("/delivery-notes", json={"quotation_id": quote["quotation_id"], "items": []}, headers=owner["headers"]).status_code == 422
    res = client.post(
        "/delivery-notes",
        json={"quotation_id": quote["quotation_id"], "items": [{"quotation_item_id": item, "quantity": 1}, {"quotation_item_id": item, "quantity": 2}]},
        headers=owner["headers"],
    )
    assert res.status_code == 422
    draft = create_note(owner["headers"], quote["quotation_id"], [(item, 1)]).json()
    assert client.put(f"/delivery-notes/{draft['id']}", json={"items": []}, headers=owner["headers"]).status_code == 422


def test_over_delivery_is_rejected_when_creating_and_updating(owner, quote):
    item = quote["item_ids"][0]
    res = create_note(owner["headers"], quote["quotation_id"], [(item, 101)])
    assert res.status_code == 400 and "pendientes" in res.json()["detail"]

    issue_new(owner["headers"], quote["quotation_id"], [(item, 90)])
    assert create_note(owner["headers"], quote["quotation_id"], [(item, 11)]).status_code == 400
    draft = create_note(owner["headers"], quote["quotation_id"], [(item, 10)])
    assert draft.status_code == 201
    assert client.put(f"/delivery-notes/{draft.json()['id']}", json={"items": [{"quotation_item_id": item, "quantity": 11}]}, headers=owner["headers"]).status_code == 400


def test_over_delivery_through_two_drafts_is_stopped_at_issue(owner, quote):
    """Dos borradores válidos por separado (60 + 60 de 100): el segundo no puede emitirse."""
    item = quote["item_ids"][0]
    first = create_note(owner["headers"], quote["quotation_id"], [(item, 60)]).json()
    second = create_note(owner["headers"], quote["quotation_id"], [(item, 60)]).json()
    assert issue_note(owner["headers"], first["id"]).status_code == 200
    res = issue_note(owner["headers"], second["id"])
    assert res.status_code == 409 and "pendientes" in res.json()["detail"]
    assert delivery_status(owner["headers"], quote["quotation_id"])["total_delivered"] == 60
    still_draft = client.get(f"/delivery-notes/{second['id']}", headers=owner["headers"]).json()
    assert still_draft["status"] == "DRAFT" and still_draft["number"] is None


def test_voiding_the_first_makes_room_for_the_blocked_second(owner, quote):
    item = quote["item_ids"][0]
    first = create_note(owner["headers"], quote["quotation_id"], [(item, 60)]).json()
    second = create_note(owner["headers"], quote["quotation_id"], [(item, 60)]).json()
    issue_note(owner["headers"], first["id"])
    assert issue_note(owner["headers"], second["id"]).status_code == 409
    void_note(owner["headers"], first["id"])
    assert issue_note(owner["headers"], second["id"]).status_code == 200


def test_double_issue_and_double_void_are_rejected(owner, quote):
    issued = issue_new(owner["headers"], quote["quotation_id"], [(quote["item_ids"][0], 5)])
    assert issue_note(owner["headers"], issued["id"]).status_code == 409
    assert void_note(owner["headers"], issued["id"]).status_code == 200
    assert void_note(owner["headers"], issued["id"]).status_code == 409
    assert issue_note(owner["headers"], issued["id"]).status_code == 409
    assert delivery_status(owner["headers"], quote["quotation_id"])["total_delivered"] == 0


def test_a_draft_cannot_be_voided(owner, quote):
    draft = create_note(owner["headers"], quote["quotation_id"], [(quote["item_ids"][0], 5)]).json()
    assert void_note(owner["headers"], draft["id"]).status_code == 409


def test_issued_and_voided_notes_are_read_only(owner, quote):
    item = quote["item_ids"][0]
    issued = issue_new(owner["headers"], quote["quotation_id"], [(item, 5)])
    body = {"notes": "cambio silencioso", "items": [{"quotation_item_id": item, "quantity": 99}]}
    assert client.put(f"/delivery-notes/{issued['id']}", json=body, headers=owner["headers"]).status_code == 409
    void_note(owner["headers"], issued["id"])
    assert client.put(f"/delivery-notes/{issued['id']}", json=body, headers=owner["headers"]).status_code == 409
    note = client.get(f"/delivery-notes/{issued['id']}", headers=owner["headers"]).json()
    assert note["notes"] is None and note["items"][0]["quantity"] == 5


@pytest.mark.parametrize("status", ["draft", "sent", "cancelled"])
def test_only_accepted_quotations_are_eligible(owner, status):
    q = make_quotation(owner["headers"], quantities=(10,), status=status)
    res = create_note(owner["headers"], q["quotation_id"], [(q["item_ids"][0], 1)])
    assert res.status_code == 409 and "aceptadas" in res.json()["detail"]
    s = delivery_status(owner["headers"], q["quotation_id"])
    assert s["eligible"] is False and s["ineligible_reason"]


def test_accepted_quotation_is_eligible(owner, quote):
    assert delivery_status(owner["headers"], quote["quotation_id"])["eligible"] is True


def test_draft_cannot_be_issued_after_the_quotation_is_cancelled(owner):
    # Sin corte confirmado la cotización todavía se puede cancelar (con el corte hecho, stock lo impide).
    quote = make_quotation(owner["headers"], quantities=(100,), confirm_cut_for_all=False)
    draft = create_note(owner["headers"], quote["quotation_id"], [(quote["item_ids"][0], 5)]).json()
    assert set_status(owner["headers"], quote["quotation_id"], "cancelled").status_code == 200
    res = issue_note(owner["headers"], draft["id"])
    assert res.status_code == 409 and "aceptadas" in res.json()["detail"]


def test_quotation_with_issued_notes_cannot_be_cancelled_even_after_voiding(owner, quote):
    """Un remito emitido exige corte confirmado, y una cotización con corte confirmado no puede
    cancelarse (regla de stock existente): las dos guardas se refuerzan entre sí."""
    issued = issue_new(owner["headers"], quote["quotation_id"], [(quote["item_ids"][0], 5)])
    res = set_status(owner["headers"], quote["quotation_id"], "cancelled")
    assert res.status_code == 409 and "remitos emitidos" in res.json()["detail"]
    assert client.get(f"/quotations/{quote['quotation_id']}", headers=owner["headers"]).json()["status"] == "accepted"
    void_note(owner["headers"], issued["id"])
    res = set_status(owner["headers"], quote["quotation_id"], "cancelled")
    assert res.status_code == 409 and "corte" in res.json()["detail"]


def test_quotation_item_referenced_by_a_note_cannot_be_deleted(owner):
    q = make_quotation(owner["headers"], quantities=(10, 10))
    issue_new(owner["headers"], q["quotation_id"], [(q["item_ids"][0], 5)])
    res = client.delete(f"/quotation-items/{q['item_ids'][0]}", headers=owner["headers"])
    assert res.status_code == 409 and "remitos" in res.json()["detail"]
    assert client.delete(f"/quotation-items/{q['item_ids'][1]}", headers=owner["headers"]).status_code == 204


def test_database_rejects_zero_quantity_and_duplicate_numbers(owner, quote):
    issued = issue_new(owner["headers"], quote["quotation_id"], [(quote["item_ids"][0], 5)])
    db = SessionLocal()
    try:
        db.add(DeliveryNoteItem(delivery_note_id=issued["id"], quotation_item_id=quote["item_ids"][0],
                                piece_name="x", quantity=0, unit="un"))
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()

        base = db.query(DeliveryNote).filter(DeliveryNote.id == issued["id"]).one()
        db.add(DeliveryNote(company_id=base.company_id, quotation_id=base.quotation_id, client_id=base.client_id,
                            number=base.number, status="ISSUED", quotation_number="x", client_name="x"))
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()

        db.add(DeliveryNote(company_id=base.company_id, quotation_id=base.quotation_id, client_id=base.client_id,
                            number=None, status="BOGUS", quotation_number="x", client_name="x"))
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()
    finally:
        db.close()


def test_many_drafts_without_number_do_not_collide(owner, quote):
    for _ in range(3):
        assert create_note(owner["headers"], quote["quotation_id"], [(quote["item_ids"][0], 1)]).status_code == 201
