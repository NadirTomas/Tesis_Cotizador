"""
Genera una imagen PNG de preview a partir de un archivo DXF.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # sin GUI, siempre antes de importar pyplot
import matplotlib.pyplot as plt
import ezdxf
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend


_LINE_COLOR = "#1A1A2E"
_LINE_WIDTH = 1.8


def generate_dxf_preview(dxf_path: str, output_path: str, size_px: int = 500) -> str:
    """
    Renderiza el DXF en dxf_path y guarda un PNG en output_path.
    Fondo blanco, líneas oscuras (apto para PDF).
    Devuelve output_path.
    """
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()

    dpi = 150
    size_in = size_px / dpi

    fig, ax = plt.subplots(figsize=(size_in, size_in), dpi=dpi)
    ax.set_aspect("equal")

    backend = MatplotlibBackend(ax)
    Frontend(RenderContext(doc), backend).draw_layout(msp)

    # Las entidades DXF son blancas por defecto; forzar a oscuro para fondo blanco
    for patch in ax.patches:
        patch.set_edgecolor(_LINE_COLOR)
        patch.set_linewidth(_LINE_WIDTH)
        patch.set_facecolor("none")
    for line in ax.lines:
        line.set_color(_LINE_COLOR)
        line.set_linewidth(_LINE_WIDTH)
    for col in ax.collections:
        try:
            col.set_edgecolor(_LINE_COLOR)
            col.set_linewidth(_LINE_WIDTH)
        except Exception:
            pass

    ax.set_facecolor("#FFFFFF")
    fig.patch.set_facecolor("#FFFFFF")
    ax.axis("off")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight", facecolor="#FFFFFF", pad_inches=0.05)
    plt.close(fig)

    return output_path
