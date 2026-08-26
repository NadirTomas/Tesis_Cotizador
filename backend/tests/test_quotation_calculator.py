"""
Cobertura de quotation_calculator.py — antes de este archivo, solo se
ejercitaba indirectamente vía el flujo E2E y test_audit_fixes.py
(1 caso de recálculo). Fórmula real (calculate_quotation_item):

    costo_material = (piece.area_mm2 / (sheet_width_mm * sheet_height_mm)) * sheet_cost_ars * quantity
    tiempo_por_unidad_h = (piece.length_cut_mm / cut_speed_mm_min + setup_time_min) / 60
    costo_maquina = tiempo_por_unidad_h * machine_cost_per_hour_ars * quantity
    costo_labor = costo_maquina * (labor_percent / 100)
    unit_price = ((costo_material + costo_maquina + costo_labor) / quantity) * (1 + margin_percent / 100)
    total_price = unit_price * quantity

Los tests fijan piece.area_mm2/length_cut_mm directo por DB (en vez de
depender de que un DXF particular produzca un valor exacto) para poder
verificar la fórmula a mano con números redondos.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db.init_db import init_db
from app.db.session import SessionLocal, engine
from app.main import app
from app.models.machine_config import MachineConfig
from app.models.piece import Piece
from app.models.quotation_item import QuotationItem
from app.services.quotation_calculator import calculate_quotation_item

client = TestClient(app)


def _reset_db_file() -> None:
    engine.dispose()
    db_path = Path("cotizalaser.db")
    if db_path.exists():
        db_path.unlink()


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


def _create_material(headers, sheet_cost_ars=100_000.0, sheet_width_mm=1000.0, sheet_height_mm=1000.0):
    res = client.post(
        "/materials",
        json={
            "name": "Acero", "material_type": "Acero al carbono", "thickness_mm": 3,
            "sheet_width_mm": sheet_width_mm, "sheet_height_mm": sheet_height_mm, "sheet_cost_ars": sheet_cost_ars,
        },
        headers=headers,
    )
    assert res.status_code == 200
    return res.json()["id"]


def _create_machine_config(headers, material_id, cut_speed_mm_min=1000.0, machine_cost_per_hour_ars=6000.0, setup_time_min=5.0, labor_percent=30.0):
    res = client.post(
        "/machine-configs",
        json={
            "material_id": material_id, "cut_speed_mm_min": cut_speed_mm_min,
            "machine_cost_per_hour_ars": machine_cost_per_hour_ars, "setup_time_min": setup_time_min,
            "labor_percent": labor_percent,
        },
        headers=headers,
    )
    assert res.status_code == 200
    return res.json()["id"]


def _create_piece(headers, material_id, area_mm2=100_000.0, length_cut_mm=2000.0, name="Pieza"):
    """Crea la pieza sin DXF y fija area_mm2/length_cut_mm directo por DB
    -- valores exactos y redondos para verificar la fórmula a mano, sin
    depender de la geometría real de un DXF (eso ya lo cubre
    test_dxf_analysis.py por separado)."""
    res = client.post("/pieces", json={"name": name, "material_id": material_id}, headers=headers)
    assert res.status_code == 200
    piece_id = res.json()["id"]
    db = SessionLocal()
    piece = db.query(Piece).filter(Piece.id == piece_id).first()
    piece.area_mm2 = area_mm2
    piece.length_cut_mm = length_cut_mm
    db.commit()
    db.close()
    return piece_id


def _create_client_record(headers, name="Cliente"):
    res = client.post("/clients", json={"name": name}, headers=headers)
    assert res.status_code == 200
    return res.json()["id"]


def _create_quotation(headers, client_id, exchange_rate=None, currency="ARS"):
    payload = {"client_id": client_id, "issue_date": "2026-08-26T00:00:00", "currency": currency}
    if exchange_rate is not None:
        payload["exchange_rate"] = exchange_rate
    res = client.post("/quotations", json=payload, headers=headers)
    assert res.status_code == 200
    return res.json()["id"]


def _add_item(headers, quotation_id, piece_id, material_id, quantity=1, margin_percent=0.0):
    res = client.post(
        "/quotation-items",
        json={
            "quotation_id": quotation_id, "piece_id": piece_id, "material_id": material_id,
            "quantity": quantity, "margin_percent": margin_percent,
        },
        headers=headers,
    )
    return res


def _full_setup(**material_kwargs):
    _reset_db_file()
    init_db()
    headers, company_id = _register_and_create_company("owner_calc@test.com", "Empresa Calc")
    material_id = _create_material(headers, **material_kwargs)
    _create_machine_config(headers, material_id)
    return headers, company_id, material_id


# ---------- fórmula: material, máquina, labor, margen ----------


def test_cost_breakdown_matches_formula_for_quantity_one():
    headers, _company_id, material_id = _full_setup()
    piece_id = _create_piece(headers, material_id, area_mm2=100_000.0, length_cut_mm=2000.0)
    client_id = _create_client_record(headers)
    quotation_id = _create_quotation(headers, client_id)

    res = _add_item(headers, quotation_id, piece_id, material_id, quantity=1, margin_percent=0.0)
    assert res.status_code == 200
    item = res.json()

    # material: (100_000 / (1000*1000)) * 100_000 * 1 = 10_000
    assert item["cost_material_ars"] == pytest.approx(10_000.0)
    # máquina: ((2000/1000 + 5) / 60) * 6000 * 1 = (7/60)*6000 = 700
    assert item["cost_machine_ars"] == pytest.approx(700.0)
    # labor: 700 * 30% = 210
    assert item["cost_labor_ars"] == pytest.approx(210.0)
    # base = 10000 + 700 + 210 = 10910; margen 0% -> unit == total (qty=1)
    assert item["unit_price_ars"] == pytest.approx(10_910.0)
    assert item["total_price_ars"] == pytest.approx(10_910.0)


def test_quantity_scales_total_but_not_unit_price_without_margin_change():
    """
    setup_time_min entra en el tiempo POR UNIDAD antes de multiplicar por
    quantity -- confirma exactamente el comportamiento ya señalado en la
    auditoría (pendiente de validar con Cortesar, ver test dedicado más
    abajo): con margen fijo, el unit_price NO cambia con la cantidad,
    porque material y máquina escalan linealmente y se vuelven a dividir
    por quantity. Documentado, no modificado.
    """
    headers, _company_id, material_id = _full_setup()
    piece_id = _create_piece(headers, material_id, area_mm2=100_000.0, length_cut_mm=2000.0)
    client_id = _create_client_record(headers)
    quotation_id = _create_quotation(headers, client_id)

    res_qty1 = _add_item(headers, quotation_id, piece_id, material_id, quantity=1, margin_percent=0.0)
    quotation_id_2 = _create_quotation(headers, client_id)
    res_qty3 = _add_item(headers, quotation_id_2, piece_id, material_id, quantity=3, margin_percent=0.0)

    assert res_qty1.json()["unit_price_ars"] == pytest.approx(res_qty3.json()["unit_price_ars"])
    assert res_qty3.json()["total_price_ars"] == pytest.approx(res_qty1.json()["unit_price_ars"] * 3)
    assert res_qty3.json()["cost_material_ars"] == pytest.approx(res_qty1.json()["cost_material_ars"] * 3)
    assert res_qty3.json()["cost_machine_ars"] == pytest.approx(res_qty1.json()["cost_machine_ars"] * 3)


def test_positive_margin_applies_over_full_cost_base():
    headers, _company_id, material_id = _full_setup()
    piece_id = _create_piece(headers, material_id, area_mm2=100_000.0, length_cut_mm=2000.0)
    client_id = _create_client_record(headers)
    quotation_id = _create_quotation(headers, client_id)

    res = _add_item(headers, quotation_id, piece_id, material_id, quantity=3, margin_percent=20.0)
    item = res.json()
    cost_base_total = item["cost_material_ars"] + item["cost_machine_ars"] + item["cost_labor_ars"]
    assert item["unit_price_ars"] == pytest.approx((cost_base_total / 3) * 1.2)
    assert item["total_price_ars"] == pytest.approx(item["unit_price_ars"] * 3)


def test_setup_time_is_charged_once_per_unit_not_once_per_job():
    """
    PENDIENTE DE VALIDACIÓN DE NEGOCIO (no modificar sin confirmación):
    setup_time_min se suma DENTRO del tiempo por unidad, antes de
    multiplicar por quantity -- así que un ítem de 5 unidades cobra 5 veces
    el tiempo de preparación, no una sola vez por la corrida completa. Este
    test documenta el comportamiento actual tal cual está, no lo valida
    como correcto ni lo cambia. Confirmar con Cortesar si setup_time_min
    debería ser por unidad, por lote, o por trabajo completo.
    """
    headers, _company_id, material_id = _full_setup()  # setup_time_min=5, machine_cost_per_hour_ars=6000
    piece_id = _create_piece(headers, material_id, area_mm2=0.0, length_cut_mm=2000.0)
    client_id = _create_client_record(headers)

    quotation_1 = _create_quotation(headers, client_id)
    res_1 = _add_item(headers, quotation_1, piece_id, material_id, quantity=1)
    quotation_5 = _create_quotation(headers, client_id)
    res_5 = _add_item(headers, quotation_5, piece_id, material_id, quantity=5)

    # tiempo por unidad = (2000/1000 + 5) / 60 h = 7/60 h -> costo = (7/60)*6000 = 700
    cost_machine_1_unit = res_1.json()["cost_machine_ars"]
    cost_machine_5_units = res_5.json()["cost_machine_ars"]
    assert cost_machine_1_unit == pytest.approx(700.0)
    assert cost_machine_5_units == pytest.approx(700.0 * 5), (
        "comportamiento actual: el setup (incluido en el tiempo por unidad) se "
        "cobra una vez POR UNIDAD, no una vez por la corrida completa -- si esto "
        "cambia, este test debe actualizarse junto con la confirmación de negocio"
    )


# ---------- área/longitud en cero (pieza sin geometría útil, ej. un círculo mal leído) ----------


def test_zero_area_piece_has_no_material_cost_but_keeps_machine_cost():
    headers, _company_id, material_id = _full_setup()
    piece_id = _create_piece(headers, material_id, area_mm2=0.0, length_cut_mm=2000.0)
    client_id = _create_client_record(headers)
    quotation_id = _create_quotation(headers, client_id)

    res = _add_item(headers, quotation_id, piece_id, material_id, quantity=1)
    item = res.json()
    assert item["cost_material_ars"] == 0.0
    assert item["cost_machine_ars"] > 0.0


def test_zero_length_piece_has_no_machine_or_labor_cost():
    headers, _company_id, material_id = _full_setup()
    piece_id = _create_piece(headers, material_id, area_mm2=100_000.0, length_cut_mm=0.0)
    client_id = _create_client_record(headers)
    quotation_id = _create_quotation(headers, client_id)

    res = _add_item(headers, quotation_id, piece_id, material_id, quantity=1)
    item = res.json()
    assert item["cost_machine_ars"] == 0.0
    assert item["cost_labor_ars"] == 0.0  # depende de cost_machine, también en 0
    assert item["cost_material_ars"] > 0.0


# ---------- USD ----------


def test_total_usd_computed_when_exchange_rate_present():
    headers, _company_id, material_id = _full_setup()
    piece_id = _create_piece(headers, material_id, area_mm2=100_000.0, length_cut_mm=2000.0)
    client_id = _create_client_record(headers)
    quotation_id = _create_quotation(headers, client_id, exchange_rate=1000.0)

    _add_item(headers, quotation_id, piece_id, material_id, quantity=1)
    res = client.get(f"/quotations/{quotation_id}", headers=headers)
    quotation = res.json()
    assert quotation["total_usd"] == pytest.approx(quotation["total_ars"] / 1000.0)


@pytest.mark.parametrize("exchange_rate", [None, 0.0])
def test_total_usd_is_zero_without_a_valid_exchange_rate(exchange_rate):
    headers, _company_id, material_id = _full_setup()
    piece_id = _create_piece(headers, material_id, area_mm2=100_000.0, length_cut_mm=2000.0)
    client_id = _create_client_record(headers)
    quotation_id = _create_quotation(headers, client_id, exchange_rate=exchange_rate)

    _add_item(headers, quotation_id, piece_id, material_id, quantity=1)
    res = client.get(f"/quotations/{quotation_id}", headers=headers)
    assert res.json()["total_usd"] == 0.0


# ---------- configuración inexistente ----------


def test_missing_active_machine_config_fails_cleanly():
    _reset_db_file()
    init_db()
    headers, _company_id = _register_and_create_company("owner_calc_noconf@test.com", "Empresa CalcSinConfig")
    material_id = _create_material(headers)  # sin machine-config
    piece_id = _create_piece(headers, material_id)
    client_id = _create_client_record(headers)
    quotation_id = _create_quotation(headers, client_id)

    res = _add_item(headers, quotation_id, piece_id, material_id)
    assert res.status_code == 400
    assert "MachineConfig" in res.json()["detail"]


def test_quantity_zero_does_not_crash_calculator_directly():
    """quantity<=0 ya se rechaza en el schema (Field(gt=0)) antes de llegar
    acá -- se llama a calculate_quotation_item directo para confirmar que
    el guard `if quantity > 0` realmente evita la división por cero si
    algún día un caller interno se salteara la validación del schema."""
    headers, company_id, material_id = _full_setup()
    piece_id = _create_piece(headers, material_id)
    client_id = _create_client_record(headers)
    quotation_id = _create_quotation(headers, client_id)

    db = SessionLocal()
    item = QuotationItem(quotation_id=quotation_id, piece_id=piece_id, material_id=material_id, quantity=0)
    db.add(item)
    db.flush()
    calculate_quotation_item(db, item, company_id)  # no debe lanzar ZeroDivisionError
    assert item.unit_price_ars == 0.0
    assert item.total_price_ars == 0.0
    db.close()


# ---------- defensa en profundidad cross-company ----------


def test_calculator_rejects_piece_from_another_company():
    headers_a, company_a, material_a = _full_setup()
    piece_a = _create_piece(headers_a, material_a)
    client_a = _create_client_record(headers_a)
    quotation_a = _create_quotation(headers_a, client_a)

    _headers_b, company_b = _register_and_create_company("owner_calc_b@test.com", "Empresa CalcB")

    db = SessionLocal()
    item = QuotationItem(quotation_id=quotation_a, piece_id=piece_a, material_id=material_a, quantity=1)
    db.add(item)
    db.flush()
    with pytest.raises(ValueError, match="Piece"):
        calculate_quotation_item(db, item, company_b)  # company_b no es dueña de piece_a
    db.close()


def test_calculator_rejects_material_from_another_company():
    headers_a, company_a, material_a = _full_setup()
    piece_a = _create_piece(headers_a, material_a)
    client_a = _create_client_record(headers_a)
    quotation_a = _create_quotation(headers_a, client_a)

    headers_b, company_b = _register_and_create_company("owner_calc_b2@test.com", "Empresa CalcB2")
    material_b = _create_material(headers_b)

    db = SessionLocal()
    # piece_a pertenece a company_a, pero se arma el item con material_b
    # (de company_b) -- calculado con company_id=company_a: la pieza pasa
    # su propio chequeo, pero material_b no pertenece a company_a.
    item = QuotationItem(quotation_id=quotation_a, piece_id=piece_a, material_id=material_b, quantity=1)
    db.add(item)
    db.flush()
    with pytest.raises(ValueError, match="Material"):
        calculate_quotation_item(db, item, company_a)
    db.close()
