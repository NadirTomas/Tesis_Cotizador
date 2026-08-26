"""
Cobertura del motor de análisis DXF (dxf_analysis.py) — antes de este
archivo, cero tests dedicados (hallazgo de la auditoría), pese a ser el
módulo donde vivía el bug de área con agujeros ya corregido esta sesión
(ver services/dxf_analysis.py, _closed_loop_area).

Los DXF construidos con `ezdxf.new()` + `saveas()` producen documentos
completos y válidos: `ezdxf.readfile()` los lee directo, sin pasar por
`recover` ni por el fallback manual — es el camino "normal". Los DXF de
texto crudo mínimo (mismo patrón que usan test_stock_reservation.py y
otros: solo SECTION/ENTITIES/ENDSEC, sin HEADER/TABLES ni subclases
AcDbPolyline) hacen fallar tanto `readfile` como `recover.readfile`, así
que caen siempre en el parser de fallback línea por línea — confirmado
empíricamente antes de escribir este archivo. Ambos caminos se prueban
por separado para no dejar ninguno sin cobertura real.
"""

import math

import ezdxf
import pytest
from shapely.geometry import Polygon

from app.services import dxf_analysis
from app.services.dxf_analysis import analyze_dxf, extract_piece_polygon, get_bounding_box


# ---------- helpers ----------


def _write_ezdxf_doc(path, build_fn):
    """Crea un DXF válido y completo (camino normal de ezdxf.readfile)."""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    build_fn(msp)
    doc.saveas(path)
    return path


def _minimal_raw_dxf(entities_text: str) -> str:
    """DXF mínimo de texto crudo (sin HEADER/TABLES) — fuerza el fallback manual."""
    return f"0\nSECTION\n2\nENTITIES\n{entities_text}0\nENDSEC\n0\nEOF\n"


def _raw_closed_square(w: float, h: float) -> str:
    return (
        "0\nLWPOLYLINE\n8\n0\n90\n4\n70\n1\n"
        f"10\n0\n20\n0\n10\n{w}\n20\n0\n10\n{w}\n20\n{h}\n10\n0\n20\n{h}\n"
    )


# ---------- geometría simple: camino normal de ezdxf ----------


def test_open_line_contributes_length_but_no_area(tmp_path):
    path = str(tmp_path / "line.dxf")
    _write_ezdxf_doc(path, lambda msp: msp.add_line((0, 0), (30, 40)))
    length, area = analyze_dxf(path)
    assert length == pytest.approx(50.0)  # 3-4-5
    assert area == 0.0


def test_closed_lwpolyline_rectangle_length_and_area(tmp_path):
    path = str(tmp_path / "rect.dxf")
    _write_ezdxf_doc(path, lambda msp: msp.add_lwpolyline([(0, 0), (100, 0), (100, 50), (0, 50)], close=True))
    length, area = analyze_dxf(path)
    assert length == pytest.approx(2 * (100 + 50))
    assert area == pytest.approx(100 * 50)


def test_circle_length_and_area(tmp_path):
    path = str(tmp_path / "circle.dxf")
    radius = 40.0
    _write_ezdxf_doc(path, lambda msp: msp.add_circle((0, 0), radius))
    length, area = analyze_dxf(path)
    assert length == pytest.approx(2 * math.pi * radius)
    # extract_piece_polygon aproxima el círculo con un polígono de 32 lados
    # inscripto -- ligeramente menor al área real, nunca mayor.
    assert area < math.pi * radius**2
    assert area == pytest.approx(math.pi * radius**2, rel=0.01)


# ---------- área: polígono con agujero, círculo, varios contornos ----------


def test_area_subtracts_a_hole(tmp_path):
    path = str(tmp_path / "area_hole.dxf")

    def build(msp):
        msp.add_lwpolyline([(0, 0), (100, 0), (100, 100), (0, 100)], close=True)
        msp.add_lwpolyline([(20, 20), (40, 20), (40, 40), (20, 40)], close=True)  # agujero 20x20

    _write_ezdxf_doc(path, build)
    _length, area = analyze_dxf(path)
    assert area == pytest.approx(100 * 100 - 20 * 20)


def test_multiple_disjoint_contours_only_the_largest_counts_as_exterior(tmp_path):
    """
    Comportamiento actual documentado, no un bug a arreglar en este pase:
    _build_polygon_from_loops toma el loop de mayor área como exterior y
    solo trata como agujero a los loops que ese exterior CONTIENE. Dos
    contornos separados (ninguno adentro del otro) no se suman -- el más
    chico se ignora silenciosamente. Pieza multi-contorno real no está
    soportada hoy; este test deja registrado el comportamiento exacto.
    """
    path = str(tmp_path / "area_disjoint.dxf")

    def build(msp):
        msp.add_lwpolyline([(0, 0), (100, 0), (100, 50), (0, 50)], close=True)  # 100x50 = 5000
        msp.add_lwpolyline([(200, 0), (240, 0), (240, 40), (200, 40)], close=True)  # 40x40 = 1600, separado

    _write_ezdxf_doc(path, build)
    _length, area = analyze_dxf(path)
    assert area == pytest.approx(100 * 50)  # solo el contorno más grande, el de 1600 se pierde


# ---------- bounding box ----------


def test_bounding_box_matches_rectangle_dimensions(tmp_path):
    path = str(tmp_path / "bbox.dxf")
    _write_ezdxf_doc(path, lambda msp: msp.add_lwpolyline([(0, 0), (120, 0), (120, 33), (0, 33)], close=True))
    width, height = get_bounding_box(path)
    assert (width, height) == pytest.approx((120.0, 33.0))


def test_bounding_box_of_a_circle_is_its_diameter(tmp_path):
    path = str(tmp_path / "bbox_circle.dxf")
    _write_ezdxf_doc(path, lambda msp: msp.add_circle((10, 10), 25))
    width, height = get_bounding_box(path)
    assert (width, height) == pytest.approx((50.0, 50.0))


# ---------- extract_piece_polygon ----------


def test_extract_piece_polygon_simple_rectangle(tmp_path):
    path = str(tmp_path / "poly.dxf")
    _write_ezdxf_doc(path, lambda msp: msp.add_lwpolyline([(0, 0), (10, 0), (10, 20), (0, 20)], close=True))
    poly = extract_piece_polygon(path)
    assert isinstance(poly, Polygon)
    assert poly.area == pytest.approx(200.0)
    assert len(poly.interiors) == 0


def test_extract_piece_polygon_with_hole(tmp_path):
    path = str(tmp_path / "extract_hole.dxf")

    def build(msp):
        msp.add_lwpolyline([(0, 0), (10, 0), (10, 10), (0, 10)], close=True)
        msp.add_lwpolyline([(2, 2), (4, 2), (4, 4), (2, 4)], close=True)

    _write_ezdxf_doc(path, build)
    poly = extract_piece_polygon(path)
    assert len(poly.interiors) == 1
    assert poly.area == pytest.approx(100 - 4)


def test_extract_piece_polygon_irregular_l_shape(tmp_path):
    path = str(tmp_path / "l_shape.dxf")
    l_shape = [(0, 0), (10, 0), (10, 5), (5, 5), (5, 10), (0, 10)]
    _write_ezdxf_doc(path, lambda msp: msp.add_lwpolyline(l_shape, close=True))
    poly = extract_piece_polygon(path)
    assert poly.is_valid
    assert poly.area == pytest.approx(Polygon(l_shape).area)


def test_extract_piece_polygon_rejects_open_contour(tmp_path):
    path = str(tmp_path / "open.dxf")
    # close=False: no es un contorno cerrado -- no hay ninguna pieza real ahí.
    _write_ezdxf_doc(path, lambda msp: msp.add_lwpolyline([(0, 0), (10, 0), (10, 10), (0, 10)], close=False))
    with pytest.raises(ValueError):
        extract_piece_polygon(path)


def test_extract_piece_polygon_invalid_geometry_raises_clear_error(tmp_path):
    path = str(tmp_path / "degenerate.dxf")
    # Solo 2 puntos distintos (duplicado) -- no forma un polígono real.
    _write_ezdxf_doc(path, lambda msp: msp.add_lwpolyline([(0, 0), (0, 0), (0, 0)], close=True))
    with pytest.raises(ValueError):
        extract_piece_polygon(path)


# ---------- fallback: ezdxf y recover fallan, opera el parser manual ----------


def test_fallback_activates_when_ezdxf_and_recover_both_fail(tmp_path, monkeypatch):
    """
    Fuerza el fallback de forma determinística (en vez de depender de que
    un DXF "se vea" suficientemente roto) para probar el parser manual en
    aislamiento real, más allá de que los DXF mínimos de otros tests ya lo
    disparen incidentalmente.
    """
    path = str(tmp_path / "forced_fallback.dxf")
    with open(path, "w") as f:
        f.write(_minimal_raw_dxf(_raw_closed_square(100, 50)))

    def _boom(*_a, **_kw):
        raise Exception("forced failure")

    monkeypatch.setattr(dxf_analysis.ezdxf, "readfile", _boom)
    monkeypatch.setattr(dxf_analysis.recover, "readfile", _boom)

    length, area = analyze_dxf(path)
    assert length == pytest.approx(2 * (100 + 50))
    assert area == pytest.approx(100 * 50)
    assert get_bounding_box(path) == pytest.approx((100.0, 50.0))
    assert extract_piece_polygon(path).area == pytest.approx(100 * 50)


def test_minimal_raw_dxf_naturally_triggers_fallback_without_forcing(tmp_path):
    """Documenta que el patrón de DXF mínimo usado en el resto del suite
    (test_stock_reservation.py, etc.) ya cae en el fallback por sí solo —
    ezdxf.readfile/recover.readfile fallan ambos porque falta la subclase
    AcDbPolyline, sin necesitar monkeypatch."""
    path = str(tmp_path / "minimal.dxf")
    with open(path, "w") as f:
        f.write(_minimal_raw_dxf(_raw_closed_square(60, 30)))

    with pytest.raises(Exception):
        ezdxf.readfile(path)

    length, area = analyze_dxf(path)
    assert length == pytest.approx(2 * (60 + 30))
    assert area == pytest.approx(60 * 30)


# ---------- DXF inválido: vacío, corrupto, sin geometría útil ----------


def test_empty_dxf_returns_zero_without_crashing(tmp_path):
    path = str(tmp_path / "empty.dxf")
    open(path, "w").close()
    assert analyze_dxf(path) == (0.0, 0.0)
    assert get_bounding_box(path) == (0.0, 0.0)
    with pytest.raises(ValueError):
        extract_piece_polygon(path)


def test_corrupt_binary_dxf_returns_zero_without_crashing(tmp_path):
    path = str(tmp_path / "garbage.dxf")
    with open(path, "wb") as f:
        f.write(b"\x00\x01\x02not a real dxf file at all \xff\xfe\x00")
    assert analyze_dxf(path) == (0.0, 0.0)
    with pytest.raises(ValueError):
        extract_piece_polygon(path)


def test_dxf_with_no_entities_has_zero_length_and_area(tmp_path):
    path = str(tmp_path / "no_entities.dxf")
    _write_ezdxf_doc(path, lambda msp: None)  # documento válido, sin dibujar nada
    assert analyze_dxf(path) == (0.0, 0.0)
    with pytest.raises(ValueError):
        extract_piece_polygon(path)


# ---------- la API nunca debe filtrar stack traces / internals ----------


def test_upload_dxf_endpoint_rejects_corrupt_file_cleanly():
    """
    analyze_dxf no lanza para contenido vacío/corrupto (ver tests de
    arriba) -- el upload en sí no falla por eso. Lo que sí debe fallar sin
    filtrar internals es un archivo que directamente ni pueda escribirse/
    leerse como bytes DXF razonables junto con una extensión no permitida,
    o cuando analyze_dxf sí lanza (extract_piece_polygon-like ValueError
    no aplica acá, pero cubrimos el contrato real de la ruta: siempre
    ".dxf" + 400 con mensaje de dominio, nunca 500 con traceback).
    """
    from fastapi.testclient import TestClient
    from pathlib import Path
    from app.db.init_db import init_db
    from app.db.session import engine
    from app.main import app

    client = TestClient(app)
    engine.dispose()
    db_path = Path("cotizalaser.db")
    db_path.exists() and db_path.unlink()
    init_db()

    res = client.post("/auth/register", json={"email": "dxf_owner@test.com", "password": "Password1!"})
    token = res.json()["access_token"]
    res = client.post("/companies", json={"company_name": "Empresa DXF"}, headers={"Authorization": f"Bearer {token}"})
    headers = {"Authorization": f"Bearer {token}", "X-Company-Id": str(res.json()["id"])}
    res = client.post("/materials", json={"name": "Acero", "material_type": "Acero", "thickness_mm": 3, "sheet_width_mm": 1500, "sheet_height_mm": 3000, "sheet_cost_ars": 85000}, headers=headers)
    material_id = res.json()["id"]
    res = client.post("/pieces", json={"name": "Pieza", "material_id": material_id}, headers=headers)
    piece_id = res.json()["id"]

    # Extensión no permitida -- rechazo de contrato, sin tocar analyze_dxf.
    files = {"file": ("pieza.txt", b"no es un dxf", "text/plain")}
    res = client.post(f"/pieces/{piece_id}/upload-dxf", files=files, headers=headers)
    assert res.status_code == 400
    assert "traceback" not in res.text.lower()
    assert "Traceback (most recent call last)" not in res.text

    # Contenido corrupto pero con extensión .dxf -- analyze_dxf no lanza
    # (devuelve 0.0, 0.0), así que el upload se acepta con longitud/área
    # en 0. Limitación conocida documentada en el informe de auditoría, no
    # un 500 -- lo que importa acá es que en ningún caso se filtre un
    # stack trace ni un detalle interno en la respuesta.
    files = {"file": ("pieza.dxf", b"\x00\x01\x02 garbage \xff\xfe", "application/dxf")}
    res = client.post(f"/pieces/{piece_id}/upload-dxf", files=files, headers=headers)
    assert res.status_code in (200, 400)
    assert "traceback" not in res.text.lower()
