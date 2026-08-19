"""
Genera archivos DXF de prueba en data/dxf/
Ejecutar con: venv/Scripts/python generate_test_dxf.py
"""
import math
from pathlib import Path

import ezdxf

OUTPUT_DIR = Path("data/dxf")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def create_bracket():
    """Bracket rectangular 100x50mm con 4 agujeros de 8mm."""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()

    # Contorno exterior (LWPOLYLINE cerrada)
    points = [(0, 0), (100, 0), (100, 50), (0, 50)]
    msp.add_lwpolyline(points, close=True)

    # 4 agujeros (círculos r=4mm)
    for cx, cy in [(15, 10), (85, 10), (15, 40), (85, 40)]:
        msp.add_circle((cx, cy), radius=4)

    path = OUTPUT_DIR / "bracket_100x50.dxf"
    doc.saveas(str(path))
    print(f"  Creado: {path}")


def create_panel():
    """Panel rectangular 200x120mm con ranura central y agujeros."""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()

    # Contorno exterior
    msp.add_lwpolyline([(0, 0), (200, 0), (200, 120), (0, 120)], close=True)

    # Ranura central (rectángulo interior 80x20mm centrado)
    msp.add_lwpolyline([(60, 50), (140, 50), (140, 70), (60, 70)], close=True)

    # 6 agujeros de montaje (r=5mm)
    for cx, cy in [(15, 15), (100, 15), (185, 15), (15, 105), (100, 105), (185, 105)]:
        msp.add_circle((cx, cy), radius=5)

    path = OUTPUT_DIR / "panel_200x120.dxf"
    doc.saveas(str(path))
    print(f"  Creado: {path}")


def create_disc():
    """Disco circular de 80mm de diámetro con agujero central de 20mm."""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()

    # Circunferencia exterior (r=40mm)
    msp.add_circle((0, 0), radius=40)

    # Agujero central (r=10mm)
    msp.add_circle((0, 0), radius=10)

    # 6 agujeros de paso equidistantes (r=4mm, a 28mm del centro)
    for i in range(6):
        angle = math.radians(i * 60)
        cx = 28 * math.cos(angle)
        cy = 28 * math.sin(angle)
        msp.add_circle((cx, cy), radius=4)

    path = OUTPUT_DIR / "disco_d80.dxf"
    doc.saveas(str(path))
    print(f"  Creado: {path}")


if __name__ == "__main__":
    print("Generando DXF de prueba...")
    create_bracket()
    create_panel()
    create_disc()
    print("\nListo. Archivos en:", OUTPUT_DIR.resolve())
    print("\nDimensiones aproximadas:")
    print("  bracket_100x50.dxf  → contorno 100×50mm + 4 agujeros ø8mm")
    print("  panel_200x120.dxf   → contorno 200×120mm + ranura + 6 agujeros ø10mm")
    print("  disco_d80.dxf       → disco ø80mm + agujero central ø20mm + 6 agujeros ø8mm")
