from dataclasses import dataclass

from shapely.geometry import Polygon, shape
from sqlalchemy.orm import Session

from app.models.machine_config import MachineConfig
from app.models.material import Material
from app.models.stock_sheet import StockSheet
from app.services.stock_placement import find_placement

REMNANT_SCORE_WEIGHT = 0.4
UTILIZATION_SCORE_WEIGHT = 0.6


@dataclass
class RecommendationResult:
    stock_sheet: StockSheet
    rotation: int
    x: float
    y: float
    piece_area_mm2: float
    utilization_percent: float
    score: float
    reason: str


def recommend_stock_for_piece(
    db: Session, company_id: int, piece_polygon: Polygon, material_id: int
) -> list[RecommendationResult]:
    """
    Busca, dentro del stock AVAILABLE de la empresa activa, todas las chapas
    o retazos compatibles (mismo tipo/calidad/espesor) que contienen la
    pieza, puntuados y ordenados de mejor a peor — el primero es "la
    recomendación", el resto son las alternativas.

    Estrategia (ver plan para el detalle completo):
    1. filtrar stock compatible por company_id + material_type/alloy/
       thickness_mm + status AVAILABLE;
    2. ordenar candidatos con retazos primero, y de menor a mayor área
       restante dentro de cada grupo (best-fit);
    3. para cada candidato, intentar ubicar la pieza (find_placement);
    4. descartar los que no entran;
    5. puntuar los que sí entran y devolver todos, ordenados por score.

    No modifica ningún StockSheet — es puro análisis/recomendación.
    """
    material = db.query(Material).filter(Material.id == material_id, Material.company_id == company_id).first()
    if not material:
        raise ValueError("Material no encontrado")

    machine_config = (
        db.query(MachineConfig)
        .filter(
            MachineConfig.material_id == material.id,
            MachineConfig.company_id == company_id,
            MachineConfig.active.is_(True),
        )
        .order_by(MachineConfig.id)
        .first()
    )
    if not machine_config:
        raise ValueError("No hay configuración de máquina activa para este material")

    material_type_filter = (
        Material.material_type.is_(None) if material.material_type is None else Material.material_type == material.material_type
    )
    alloy_filter = Material.alloy.is_(None) if material.alloy is None else Material.alloy == material.alloy

    candidates_query = (
        db.query(StockSheet)
        .join(Material, Material.id == StockSheet.material_id)
        .filter(
            StockSheet.company_id == company_id,
            StockSheet.status == "AVAILABLE",
            material_type_filter,
            alloy_filter,
            Material.thickness_mm == material.thickness_mm,
        )
    )

    candidates = candidates_query.all()
    # Retazos antes que chapas completas, y dentro de cada grupo el de menor
    # área restante primero (best-fit: no gastar un stock grande de más).
    candidates.sort(key=lambda s: (0 if s.stock_type == "REMNANT" else 1, s.remaining_area_mm2))

    piece_area = piece_polygon.area
    results: list[RecommendationResult] = []

    for stock in candidates:
        stock_polygon = shape(stock.geometry)
        placement = find_placement(
            piece_polygon, stock_polygon, machine_config.kerf_mm, machine_config.minimum_spacing_mm
        )
        if placement is None:
            continue

        utilization_ratio = min(piece_area / stock.remaining_area_mm2, 1.0) if stock.remaining_area_mm2 > 0 else 0.0
        remnant_bonus = 1.0 if stock.stock_type == "REMNANT" else 0.0
        score = UTILIZATION_SCORE_WEIGHT * utilization_ratio + REMNANT_SCORE_WEIGHT * remnant_bonus
        utilization_percent = round(utilization_ratio * 100, 1)

        reason = f"{stock.code} recomendado: contiene la pieza, aprovechamiento del {utilization_percent}% sobre ese stock"
        if stock.stock_type == "REMNANT":
            reason += ", prioriza un retazo existente antes que una chapa nueva."
        else:
            reason += "."

        results.append(
            RecommendationResult(
                stock_sheet=stock,
                rotation=placement.rotation,
                x=placement.x,
                y=placement.y,
                piece_area_mm2=round(piece_area, 2),
                utilization_percent=utilization_percent,
                score=round(score, 4),
                reason=reason,
            )
        )

    results.sort(key=lambda r: r.score, reverse=True)
    return results
