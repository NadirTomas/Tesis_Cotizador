"""Helpers compartidos por los tests de remitos (SQLite y Postgres real).

No resetean la base: cada archivo decide cómo aislarse."""

from fastapi.testclient import TestClient

from app.main import app
from tests._dates import issue_iso
from tests.test_quotation_delete import (
    _create_client_record,
    _create_material,
    _create_machine_config,
    _create_piece_with_dxf,
    _create_quotation,
    _register_and_create_company,
)

client = TestClient(app)


def register_company(email: str, company_name: str) -> tuple[dict, int]:
    return _register_and_create_company(email, company_name)


def add_employee(owner_headers: dict, company_id: int, email: str) -> dict:
    res = client.post(
        f"/companies/{company_id}/members",
        json={"email": email, "password": "Password1!", "role": "employee"},
        headers=owner_headers,
    )
    assert res.status_code == 201, res.text
    token = client.post("/auth/login", json={"email": email, "password": "Password1!"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}", "X-Company-Id": str(company_id)}


def set_status(headers: dict, quotation_id: int, status: str):
    return client.patch(f"/quotations/{quotation_id}/status", json={"status": status}, headers=headers)


def confirm_cut(
    headers: dict, quotation: dict, index: int = 0, *, confirm: bool = True, link_item: bool = True
) -> int:
    """Reserva una chapa para el ítem `index` de la cotización y (por defecto) confirma el corte.

    Es el flujo real (reserve -> confirm-cut); no hay una bandera aparte. confirm=False deja la
    reserva ACTIVE; link_item=False la crea sin quotation_item_id. Devuelve el id de la reserva."""
    res = client.post(
        "/stock",
        json={"material_id": quotation["material_id"], "stock_type": "FULL_SHEET", "width_mm": 400, "height_mm": 400},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    stock_id = res.json()["id"]
    res = client.post(
        f"/stock/{stock_id}/reserve",
        json={
            "piece_id": quotation["piece_ids"][index],
            "material_id": quotation["material_id"],
            "quotation_id": quotation["quotation_id"],
            **({"quotation_item_id": quotation["item_ids"][index]} if link_item else {}),
        },
        headers=headers,
    )
    assert res.status_code == 200, res.text
    reservation_id = res.json()["id"]
    if confirm:
        res = client.post(f"/stock/reservations/{reservation_id}/confirm-cut", headers=headers)
        assert res.status_code == 200, res.text
    return reservation_id


def make_quotation(
    headers: dict,
    quantities=(100,),
    *,
    status: str | None = "accepted",
    confirm_cut_for_all: bool = True,
) -> dict:
    """Crea cliente, material, máquina, piezas, cotización e ítems (uno por cantidad).

    status="accepted" (por defecto) la lleva por draft -> sent -> accepted. Si la cotización queda
    aceptada, por defecto también se confirma el corte de TODOS sus ítems (condición para emitir
    remitos); los tests de la regla de corte usan confirm_cut_for_all=False."""
    material_id = _create_material(headers)
    _create_machine_config(headers, material_id)
    client_id = _create_client_record(headers, name="Cliente Remitos")
    quotation_id = _create_quotation(headers, client_id)
    item_ids = []
    piece_ids = []
    for index, quantity in enumerate(quantities):
        piece_id = _create_piece_with_dxf(headers, material_id, name=f"Pieza {index + 1}")
        piece_ids.append(piece_id)
        res = client.post(
            "/quotation-items",
            json={"quotation_id": quotation_id, "piece_id": piece_id, "material_id": material_id, "quantity": quantity},
            headers=headers,
        )
        assert res.status_code == 200, res.text
        item_ids.append(res.json()["id"])
    if status in ("sent", "accepted", "cancelled"):
        assert set_status(headers, quotation_id, "sent").status_code == 200
    if status == "accepted":
        assert set_status(headers, quotation_id, "accepted").status_code == 200
    if status == "cancelled":
        assert set_status(headers, quotation_id, "cancelled").status_code == 200
    result = {
        "quotation_id": quotation_id,
        "item_ids": item_ids,
        "piece_ids": piece_ids,
        "client_id": client_id,
        "material_id": material_id,
    }
    if status == "accepted" and confirm_cut_for_all:
        for index in range(len(item_ids)):
            confirm_cut(headers, result, index)
    return result


def create_note(headers: dict, quotation_id: int, lines: list[tuple[int, int]], notes: str | None = None):
    body = {"quotation_id": quotation_id, "items": [{"quotation_item_id": i, "quantity": q} for i, q in lines]}
    if notes is not None:
        body["notes"] = notes
    return client.post("/delivery-notes", json=body, headers=headers)


def issue_note(headers: dict, note_id: int):
    return client.post(f"/delivery-notes/{note_id}/issue", headers=headers)


def void_note(headers: dict, note_id: int, reason: str = "Error de carga"):
    return client.post(f"/delivery-notes/{note_id}/void", json={"reason": reason}, headers=headers)


def delivery_status(headers: dict, quotation_id: int) -> dict:
    res = client.get(f"/delivery-notes/quotation/{quotation_id}/status", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def issue_new(headers: dict, quotation_id: int, lines: list[tuple[int, int]]) -> dict:
    res = create_note(headers, quotation_id, lines)
    assert res.status_code == 201, res.text
    res = issue_note(headers, res.json()["id"])
    assert res.status_code == 200, res.text
    return res.json()


__all__ = ["issue_iso"]
