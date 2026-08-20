from dataclasses import dataclass

from shapely import affinity
from shapely.geometry import Polygon

DEFAULT_ANGLES = (0, 90, 180, 270)
MIN_STEP_MM = 5.0
MAX_CANDIDATES_PER_ANGLE = 2000


@dataclass
class Placement:
    rotation: int
    x: float
    y: float


def find_placement(
    piece_polygon: Polygon,
    stock_polygon: Polygon,
    kerf_mm: float = 0.0,
    minimum_spacing_mm: float = 0.0,
    angles: tuple[int, ...] = DEFAULT_ANGLES,
) -> Placement | None:
    """
    Busca una posición y rotación donde `piece_polygon` entra completamente
    dentro de `stock_polygon`, considerando kerf y separación mínima.

    Heurística (no busca el óptimo global — ver plan):
    - Prueba cada ángulo de `angles` en orden; se queda con la PRIMERA
      rotación que logre entrar en algún lado (el score que decide entre
      distintos stocks no depende de la rotación elegida dentro de uno solo).
    - Para cada ángulo, recorre una grilla de posiciones candidatas sobre el
      bounding box del stock, con paso proporcional al tamaño de la pieza
      (nunca menor a MIN_STEP_MM) para no generar una cantidad excesiva de
      candidatos, y con un tope duro (MAX_CANDIDATES_PER_ANGLE) como
      salvaguarda ante piezas muy chicas en chapas muy grandes.
    - Se devuelve la primera posición (izquierda→derecha, abajo→arriba) que
      queda completamente contenida en el stock — heurística tipo
      "bottom-left", simple y determinística.
    """
    for angle in angles:
        rotated = affinity.rotate(piece_polygon, angle, origin="centroid")
        buffer_d = (kerf_mm + minimum_spacing_mm) / 2
        occupied = rotated.buffer(buffer_d) if buffer_d > 0 else rotated
        if occupied.is_empty:
            continue

        # Normalizamos ambas geometrías al origen de la PIEZA (no del área
        # ocupada con el buffer), para que (x, y) reportado sea la posición
        # de la pieza en sí, no del margen de kerf/separación alrededor.
        rminx, rminy, rmaxx, rmaxy = rotated.bounds
        piece_w = rmaxx - rminx
        piece_h = rmaxy - rminy
        occupied_at_piece_origin = affinity.translate(occupied, -rminx, -rminy)

        sminx, sminy, smaxx, smaxy = stock_polygon.bounds
        if piece_w > (smaxx - sminx) or piece_h > (smaxy - sminy):
            continue  # ni el bounding box de la pieza entra, no vale la pena generar grilla

        step = max(MIN_STEP_MM, min(piece_w, piece_h) / 4)

        candidates = 0
        x = sminx
        while x + piece_w <= smaxx:
            y = sminy
            while y + piece_h <= smaxy:
                candidates += 1
                if candidates > MAX_CANDIDATES_PER_ANGLE:
                    break
                candidate = affinity.translate(occupied_at_piece_origin, x, y)
                if stock_polygon.contains(candidate):
                    return Placement(rotation=angle, x=round(x, 2), y=round(y, 2))
                y += step
            if candidates > MAX_CANDIDATES_PER_ANGLE:
                break
            x += step

    return None
