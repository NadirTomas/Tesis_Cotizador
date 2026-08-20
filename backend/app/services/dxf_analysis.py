import math
from typing import Tuple

import ezdxf
from ezdxf import recover
from shapely.geometry import Point, Polygon


# Paso 7: Análisis básico de DXF (longitud y área)
def analyze_dxf(path: str) -> Tuple[float, float]:
    """
    Analiza un archivo DXF y devuelve:
    - length_cut_mm: longitud total de corte en mm
    - area_mm2: área aproximada en mm^2 (si se puede calcular, sino 0.0)
    """
    try:
        doc = ezdxf.readfile(path)
        msp = doc.modelspace()
        return _analyze_modelspace(msp)
    except Exception:
        try:
            doc, _auditor = recover.readfile(path)
            msp = doc.modelspace()
            return _analyze_modelspace(msp)
        except Exception:
            return _analyze_dxf_fallback(path)


def _analyze_modelspace(msp) -> Tuple[float, float]:
    length_total = 0.0
    area_total = 0.0

    for entity in msp:
        dxftype = entity.dxftype()

        if dxftype == "LINE":
            start = entity.dxf.start
            end = entity.dxf.end
            length_total += math.dist((start.x, start.y), (end.x, end.y))

        elif dxftype == "LWPOLYLINE":
            vertices = [(v[0], v[1]) for v in entity.get_points("xy")]
            if len(vertices) >= 2:
                for idx in range(len(vertices) - 1):
                    length_total += math.dist(vertices[idx], vertices[idx + 1])
                is_closed = entity.closed or getattr(entity, "is_closed", False)
                if is_closed:
                    length_total += math.dist(vertices[-1], vertices[0])
            if entity.closed and len(vertices) >= 3:
                area_total += _polygon_area(vertices)

        elif dxftype == "CIRCLE":
            radius = entity.dxf.radius
            length_total += 2 * math.pi * radius

    return float(length_total), float(area_total)


def _analyze_dxf_fallback(path: str) -> Tuple[float, float]:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            lines = [line.strip() for line in handle.readlines()]
    except Exception as exc:
        raise ValueError(f"DXF inválido o no se pudo leer: {exc}") from exc

    length_total = 0.0
    area_total = 0.0

    idx = 0
    while idx < len(lines) - 1:
        code = lines[idx]
        value = lines[idx + 1]
        if code == "0" and value in {"LINE", "LWPOLYLINE", "CIRCLE"}:
            entity_type = value
            idx += 2
            entity_data = {}
            vertices: list[tuple[float, float]] = []
            is_closed = False
            start = None
            end = None
            center = None
            radius = None

            while idx < len(lines) - 1 and lines[idx] != "0":
                group_code = lines[idx]
                group_value = lines[idx + 1]
                if entity_type == "LINE":
                    if group_code == "10":
                        x = float(group_value)
                        y = float(lines[idx + 3]) if lines[idx + 2] == "20" else None
                        start = (x, y) if y is not None else start
                    elif group_code == "11":
                        x = float(group_value)
                        y = float(lines[idx + 3]) if lines[idx + 2] == "21" else None
                        end = (x, y) if y is not None else end
                elif entity_type == "LWPOLYLINE":
                    if group_code == "70":
                        is_closed = int(group_value) & 1 == 1
                    elif group_code == "10":
                        x = float(group_value)
                        y = float(lines[idx + 3]) if lines[idx + 2] == "20" else None
                        if y is not None:
                            vertices.append((x, y))
                elif entity_type == "CIRCLE":
                    if group_code == "10":
                        x = float(group_value)
                        y = float(lines[idx + 3]) if lines[idx + 2] == "20" else None
                        center = (x, y) if y is not None else center
                    elif group_code == "40":
                        radius = float(group_value)

                idx += 2

            if entity_type == "LINE" and start and end:
                length_total += math.dist(start, end)
            elif entity_type == "LWPOLYLINE":
                if len(vertices) >= 2:
                    for v_idx in range(len(vertices) - 1):
                        length_total += math.dist(vertices[v_idx], vertices[v_idx + 1])
                    if is_closed:
                        length_total += math.dist(vertices[-1], vertices[0])
                if is_closed and len(vertices) >= 3:
                    area_total += _polygon_area(vertices)
            elif entity_type == "CIRCLE" and radius is not None:
                length_total += 2 * math.pi * radius
        else:
            idx += 2

    return float(length_total), float(area_total)


def get_bounding_box(path: str) -> tuple[float, float]:
    """
    Devuelve (width_mm, height_mm) del bounding box de la pieza en el DXF.
    """
    try:
        doc = ezdxf.readfile(path)
        msp = doc.modelspace()
    except Exception:
        try:
            doc, _auditor = recover.readfile(path)
            msp = doc.modelspace()
        except Exception:
            return _bounding_box_fallback(path)

    all_x: list[float] = []
    all_y: list[float] = []

    for entity in msp:
        t = entity.dxftype()
        if t == "LINE":
            all_x += [entity.dxf.start.x, entity.dxf.end.x]
            all_y += [entity.dxf.start.y, entity.dxf.end.y]
        elif t == "LWPOLYLINE":
            for v in entity.get_points("xy"):
                all_x.append(v[0])
                all_y.append(v[1])
        elif t == "CIRCLE":
            cx, cy, r = entity.dxf.center.x, entity.dxf.center.y, entity.dxf.radius
            all_x += [cx - r, cx + r]
            all_y += [cy - r, cy + r]
        elif t == "ARC":
            cx, cy, r = entity.dxf.center.x, entity.dxf.center.y, entity.dxf.radius
            all_x += [cx - r, cx + r]
            all_y += [cy - r, cy + r]

    if not all_x:
        return _bounding_box_fallback(path)

    return max(all_x) - min(all_x), max(all_y) - min(all_y)


def _bounding_box_fallback(path: str) -> tuple[float, float]:
    """
    Igual que `_analyze_dxf_fallback`, pero acumulando el bounding box en vez
    de longitud/área. Se usa cuando ezdxf no puede leer el DXF (mismos DXF
    mínimos/con errores que ya forzaban ese fallback en `analyze_dxf`).
    """
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            lines = [line.strip() for line in handle.readlines()]
    except Exception:
        return 0.0, 0.0

    all_x: list[float] = []
    all_y: list[float] = []

    idx = 0
    while idx < len(lines) - 1:
        code = lines[idx]
        value = lines[idx + 1]
        if code == "0" and value in {"LINE", "LWPOLYLINE", "CIRCLE"}:
            entity_type = value
            idx += 2
            center = None
            radius = None

            while idx < len(lines) - 1 and lines[idx] != "0":
                group_code = lines[idx]
                group_value = lines[idx + 1]
                if entity_type in {"LINE", "LWPOLYLINE"}:
                    if group_code in {"10", "11"}:
                        x = float(group_value)
                        y_code = "20" if group_code == "10" else "21"
                        y = float(lines[idx + 3]) if lines[idx + 2] == y_code else None
                        if y is not None:
                            all_x.append(x)
                            all_y.append(y)
                elif entity_type == "CIRCLE":
                    if group_code == "10":
                        x = float(group_value)
                        y = float(lines[idx + 3]) if lines[idx + 2] == "20" else None
                        center = (x, y) if y is not None else center
                    elif group_code == "40":
                        radius = float(group_value)

                idx += 2

            if entity_type == "CIRCLE" and center is not None and radius is not None:
                cx, cy = center
                all_x += [cx - radius, cx + radius]
                all_y += [cy - radius, cy + radius]
        else:
            idx += 2

    if not all_x:
        return 0.0, 0.0

    return max(all_x) - min(all_x), max(all_y) - min(all_y)


def extract_piece_polygon(path: str) -> Polygon:
    """
    Extrae el contorno 2D de la pieza como un polígono de Shapely (con huecos
    internos si corresponde), para el motor de recomendación de stock.

    Mismo patrón de lectura robusto que analyze_dxf/get_bounding_box. No
    interpreta bulge (arcos dentro de una LWPOLYLINE) — misma simplificación
    que ya tiene el cálculo de longitud/área existente, no es una regresión
    nueva. Si el DXF no puede leerse ni con ezdxf.readfile ni con
    recover.readfile, o no se encuentra ningún contorno cerrado válido, se
    lanza ValueError con un mensaje entendible en vez de seguir de largo con
    una geometría inválida.
    """
    try:
        doc = ezdxf.readfile(path)
        msp = doc.modelspace()
    except Exception:
        try:
            doc, _auditor = recover.readfile(path)
            msp = doc.modelspace()
        except Exception:
            # Mismos DXF mínimos/con errores que ya forzaban el fallback
            # manual en get_bounding_box (p. ej. falta la subclase
            # AcDbPolyline) — se reutiliza el mismo parseo línea por línea.
            return _build_polygon_from_loops(_loops_from_fallback_parse(path))

    return _build_polygon_from_loops(_loops_from_msp(msp))


def _loops_from_msp(msp) -> list[Polygon]:
    loops: list[Polygon] = []
    for entity in msp:
        dxftype = entity.dxftype()
        if dxftype == "LWPOLYLINE":
            is_closed = entity.closed or getattr(entity, "is_closed", False)
            if not is_closed:
                continue
            vertices = [(v[0], v[1]) for v in entity.get_points("xy")]
            if len(vertices) < 3:
                continue
            try:
                poly = Polygon(vertices)
            except Exception:
                continue
            if poly.is_valid and poly.area > 0:
                loops.append(poly)
        elif dxftype == "CIRCLE":
            cx, cy, r = entity.dxf.center.x, entity.dxf.center.y, entity.dxf.radius
            if r > 0:
                loops.append(Point(cx, cy).buffer(r, resolution=32))
    return loops


def _loops_from_fallback_parse(path: str) -> list[Polygon]:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            lines = [line.strip() for line in handle.readlines()]
    except Exception as exc:
        raise ValueError(f"DXF inválido o no se pudo leer: {exc}") from exc

    loops: list[Polygon] = []
    idx = 0
    while idx < len(lines) - 1:
        code = lines[idx]
        value = lines[idx + 1]
        if code == "0" and value in {"LWPOLYLINE", "CIRCLE"}:
            entity_type = value
            idx += 2
            vertices: list[tuple[float, float]] = []
            is_closed = False
            center = None
            radius = None

            while idx < len(lines) - 1 and lines[idx] != "0":
                group_code = lines[idx]
                group_value = lines[idx + 1]
                if entity_type == "LWPOLYLINE":
                    if group_code == "70":
                        is_closed = int(group_value) & 1 == 1
                    elif group_code == "10":
                        x = float(group_value)
                        y = float(lines[idx + 3]) if lines[idx + 2] == "20" else None
                        if y is not None:
                            vertices.append((x, y))
                elif entity_type == "CIRCLE":
                    if group_code == "10":
                        x = float(group_value)
                        y = float(lines[idx + 3]) if lines[idx + 2] == "20" else None
                        center = (x, y) if y is not None else center
                    elif group_code == "40":
                        radius = float(group_value)
                idx += 2

            if entity_type == "LWPOLYLINE" and is_closed and len(vertices) >= 3:
                try:
                    poly = Polygon(vertices)
                except Exception:
                    poly = None
                if poly is not None and poly.is_valid and poly.area > 0:
                    loops.append(poly)
            elif entity_type == "CIRCLE" and center is not None and radius and radius > 0:
                loops.append(Point(center).buffer(radius, resolution=32))
        else:
            idx += 2

    return loops


def _build_polygon_from_loops(loops: list[Polygon]) -> Polygon:
    if not loops:
        raise ValueError("No se pudo obtener un polígono cerrado válido del DXF.")

    loops.sort(key=lambda p: p.area, reverse=True)
    exterior = loops[0]
    holes = [loop.exterior.coords for loop in loops[1:] if exterior.contains(loop)]

    polygon = Polygon(exterior.exterior.coords, holes=holes) if holes else exterior

    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError("El contorno de la pieza no forma un polígono válido.")

    return polygon


def _polygon_area(vertices: list[tuple[float, float]]) -> float:
    area = 0.0
    for idx in range(len(vertices)):
        x1, y1 = vertices[idx]
        x2, y2 = vertices[(idx + 1) % len(vertices)]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0
