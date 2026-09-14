"""
Cobertura de scripts/recalculate_piece_geometry.py — el backfill que
corrige Piece.area_mm2/length_cut_mm para piezas cargadas antes del fix
de agujeros/CIRCLE (134425d, 2026-08-26). Ver PROJECT_MEMORY.md.

Dos frentes separados a propósito:
  1. Que la geometría recalculada sea correcta (reusa analyze_dxf real,
     no hace falta reprobar su matemática acá -- eso ya lo cubre
     test_dxf_analysis.py -- pero sí confirmar que el script la aplica
     bien: rectángulo/agujero/círculo/contornos múltiples).
  2. Que la política de qué cotizaciones se tocan y cuáles no se respete
     al pie de la letra -- draft se recalcula, sent/accepted/cancelled
     quedan byte-a-byte intactas, y una carrera de cambio de estado
     protege al ítem en vez de pisarlo.
"""

from pathlib import Path

import ezdxf
import pytest
from fastapi.testclient import TestClient

from app.db.init_db import init_db
from app.db.session import SessionLocal, engine
from app.main import app
from app.models.piece import Piece
from app.models.quotation import Quotation
from app.models.quotation_item import QuotationItem
from scripts import recalculate_piece_geometry as recalc

client = TestClient(app)


# ---------- boilerplate (mismo patrón que el resto de la suite) ----------


def _reset_db_file() -> None:
    engine.dispose()
    db_path = Path("cotizalaser.db")
    if db_path.exists():
        db_path.unlink()


def _setup_owner(email="recalc_owner@test.com") -> dict:
    _reset_db_file()
    init_db()
    res = client.post("/auth/register", json={"email": email, "password": "Password1!"})
    token = res.json()["access_token"]
    res = client.post("/companies", json={"company_name": "Empresa Recalc"}, headers={"Authorization": f"Bearer {token}"})
    company_id = res.json()["id"]
    return {"Authorization": f"Bearer {token}", "X-Company-Id": str(company_id)}


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


def _create_machine_config(headers, material_id):
    res = client.post(
        "/machine-configs",
        json={
            "material_id": material_id, "cut_speed_mm_min": 1000.0,
            "machine_cost_per_hour_ars": 6000.0, "setup_time_min": 5.0, "labor_percent": 30.0,
        },
        headers=headers,
    )
    assert res.status_code == 200
    return res.json()["id"]


def _write_ezdxf_doc(path, build_fn) -> str:
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    build_fn(msp)
    doc.saveas(path)
    return path


def _create_piece_with_rect_dxf(headers, tmp_path, material_id, w=100.0, h=50.0, name="Pieza") -> int:
    """Sube un DXF real (rectángulo w×h) -- area/length quedan correctos desde el alta."""
    path = _write_ezdxf_doc(
        str(tmp_path / f"{name}.dxf"),
        lambda msp: msp.add_lwpolyline([(0, 0), (w, 0), (w, h), (0, h)], close=True),
    )
    with open(path, "rb") as fh:
        res = client.post(
            "/pieces",
            data={"name": name, "material_id": material_id},
            files={"file": (f"{name}.dxf", fh.read(), "application/dxf")},
            headers=headers,
        )
    assert res.status_code == 200
    return res.json()["id"]


def _corrupt_piece_geometry(piece_id: int, area_mm2: float, length_cut_mm: float) -> None:
    """Simula el estado 'pre-fix': pisa area/length por DB con valores deliberadamente incorrectos."""
    db = SessionLocal()
    piece = db.query(Piece).filter(Piece.id == piece_id).first()
    piece.area_mm2 = area_mm2
    piece.length_cut_mm = length_cut_mm
    db.commit()
    db.close()


def _get_piece(piece_id: int) -> Piece:
    db = SessionLocal()
    piece = db.query(Piece).filter(Piece.id == piece_id).first()
    db.expunge(piece)
    db.close()
    return piece


def _get_item(item_id: int) -> QuotationItem:
    db = SessionLocal()
    item = db.query(QuotationItem).filter(QuotationItem.id == item_id).first()
    db.expunge(item)
    db.close()
    return item


def _get_quotation(quotation_id: int) -> Quotation:
    db = SessionLocal()
    q = db.query(Quotation).filter(Quotation.id == quotation_id).first()
    db.expunge(q)
    db.close()
    return q


def _create_client_record(headers, name="Cliente"):
    res = client.post("/clients", json={"name": name}, headers=headers)
    assert res.status_code == 200
    return res.json()["id"]


def _create_quotation(headers, client_id):
    res = client.post(
        "/quotations",
        json={"client_id": client_id, "issue_date": "2026-08-26T00:00:00"},
        headers=headers,
    )
    assert res.status_code == 200
    return res.json()["id"]


def _add_item(headers, quotation_id, piece_id, material_id, quantity=2, margin_percent=20.0):
    res = client.post(
        "/quotation-items",
        json={
            "quotation_id": quotation_id, "piece_id": piece_id, "material_id": material_id,
            "quantity": quantity, "margin_percent": margin_percent,
        },
        headers=headers,
    )
    assert res.status_code == 200
    return res.json()["id"]


def _set_status(headers, quotation_id, status):
    """Encadena las transiciones intermedias necesarias (draft -> sent -> accepted)."""
    path = {"sent": ["sent"], "accepted": ["sent", "accepted"], "cancelled": ["cancelled"]}[status]
    for step in path:
        res = client.patch(f"/quotations/{quotation_id}/status", json={"status": step}, headers=headers)
        assert res.status_code == 200


def _run(db, **kwargs):
    return recalc.run(db, verbose=False, **kwargs)


# ---------- 1. geometría: rectángulo / agujero / círculo / contornos múltiples ----------


def test_rectangle_already_correct_is_unchanged(tmp_path):
    headers = _setup_owner()
    material_id = _create_material(headers)
    piece_id = _create_piece_with_rect_dxf(headers, tmp_path, material_id, w=100, h=50)

    db = SessionLocal()
    stats, rows = _run(db, apply=False)
    db.close()

    assert stats["pieces_inspected"] == 1
    assert stats["pieces_unchanged"] == 1
    assert stats["pieces_corrected"] == 0
    assert rows == []


def test_hole_detects_and_corrects_area(tmp_path):
    """El bug viejo SUMABA el agujero en vez de restarlo -- simulamos ese valor."""
    headers = _setup_owner()
    material_id = _create_material(headers)

    path = _write_ezdxf_doc(
        str(tmp_path / "hole.dxf"),
        lambda msp: (
            msp.add_lwpolyline([(0, 0), (100, 0), (100, 100), (0, 100)], close=True),
            msp.add_lwpolyline([(20, 20), (40, 20), (40, 40), (20, 40)], close=True),
        ),
    )
    with open(path, "rb") as fh:
        res = client.post(
            "/pieces", data={"name": "Hueco", "material_id": material_id},
            files={"file": ("hueco.dxf", fh.read(), "application/dxf")}, headers=headers,
        )
    piece_id = res.json()["id"]
    correct_area = res.json()["area_mm2"]
    assert correct_area == pytest.approx(100 * 100 - 20 * 20)

    # Simular el valor que el bug viejo hubiera guardado: sumaba el agujero.
    _corrupt_piece_geometry(piece_id, area_mm2=100 * 100 + 20 * 20, length_cut_mm=res.json()["length_cut_mm"])

    db = SessionLocal()
    stats, rows = _run(db, apply=True)
    db.close()

    assert stats["pieces_corrected"] == 1
    piece = _get_piece(piece_id)
    assert piece.area_mm2 == pytest.approx(correct_area)


def test_circle_detects_and_corrects_area(tmp_path):
    """El bug viejo no sumaba nada para CIRCLE -- simulamos area_mm2=0."""
    headers = _setup_owner()
    material_id = _create_material(headers)
    path = _write_ezdxf_doc(str(tmp_path / "circle.dxf"), lambda msp: msp.add_circle((0, 0), 40.0))
    with open(path, "rb") as fh:
        res = client.post(
            "/pieces", data={"name": "Circulo", "material_id": material_id},
            files={"file": ("circulo.dxf", fh.read(), "application/dxf")}, headers=headers,
        )
    piece_id = res.json()["id"]
    correct_area = res.json()["area_mm2"]
    assert correct_area > 0

    _corrupt_piece_geometry(piece_id, area_mm2=0.0, length_cut_mm=res.json()["length_cut_mm"])

    db = SessionLocal()
    stats, _ = _run(db, apply=True)
    db.close()

    assert stats["pieces_corrected"] == 1
    piece = _get_piece(piece_id)
    assert piece.area_mm2 == pytest.approx(correct_area)


def test_multiple_contours_keeps_only_largest_after_recalc(tmp_path):
    headers = _setup_owner()
    material_id = _create_material(headers)
    path = _write_ezdxf_doc(
        str(tmp_path / "multi.dxf"),
        lambda msp: (
            msp.add_lwpolyline([(0, 0), (100, 0), (100, 100), (0, 100)], close=True),  # 100x100, más grande
            msp.add_lwpolyline([(200, 200), (220, 200), (220, 220), (200, 220)], close=True),  # 20x20, disjunto
        ),
    )
    with open(path, "rb") as fh:
        res = client.post(
            "/pieces", data={"name": "Multi", "material_id": material_id},
            files={"file": ("multi.dxf", fh.read(), "application/dxf")}, headers=headers,
        )
    piece_id = res.json()["id"]
    correct_area = res.json()["area_mm2"]
    assert correct_area == pytest.approx(100 * 100)  # solo el contorno más grande

    _corrupt_piece_geometry(piece_id, area_mm2=1.0, length_cut_mm=res.json()["length_cut_mm"])

    db = SessionLocal()
    stats, _ = _run(db, apply=True)
    db.close()

    piece = _get_piece(piece_id)
    assert piece.area_mm2 == pytest.approx(100 * 100)


# ---------- 2. dry-run no escribe / apply sí / idempotencia ----------


def test_dry_run_never_writes(tmp_path):
    headers = _setup_owner()
    material_id = _create_material(headers)
    piece_id = _create_piece_with_rect_dxf(headers, tmp_path, material_id, w=100, h=50)
    _corrupt_piece_geometry(piece_id, area_mm2=1.0, length_cut_mm=1.0)

    db = SessionLocal()
    stats, rows = _run(db, apply=False)
    db.close()

    assert stats["pieces_corrected"] == 1
    piece = _get_piece(piece_id)
    # Sigue con el valor "corrupto" -- el dry-run no debe haber tocado nada.
    assert piece.area_mm2 == pytest.approx(1.0)
    assert piece.length_cut_mm == pytest.approx(1.0)


def test_apply_persists_correct_values(tmp_path):
    headers = _setup_owner()
    material_id = _create_material(headers)
    piece_id = _create_piece_with_rect_dxf(headers, tmp_path, material_id, w=100, h=50)
    _corrupt_piece_geometry(piece_id, area_mm2=1.0, length_cut_mm=1.0)

    db = SessionLocal()
    stats, _ = _run(db, apply=True)
    db.close()

    assert stats["pieces_corrected"] == 1
    piece = _get_piece(piece_id)
    assert piece.area_mm2 == pytest.approx(100 * 50)
    assert piece.length_cut_mm == pytest.approx(2 * (100 + 50))


def test_apply_twice_is_idempotent(tmp_path):
    headers = _setup_owner()
    material_id = _create_material(headers)
    piece_id = _create_piece_with_rect_dxf(headers, tmp_path, material_id, w=100, h=50)
    _corrupt_piece_geometry(piece_id, area_mm2=1.0, length_cut_mm=1.0)

    db = SessionLocal()
    stats1, _ = _run(db, apply=True)
    db.close()
    assert stats1["pieces_corrected"] == 1

    db = SessionLocal()
    stats2, rows2 = _run(db, apply=True)
    db.close()
    assert stats2["pieces_corrected"] == 0
    assert stats2["pieces_unchanged"] == 1
    assert stats2["draft_items_recalculated"] == 0
    assert rows2 == []

    # Segundo dry-run también debe confirmar 0 pendientes (requisito de idempotencia).
    db = SessionLocal()
    stats3, rows3 = _run(db, apply=False)
    db.close()
    assert stats3["pieces_corrected"] == 0
    assert rows3 == []


# ---------- 3. política por estado de cotización ----------


def _setup_piece_with_item(tmp_path, quantity=2, margin_percent=20.0):
    """Pieza con área vieja (deliberadamente incorrecta) + un ítem que la usa,
    calculado en el momento de creación con esa área vieja."""
    headers = _setup_owner()
    material_id = _create_material(headers)
    _create_machine_config(headers, material_id)
    piece_id = _create_piece_with_rect_dxf(headers, tmp_path, material_id, w=100, h=50)
    _corrupt_piece_geometry(piece_id, area_mm2=1_000.0, length_cut_mm=10.0)  # "viejo", incorrecto

    client_id = _create_client_record(headers)
    quotation_id = _create_quotation(headers, client_id)
    item_id = _add_item(headers, quotation_id, piece_id, material_id, quantity=quantity, margin_percent=margin_percent)

    return headers, material_id, piece_id, quotation_id, item_id


def test_draft_item_is_recalculated_with_official_formula(tmp_path):
    headers, material_id, piece_id, quotation_id, item_id = _setup_piece_with_item(tmp_path)
    item_before = _get_item(item_id)
    assert item_before.quantity == 2
    assert item_before.margin_percent == 20.0

    db = SessionLocal()
    stats, rows = _run(db, apply=True)
    db.close()

    assert stats["draft_items_recalculated"] == 1
    assert stats["historical_items_preserved"] == 0
    assert len(rows) == 1
    assert rows[0]["quotation_item_id"] == item_id

    piece = _get_piece(piece_id)
    assert piece.area_mm2 == pytest.approx(100 * 50)  # geometría corregida

    item_after = _get_item(item_id)
    # Parámetros elegidos por el usuario: intactos.
    assert item_after.quantity == 2
    assert item_after.margin_percent == 20.0
    assert item_after.material_id == material_id
    # El precio cambió respecto del original (calculado con área vieja).
    assert item_after.total_price_ars != pytest.approx(item_before.total_price_ars)

    # Los precios nuevos coinciden exactamente con calculate_quotation_item()
    # real vuelto a correr a mano -- ninguna fórmula duplicada en el script.
    from app.services.quotation_calculator import calculate_quotation_item
    db = SessionLocal()
    item_ref = db.query(QuotationItem).filter(QuotationItem.id == item_id).first()
    calculate_quotation_item(db, item_ref, item_ref.piece.company_id)
    expected_total = item_ref.total_price_ars
    db.close()
    assert item_after.total_price_ars == pytest.approx(expected_total)


@pytest.mark.parametrize("status", ["sent", "accepted", "cancelled"])
def test_historical_quotation_items_are_never_touched(tmp_path, status):
    headers, material_id, piece_id, quotation_id, item_id = _setup_piece_with_item(tmp_path)
    _set_status(headers, quotation_id, status)

    item_before = _get_item(item_id)
    quotation_before = _get_quotation(quotation_id)

    db = SessionLocal()
    stats, rows = _run(db, apply=True)
    db.close()

    assert stats["pieces_corrected"] == 1
    assert stats["historical_items_preserved"] == 1
    assert stats["draft_items_recalculated"] == 0
    assert rows == []  # el reporte detallado es solo para ítems draft

    # La pieza SÍ se corrige...
    piece = _get_piece(piece_id)
    assert piece.area_mm2 == pytest.approx(100 * 50)

    # ...pero el ítem y el total de la cotización quedan exactamente iguales.
    item_after = _get_item(item_id)
    assert item_after.cost_material_ars == item_before.cost_material_ars
    assert item_after.cost_machine_ars == item_before.cost_machine_ars
    assert item_after.cost_labor_ars == item_before.cost_labor_ars
    assert item_after.unit_price_ars == item_before.unit_price_ars
    assert item_after.total_price_ars == item_before.total_price_ars

    quotation_after = _get_quotation(quotation_id)
    assert quotation_after.total_ars == quotation_before.total_ars
    assert quotation_after.total_usd == quotation_before.total_usd


def test_race_protection_status_changes_between_scan_and_persist(tmp_path, monkeypatch):
    """
    Simula la carrera que preocupa al usuario: el script ya escaneó el ítem
    como draft, pero justo antes de persistir el recálculo, otra request
    (simulada acá con una escritura directa por DB) lo pasa a 'sent'. El
    guard (_quotation_still_draft) debe detectarlo y el ítem NO debe
    modificarse.
    """
    headers, material_id, piece_id, quotation_id, item_id = _setup_piece_with_item(tmp_path)
    item_before = _get_item(item_id)

    real_fetch = recalc.fetch_item_costing_context

    def _fetch_then_flip_status(db, item, company_id):
        result = real_fetch(db, item, company_id)
        # Simula otra transacción que ya comiteó sent/accepted en el medio.
        other_db = SessionLocal()
        try:
            q = other_db.query(Quotation).filter(Quotation.id == item.quotation_id).first()
            q.status = "sent"
            other_db.commit()
        finally:
            other_db.close()
        return result

    monkeypatch.setattr(recalc, "fetch_item_costing_context", _fetch_then_flip_status)

    db = SessionLocal()
    stats, rows = _run(db, apply=True)
    db.close()

    assert stats["draft_items_protected_race"] == 1
    assert stats["draft_items_recalculated"] == 0

    item_after = _get_item(item_id)
    assert item_after.total_price_ars == item_before.total_price_ars
    assert item_after.unit_price_ars == item_before.unit_price_ars

    # La pieza igual se corrigió -- la carrera solo protege al item.
    piece = _get_piece(piece_id)
    assert piece.area_mm2 == pytest.approx(100 * 50)

    # Este test abre una segunda conexión (other_db) además de la principal
    # -- en Windows el pool de SQLite puede no soltar el handle del archivo
    # a tiempo para que el siguiente test lo borre en _reset_db_file().
    # dispose() fuerza el release acá, no en medio de la transacción.
    engine.dispose()
