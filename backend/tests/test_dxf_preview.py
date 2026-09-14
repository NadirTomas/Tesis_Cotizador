"""
Cobertura de dxf_preview.py — antes de este archivo, cero tests dedicados
(hallazgo P1 de la auditoría de contexto de 2026-09-14), pese a ser parte
del flujo crítico de carga de piezas (routes_pieces.py::_process_dxf_upload
genera el preview inmediatamente después de analizar el DXF).

Bug encontrado escribiendo la primera versión de estos tests, corregido
en un commit separado: generate_dxf_preview() solo intentaba
ezdxf.readfile() -- a diferencia de analyze_dxf()/get_bounding_box()/
extract_piece_polygon(), que ya tenían un fallback a ezdxf.recover
(mismo patrón que el incidente histórico de get_bounding_box(),
PROJECT_MEMORY.md §7, corregido en 3199c15). Un DXF con errores
estructurales menores analizaba y cotizaba bien pero perdía su preview
en silencio. Ahora generate_dxf_preview() tiene el mismo fallback de 2
niveles (readfile -> recover.readfile); ver
test_recover_level_dxf_now_falls_back_and_generates_preview.
"""

from pathlib import Path

import ezdxf
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.db.init_db import init_db
from app.db.session import engine
from app.main import app
from app.services.dxf_preview import generate_dxf_preview

client = TestClient(app)


# ---------- helpers ----------


def _write_ezdxf_doc(path, build_fn) -> str:
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    build_fn(msp)
    doc.saveas(path)
    return path


def _minimal_raw_dxf(entities_text: str) -> str:
    return f"0\nSECTION\n2\nENTITIES\n{entities_text}0\nENDSEC\n0\nEOF\n"


# ---------- casos válidos: rectángulo, círculo, múltiples entidades ----------


def test_rectangle_generates_valid_png(tmp_path):
    dxf_path = _write_ezdxf_doc(
        str(tmp_path / "rect.dxf"),
        lambda msp: msp.add_lwpolyline([(0, 0), (100, 0), (100, 50), (0, 50)], close=True),
    )
    out_path = str(tmp_path / "rect.png")

    result = generate_dxf_preview(dxf_path, out_path)

    assert result == out_path
    assert Path(out_path).exists()
    assert Path(out_path).stat().st_size > 0
    with Image.open(out_path) as img:
        img.verify()  # lanza si el PNG está corrupto/incompleto
    with Image.open(out_path) as img:
        assert img.format == "PNG"
        assert img.mode in ("RGB", "RGBA")
        assert img.width > 0 and img.height > 0


def test_circle_generates_valid_png(tmp_path):
    dxf_path = _write_ezdxf_doc(str(tmp_path / "circle.dxf"), lambda msp: msp.add_circle((0, 0), 40.0))
    out_path = str(tmp_path / "circle.png")

    generate_dxf_preview(dxf_path, out_path)

    with Image.open(out_path) as img:
        img.verify()
    with Image.open(out_path) as img:
        assert img.format == "PNG"


def test_multiple_mixed_entities_generates_valid_png(tmp_path):
    def build(msp):
        msp.add_lwpolyline([(0, 0), (100, 0), (100, 100), (0, 100)], close=True)
        msp.add_lwpolyline([(20, 20), (40, 20), (40, 40), (20, 40)], close=True)  # agujero
        msp.add_circle((70, 70), 15.0)
        msp.add_line((0, 0), (100, 100))

    dxf_path = _write_ezdxf_doc(str(tmp_path / "mixed.dxf"), build)
    out_path = str(tmp_path / "mixed.png")

    generate_dxf_preview(dxf_path, out_path)

    with Image.open(out_path) as img:
        img.verify()


# ---------- dimensiones / viewport ----------


def test_output_size_roughly_matches_requested_size_px(tmp_path):
    """
    fig.savefig usa bbox_inches="tight", que recorta al contenido real --
    no da un tamaño exacto en píxeles, pero sí debería quedar en el mismo
    orden de magnitud que size_px para una figura cuadrada simple.
    """
    dxf_path = _write_ezdxf_doc(
        str(tmp_path / "square.dxf"),
        lambda msp: msp.add_lwpolyline([(0, 0), (100, 0), (100, 100), (0, 100)], close=True),
    )
    out_path = str(tmp_path / "square.png")

    generate_dxf_preview(dxf_path, out_path, size_px=400)

    with Image.open(out_path) as img:
        # tolerancia amplia por el recorte de bbox_inches="tight" + el padding fijo
        assert 200 <= img.width <= 700
        assert 200 <= img.height <= 700


def test_creates_missing_output_directory(tmp_path):
    dxf_path = _write_ezdxf_doc(
        str(tmp_path / "rect2.dxf"),
        lambda msp: msp.add_lwpolyline([(0, 0), (10, 0), (10, 10), (0, 10)], close=True),
    )
    nested_out = str(tmp_path / "nested" / "dir" / "preview.png")
    assert not Path(nested_out).parent.exists()

    generate_dxf_preview(dxf_path, nested_out)

    assert Path(nested_out).exists()


# ---------- edge cases ----------


def test_empty_modelspace_produces_blank_image_without_crashing(tmp_path):
    """
    DXF mínimo pero estructuralmente válido (SECTION/ENTITIES/ENDSEC sin
    ninguna entidad adentro) -- a diferencia de los DXF mínimos con
    entidades reales usados en otros tests (que fallan por faltarles la
    subclase AcDbPolyline), este SÍ lo lee ezdxf.readfile() directo sin
    problema, porque no hay ninguna entidad que validar. Resultado real
    verificado: una imagen en blanco válida, sin excepción.
    """
    path = tmp_path / "empty.dxf"
    path.write_text(_minimal_raw_dxf(""))
    out_path = str(tmp_path / "empty.png")

    generate_dxf_preview(str(path), out_path)

    with Image.open(out_path) as img:
        img.verify()


def test_corrupt_file_with_dxf_extension_raises(tmp_path):
    """
    A diferencia de analyze_dxf() (que devuelve (0.0, 0.0) ante contenido
    corrupto, ver test_dxf_analysis.py::test_corrupt_binary_dxf_returns_zero_without_crashing),
    generate_dxf_preview() no tiene ningún manejo de error propio -- deja
    que la excepción de ezdxf se propague. El caller real
    (routes_pieces.py::_process_dxf_upload) es quien la atrapa y trata el
    preview como no-crítico (preview_data=None). Este test fija ese
    contrato: la función en sí debe seguir lanzando, no tragarse el error.
    """
    path = tmp_path / "corrupt.dxf"
    path.write_bytes(b"\x00\x01\x02 esto no es un dxf \xff\xfe")
    out_path = str(tmp_path / "corrupt.png")

    with pytest.raises(Exception):
        generate_dxf_preview(str(path), out_path)

    assert not Path(out_path).exists()


def test_nonexistent_input_file_raises(tmp_path):
    with pytest.raises(Exception):
        generate_dxf_preview(str(tmp_path / "no_existe.dxf"), str(tmp_path / "out.png"))


# ---------- fallback a recover.readfile() (fix del bug encontrado) ----------


def test_recover_level_dxf_now_falls_back_and_generates_preview(tmp_path, monkeypatch):
    """
    Antes del fix: un DXF con un error estructural menor -- del tipo que
    ezdxf.recover.readfile() sabe recuperar -- se analizaba y cotizaba
    perfectamente bien (analyze_dxf ya usaba ese nivel de fallback), pero
    generate_dxf_preview() solo probaba ezdxf.readfile() directo y perdía
    el preview en silencio para el mismo archivo. Ahora tiene el mismo
    fallback de 2 niveles que analyze_dxf()/get_bounding_box()/
    extract_piece_polygon() -- este test confirma que, forzando el mismo
    tipo de fallo, el preview SÍ se genera correctamente vía recover.
    """
    import app.services.dxf_preview as preview_module

    dxf_path = _write_ezdxf_doc(
        str(tmp_path / "recoverable.dxf"),
        lambda msp: msp.add_lwpolyline([(0, 0), (100, 0), (100, 50), (0, 50)], close=True),
    )
    out_path = str(tmp_path / "recoverable.png")

    def _boom(*_a, **_kw):
        raise Exception("simula un DXF con error estructural menor que ezdxf.readfile() rechaza")

    monkeypatch.setattr(preview_module.ezdxf, "readfile", _boom)

    result = generate_dxf_preview(dxf_path, out_path)

    assert result == out_path
    with Image.open(out_path) as img:
        img.verify()

    # Prueba de contraste: el MISMO archivo, con el MISMO tipo de fallo
    # forzado, también se analiza correctamente vía el fallback a recover
    # que analyze_dxf() ya tenía -- confirma que ambos caminos ahora se
    # recuperan igual, no que el preview "de casualidad" funcionó.
    import app.services.dxf_analysis as analysis_module
    monkeypatch.setattr(analysis_module.ezdxf, "readfile", _boom)
    length, area = analysis_module.analyze_dxf(dxf_path)
    assert area == pytest.approx(100 * 50)


def test_truly_corrupt_dxf_still_fails_even_with_recover_fallback(tmp_path):
    """
    El fallback nuevo tiene un límite real: contenido que no es DXF en
    absoluto (no solo "readfile estricto lo rechaza") tampoco lo puede
    recuperar ezdxf.recover.readfile() -- generate_dxf_preview() debe
    seguir lanzando en ese caso, para que el caller lo siga tratando como
    no-crítico (mismo contrato de test_corrupt_file_with_dxf_extension_raises,
    repetido acá explícitamente después del fix para no asumir que
    "ahora todo se recupera").
    """
    path = tmp_path / "truly_corrupt.dxf"
    path.write_bytes(b"\x00\x01\x02 esto no es un dxf en absoluto \xff\xfe" * 20)
    out_path = str(tmp_path / "truly_corrupt.png")

    with pytest.raises(Exception):
        generate_dxf_preview(str(path), out_path)
    assert not Path(out_path).exists()


# ---------- integración real: carga de pieza vía API -> has_preview -> endpoint ----------


def _setup_owner(email="dxf_preview_owner@test.com") -> dict:
    engine.dispose()
    db_path = Path("cotizalaser.db")
    db_path.exists() and db_path.unlink()
    init_db()
    res = client.post("/auth/register", json={"email": email, "password": "Password1!"})
    token = res.json()["access_token"]
    res = client.post("/companies", json={"company_name": "Empresa Preview"}, headers={"Authorization": f"Bearer {token}"})
    return {"Authorization": f"Bearer {token}", "X-Company-Id": str(res.json()["id"])}


def test_piece_upload_sets_has_preview_and_serves_real_png(tmp_path):
    """
    Integración de punta a punta: subir una pieza con un DXF normal debe
    dejar has_preview=True, y GET /pieces/{id}/preview debe servir un PNG
    real (no solo que el campo booleano esté prendido).
    """
    headers = _setup_owner()
    dxf_path = _write_ezdxf_doc(
        str(tmp_path / "piece.dxf"),
        lambda msp: msp.add_lwpolyline([(0, 0), (80, 0), (80, 40), (0, 40)], close=True),
    )
    with open(dxf_path, "rb") as fh:
        res = client.post(
            "/pieces",
            data={"name": "Pieza con preview"},
            files={"file": ("piece.dxf", fh.read(), "application/dxf")},
            headers=headers,
        )
    assert res.status_code == 200
    piece = res.json()
    assert piece["has_preview"] is True

    preview_res = client.get(f"/pieces/{piece['id']}/preview", headers=headers)
    assert preview_res.status_code == 200
    assert preview_res.headers["content-type"] == "image/png"
    assert len(preview_res.content) > 0


def test_piece_with_recover_level_dxf_gets_preview_after_fix(tmp_path, monkeypatch):
    """
    Consecuencia real, de punta a punta, del fix: un DXF recuperable solo
    vía ezdxf.recover ahora crea la pieza con geometría correcta Y con
    preview generado (antes del fix, has_preview quedaba en False para
    este mismo caso -- ver el commit del fix para el test que documentaba
    el bug).
    """
    import app.services.dxf_preview as preview_module

    headers = _setup_owner("dxf_preview_owner2@test.com")
    dxf_path = _write_ezdxf_doc(
        str(tmp_path / "recoverable.dxf"),
        lambda msp: msp.add_lwpolyline([(0, 0), (60, 0), (60, 30), (0, 30)], close=True),
    )

    def _boom(*_a, **_kw):
        raise Exception("simula DXF con error estructural menor")

    monkeypatch.setattr(preview_module.ezdxf, "readfile", _boom)

    with open(dxf_path, "rb") as fh:
        res = client.post(
            "/pieces",
            data={"name": "Pieza con preview via recover"},
            files={"file": ("recoverable.dxf", fh.read(), "application/dxf")},
            headers=headers,
        )
    assert res.status_code == 200
    piece = res.json()
    assert piece["has_preview"] is True
    assert piece["area_mm2"] == pytest.approx(60 * 30)

    preview_res = client.get(f"/pieces/{piece['id']}/preview", headers=headers)
    assert preview_res.status_code == 200
    assert preview_res.headers["content-type"] == "image/png"
