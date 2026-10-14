"""Regresión Bug 3: agregar/reemplazar una configuración de máquina debe
quedar disponible para cotizar sin alterar los costos ya guardados en
cotizaciones anteriores."""

from fastapi.testclient import TestClient

from app.main import app
from tests.test_quotation_delete import (
    _create_machine_config,
    _create_quotation,
    _create_quotation_item,
    _setup_draft_quotation_with_item,
    _create_piece_with_dxf,
)

client = TestClient(app)


def _item(headers, item_id, quotation_id):
    items = client.get(f"/quotation-items/quotation/{quotation_id}", headers=headers).json()
    return next(i for i in items if i["id"] == item_id)


def test_replacing_machine_config_affects_new_items_only():
    headers, quotation_id, old_item_id = _setup_draft_quotation_with_item(email="repl@test.com", company_name="Empresa Repl")
    old_before = _item(headers, old_item_id, quotation_id)
    material_id = old_before["material_id"]

    configs = client.get("/machine-configs", headers=headers).json()
    assert len(configs) == 1
    old_config_id = configs[0]["id"]

    # Máquina vieja falla: se desactiva (no se borra la fila) y se carga la nueva, el doble de cara.
    assert client.delete(f"/machine-configs/{old_config_id}", headers=headers).status_code == 200
    res = client.post(
        "/machine-configs",
        json={"material_id": material_id, "cut_speed_mm_min": 3000, "machine_cost_per_hour_ars": 36000, "setup_time_min": 10},
        headers=headers,
    )
    assert res.status_code == 200
    new_config_id = res.json()["id"]
    assert new_config_id != old_config_id

    # La nueva es la única activa y aparece en el listado que alimenta la UI.
    listed = client.get("/machine-configs", headers=headers).json()
    assert [c["id"] for c in listed] == [new_config_id]

    # El ítem ya cotizado conserva sus costos guardados.
    old_after = _item(headers, old_item_id, quotation_id)
    assert old_after["cost_machine_ars"] == old_before["cost_machine_ars"]
    assert old_after["total_price_ars"] == old_before["total_price_ars"]

    # Un ítem nuevo se calcula con la máquina nueva.
    piece_id = old_before["piece_id"]
    new_quotation_id = _create_quotation(headers, client.get("/clients", headers=headers).json()[0]["id"])
    new_item_id = _create_quotation_item(headers, new_quotation_id, piece_id, material_id)
    new_item = _item(headers, new_item_id, new_quotation_id)
    assert new_item["cost_machine_ars"] > old_before["cost_machine_ars"]


def test_second_material_gets_its_own_machine_config():
    headers, _quotation_id, _item_id = _setup_draft_quotation_with_item(email="two@test.com", company_name="Empresa Two")
    res = client.post(
        "/materials",
        json={"name": "Inox", "material_type": "Inox", "thickness_mm": 2, "sheet_width_mm": 1500, "sheet_height_mm": 3000, "sheet_cost_ars": 120000},
        headers=headers,
    )
    assert res.status_code == 200
    _create_machine_config(headers, res.json()["id"])
    assert len(client.get("/machine-configs", headers=headers).json()) == 2
