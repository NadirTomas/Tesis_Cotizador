from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry


def rectangle_geojson(width_mm: float, height_mm: float) -> dict:
    """Chapa/retazo rectangular simple, en mm, con origen en (0, 0)."""
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [0, 0],
                [width_mm, 0],
                [width_mm, height_mm],
                [0, height_mm],
                [0, 0],
            ]
        ],
    }


def measure_geometry(geojson: dict) -> tuple[float, float, float]:
    """
    Valida un GeoJSON Polygon y devuelve (area_mm2, bbox_width_mm, bbox_height_mm).
    Lanza ValueError si la geometría es inválida (mal formada, autointersectada,
    o no es un polígono).
    """
    try:
        geom: BaseGeometry = shape(geojson)
    except Exception as exc:
        raise ValueError(f"Geometría inválida: {exc}") from exc

    if geom.geom_type != "Polygon":
        raise ValueError(f"La geometría debe ser un Polygon, se recibió '{geom.geom_type}'")
    if not geom.is_valid or geom.is_empty or geom.area <= 0:
        raise ValueError("El polígono es inválido, está vacío o tiene área nula")

    min_x, min_y, max_x, max_y = geom.bounds
    return geom.area, max_x - min_x, max_y - min_y
