from dataclasses import dataclass

from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry


@dataclass
class RemnantCandidate:
    geometry: Polygon
    area_mm2: float
    width_mm: float
    height_mm: float


def compute_remnants(
    stock_geometry: Polygon,
    occupied_geometry: Polygon,
    minimum_area_mm2: float,
    minimum_width_mm: float | None = None,
    minimum_height_mm: float | None = None,
) -> list[RemnantCandidate]:
    """
    Resta la geometría ocupada por la pieza (ya con su buffer de kerf/
    separación aplicado) de la geometría actual del stock, y devuelve los
    fragmentos resultantes que valen la pena conservar como retazo.

    `difference()` puede devolver un Polygon, un MultiPolygon, o geometría
    vacía/degenerada (líneas o puntos sin área — artefacto normal de la
    resta cuando los bordes coinciden exactamente). Se normaliza todo a una
    lista de Polygon reales, y se descarta cualquier fragmento que no supere
    el mínimo configurado (área, y si están definidos, ancho/alto) — ese
    material se pierde como scrap real, no se persiste.
    """
    remaining: BaseGeometry = stock_geometry.difference(occupied_geometry)

    if remaining.is_empty:
        polygons: list[Polygon] = []
    elif remaining.geom_type == "Polygon":
        polygons = [remaining]
    elif remaining.geom_type in ("MultiPolygon", "GeometryCollection"):
        polygons = [g for g in remaining.geoms if g.geom_type == "Polygon" and not g.is_empty]
    else:
        polygons = []

    candidates: list[RemnantCandidate] = []
    for poly in polygons:
        if not poly.is_valid or poly.area <= 0:
            continue
        if poly.area < minimum_area_mm2:
            continue
        minx, miny, maxx, maxy = poly.bounds
        width, height = maxx - minx, maxy - miny
        if minimum_width_mm is not None and width < minimum_width_mm:
            continue
        if minimum_height_mm is not None and height < minimum_height_mm:
            continue
        candidates.append(RemnantCandidate(geometry=poly, area_mm2=poly.area, width_mm=width, height_mm=height))

    return candidates
