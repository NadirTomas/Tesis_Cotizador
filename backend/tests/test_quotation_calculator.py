"""
Cobertura de quotation_calculator.py — antes de este archivo, solo se
ejercitaba indirectamente vía el flujo E2E y test_audit_fixes.py
(1 caso de recálculo). Fórmula real (calculate_quotation_item):

    costo_material = (piece.area_mm2 / (sheet_width_mm * sheet_height_mm)) * sheet_cost_ars * quantity
    tiempo_corte_total_h = (piece.length_cut_mm * quantity) / cut_speed_mm_min
    costo_maquina = ((tiempo_corte_total_h + setup_time_min) / 60) * machine_cost_per_hour_ars
    costo_labor = costo_maquina * (labor_percent / 100)
    unit_price = ((costo_material + costo_maquina + costo_labor) / quantity) * (1 + margin_percent / 100)
    total_price = unit_price * quantity

setup_time_min se cobra UNA sola vez por lote/trabajo, no por unidad
-- confirmado con Cortesar el 2026-09-14 (antes del 2026-09-14 se
cobraba por unidad, ver test_setup_time_is_charged_once_per_job y
PROJECT_MEMORY.md para el historial de la decisión). El tiempo de
corte sí escala con quantity.

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

_DUMMY_RECT_DXF = (
    "0\nSECTION\n2\nENTITIES\n0\nLWPOLYLINE\n8\n0\n90\n4\n70\n1\n"
    "10\n0\n20\n0\n10\n10\n20\n0\n10\n10\n20\n10\n10\n0\n20\n10\n"
    "0\nENDSEC\n0\nEOF\n"
)


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
    """Crea la pieza con un DXF dummy (el DXF es obligatorio para crear) y
    después pisa area_mm2/length_cut_mm directo por DB -- valores exactos y
    redondos para verificar la fórmula a mano, sin depender de la geometría
    real de un DXF (eso ya lo cubre test_dxf_analysis.py por separado)."""
    files = {"file": (f"{name}.dxf", _DUMMY_RECT_DXF.encode("utf-8"), "application/dxf")}
    res = client.post("/pieces", data={"name": name, "material_id": material_id}, files=files, headers=headers)
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


def test_quantity_scales_material_linearly_but_amortizes_setup_over_machine_cost():
    """
    Material SÍ escala linealmente con quantity (no depende de setup).
    Máquina ya NO escala linealmente -- el corte escala, pero el setup se
    cobra una sola vez y se reparte entre más unidades, así que
    unit_price BAJA al aumentar quantity (antes del 2026-09-14 se
    mantenía constante, porque el setup también escalaba ×quantity; ver
    PROJECT_MEMORY.md para el historial de la decisión de negocio).
    """
    headers, _company_id, material_id = _full_setup()  # setup_time_min=5, cut_speed=1000, rate=6000
    piece_id = _create_piece(headers, material_id, area_mm2=100_000.0, length_cut_mm=2000.0)
    client_id = _create_client_record(headers)
    quotation_id = _create_quotation(headers, client_id)

    res_qty1 = _add_item(headers, quotation_id, piece_id, material_id, quantity=1, margin_percent=0.0)
    quotation_id_2 = _create_quotation(headers, client_id)
    res_qty3 = _add_item(headers, quotation_id_2, piece_id, material_id, quantity=3, margin_percent=0.0)

    item1, item3 = res_qty1.json(), res_qty3.json()

    # material: escala linealmente, sin cambios
    assert item3["cost_material_ars"] == pytest.approx(item1["cost_material_ars"] * 3)

    # máquina: corte×3 (2000*3/1000=6 min) + setup UNA vez (5 min) = 11 min
    # -> (11/60)*6000 = 1100, NO 700*3=2100
    assert item1["cost_machine_ars"] == pytest.approx(700.0)
    assert item3["cost_machine_ars"] == pytest.approx(1100.0)
    assert item3["cost_machine_ars"] != pytest.approx(item1["cost_machine_ars"] * 3)

    # por lo tanto unit_price baja al aumentar quantity (setup amortizado
    # entre más unidades) -- ya NO se mantiene constante como antes.
    assert item3["unit_price_ars"] < item1["unit_price_ars"]
    assert item1["unit_price_ars"] == pytest.approx(10_910.0)  # 10000+700+210, qty=1
    assert item3["unit_price_ars"] == pytest.approx((30_000.0 + 1100.0 + 330.0) / 3)  # 10476.666...


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


def test_setup_time_is_charged_once_per_job():
    """
    Confirmado con Cortesar el 2026-09-14: setup_time_min se cobra UNA
    sola vez por lote/trabajo, no una vez por cada unidad. El tiempo de
    corte sí escala con quantity. Antes de esta fecha, el setup se
    sumaba dentro del tiempo por unidad y terminaba multiplicado por
    quantity -- comportamiento incorrecto, ya corregido (ver
    PROJECT_MEMORY.md para el historial completo de la decisión).
    """
    headers, _company_id, material_id = _full_setup()  # setup_time_min=5, machine_cost_per_hour_ars=6000
    piece_id = _create_piece(headers, material_id, area_mm2=0.0, length_cut_mm=2000.0)
    client_id = _create_client_record(headers)

    quotation_1 = _create_quotation(headers, client_id)
    res_1 = _add_item(headers, quotation_1, piece_id, material_id, quantity=1)
    quotation_5 = _create_quotation(headers, client_id)
    res_5 = _add_item(headers, quotation_5, piece_id, material_id, quantity=5)

    # qty=1: (2000*1/1000 + 5) / 60 h = 7/60 h -> costo = (7/60)*6000 = 700
    # qty=5: (2000*5/1000 + 5) / 60 h = 15/60 h -> costo = (15/60)*6000 = 1500
    cost_machine_1_unit = res_1.json()["cost_machine_ars"]
    cost_machine_5_units = res_5.json()["cost_machine_ars"]
    assert cost_machine_1_unit == pytest.approx(700.0)
    assert cost_machine_5_units == pytest.approx(1500.0), (
        "el setup (5 min) se cobra una sola vez -- no 700*5=3500, "
        "sino (2000*5/1000 + 5)/60 * 6000 = 1500"
    )


def test_cortesar_example_five_pieces_ten_minute_setup():
    """
    Ejemplo exacto confirmado con Cortesar el 2026-09-14: 5 piezas,
    1 minuto de corte cada una, 10 minutos de setup -> 15 minutos
    totales de máquina, no 5*(1+10)=55. Arma el escenario a mano (no
    reusa _full_setup) porque necesita setup_time_min=10, no el default.
    """
    _reset_db_file()
    init_db()
    headers, _company_id = _register_and_create_company("owner_calc_cortesar@test.com", "Empresa Cortesar")
    material_id = _create_material(headers, sheet_cost_ars=0.0)  # material en 0 para aislar el costo de máquina
    _create_machine_config(
        headers, material_id,
        cut_speed_mm_min=1000.0, machine_cost_per_hour_ars=6000.0,
        setup_time_min=10.0, labor_percent=0.0,
    )
    piece_id = _create_piece(headers, material_id, area_mm2=0.0, length_cut_mm=1000.0)
    client_id = _create_client_record(headers)
    quotation_id = _create_quotation(headers, client_id)

    res = _add_item(headers, quotation_id, piece_id, material_id, quantity=5, margin_percent=0.0)
    item = res.json()

    # tiempo total = 1*5 + 10 = 15 min -> costo = 15/60 * 6000 = 1500
    assert item["cost_machine_ars"] == pytest.approx(1500.0)
    assert item["cost_material_ars"] == pytest.approx(0.0)
    assert item["cost_labor_ars"] == pytest.approx(0.0)  # labor_percent=0
    assert item["total_price_ars"] == pytest.approx(1500.0)


def test_setup_time_zero_is_not_a_regression():
    """setup_time_min=0 debe dar el mismo resultado con la fórmula vieja o
    nueva -- el setup no contribuye nada en ninguna de las dos."""
    _reset_db_file()
    init_db()
    headers, _company_id = _register_and_create_company("owner_calc_zerosetup@test.com", "Empresa ZeroSetup")
    material_id = _create_material(headers)
    _create_machine_config(
        headers, material_id,
        cut_speed_mm_min=1000.0, machine_cost_per_hour_ars=6000.0,
        setup_time_min=0.0, labor_percent=30.0,
    )
    piece_id = _create_piece(headers, material_id, area_mm2=0.0, length_cut_mm=2000.0)
    client_id = _create_client_record(headers)

    quotation_1 = _create_quotation(headers, client_id)
    res_1 = _add_item(headers, quotation_1, piece_id, material_id, quantity=1)
    quotation_5 = _create_quotation(headers, client_id)
    res_5 = _add_item(headers, quotation_5, piece_id, material_id, quantity=5)

    # sin setup, el costo de máquina escala linealmente con quantity, tal
    # cual como cualquiera de las dos fórmulas predeciría en este caso.
    assert res_1.json()["cost_machine_ars"] == pytest.approx(200.0)  # (2000/1000)/60*6000
    assert res_5.json()["cost_machine_ars"] == pytest.approx(1000.0)  # 200*5


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
    try:
        # piece_a pertenece a company_a, pero se arma el item con material_b
        # (de company_b) -- calculado con company_id=company_a: la pieza pasa
        # su propio chequeo, pero material_b no pertenece a company_a.
        item = QuotationItem(quotation_id=quotation_a, piece_id=piece_a, material_id=material_b, quantity=1)
        db.add(item)
        db.flush()
        with pytest.raises(ValueError, match="Material"):
            calculate_quotation_item(db, item, company_a)
    finally:
        db.close()


# ---------- regresión: el refactor de compute_item_costs()/fetch_item_costing_context()
# (extraídos de adentro de calculate_quotation_item() para el backfill de
# geometría, ver scripts/recalculate_piece_geometry.py) no cambió ni un
# bit el comportamiento observable de calculate_quotation_item(). ----------


def test_compute_item_costs_matches_calculate_quotation_item_exactly():
    """
    calculate_quotation_item() ahora es fetch_item_costing_context() +
    compute_item_costs() + asignación -- nada más. Si esto es una
    extracción fiel (sin redondeos ni cambios de tipo introducidos),
    llamar a compute_item_costs() a mano con los mismos insumos que usó
    calculate_quotation_item() tiene que dar exactamente (==, no approx)
    los mismos 5 valores que quedaron persistidos en el item real.
    """
    from app.services.quotation_calculator import compute_item_costs, fetch_item_costing_context

    headers, _company_id, material_id = _full_setup()
    piece_id = _create_piece(headers, material_id, area_mm2=137_500.0, length_cut_mm=1234.5, name="Regresion")
    client_id = _create_client_record(headers)
    quotation_id = _create_quotation(headers, client_id)

    res = _add_item(headers, quotation_id, piece_id, material_id, quantity=4, margin_percent=17.5)
    assert res.status_code == 200
    persisted = res.json()

    db = SessionLocal()
    item = db.query(QuotationItem).filter(QuotationItem.id == persisted["id"]).first()
    piece, material, machine_config = fetch_item_costing_context(db, item, item.piece.company_id)
    costs = compute_item_costs(
        piece.area_mm2, piece.length_cut_mm, material, machine_config, item.quantity, item.margin_percent
    )
    db.close()

    # Igualdad exacta (no pytest.approx) -- misma aritmética float, mismo
    # orden de operaciones, sin Decimal ni redondeo de por medio en
    # ninguno de los dos caminos.
    assert costs.cost_material_ars == persisted["cost_material_ars"]
    assert costs.cost_machine_ars == persisted["cost_machine_ars"]
    assert costs.cost_labor_ars == persisted["cost_labor_ars"]
    assert costs.unit_price_ars == persisted["unit_price_ars"]
    assert costs.total_price_ars == persisted["total_price_ars"]
    db.close()
