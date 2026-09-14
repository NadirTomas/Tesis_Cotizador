from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.machine_config import MachineConfig
from app.models.material import Material
from app.models.piece import Piece
from app.models.quotation import Quotation
from app.models.quotation_item import QuotationItem


@dataclass(frozen=True)
class QuotationItemCosts:
    cost_material_ars: float
    cost_machine_ars: float
    cost_labor_ars: float
    unit_price_ars: float
    total_price_ars: float


def compute_item_costs(
    area_mm2: float | None,
    length_cut_mm: float | None,
    material: Material,
    machine_config: MachineConfig,
    quantity: int,
    margin_percent: float,
) -> QuotationItemCosts:
    """
    Fórmula de costeo pura, sin acceso a DB — única fuente de verdad del
    cálculo. Recibe geometría como escalares (no un Piece completo) para
    que scripts de recálculo puedan previsualizar costos con una
    geometría hipotética sin mutar ningún objeto ORM real.
    """
    cost_material_total = 0.0
    if area_mm2 and area_mm2 > 0:
        area_chapa = material.sheet_width_mm * material.sheet_height_mm
        porcentaje_uso = area_mm2 / area_chapa if area_chapa > 0 else 0.0
        costo_material_unitario = material.sheet_cost_ars * porcentaje_uso
        cost_material_total = costo_material_unitario * quantity

    cost_machine_total = 0.0
    if length_cut_mm and length_cut_mm > 0:
        # setup_time_min se cobra UNA sola vez por lote/trabajo, no por
        # unidad -- confirmado con Cortesar el 2026-09-14. El tiempo de
        # corte sí escala con quantity (cada unidad se corta individualmente).
        tiempo_corte_total_min = (length_cut_mm * quantity) / machine_config.cut_speed_mm_min
        tiempo_total_horas = (
            tiempo_corte_total_min + machine_config.setup_time_min
        ) / 60.0
        cost_machine_total = tiempo_total_horas * machine_config.machine_cost_per_hour_ars

    cost_labor = cost_machine_total * (machine_config.labor_percent / 100)

    cost_base = cost_material_total + cost_machine_total + cost_labor
    unit_price_ars = 0.0
    total_price_ars = 0.0
    if quantity > 0:
        unit_price_ars = (cost_base / quantity) * (1 + margin_percent / 100)
        total_price_ars = unit_price_ars * quantity

    return QuotationItemCosts(
        cost_material_ars=cost_material_total,
        cost_machine_ars=cost_machine_total,
        cost_labor_ars=cost_labor,
        unit_price_ars=unit_price_ars,
        total_price_ars=total_price_ars,
    )


def fetch_item_costing_context(
    db: Session, quotation_item: QuotationItem, company_id: int
) -> tuple[Piece, Material, MachineConfig]:
    """Resuelve pieza/material/config de máquina de un ítem, validados contra company_id."""
    piece = (
        db.query(Piece)
        .filter(Piece.id == quotation_item.piece_id, Piece.company_id == company_id)
        .first()
    )
    if not piece:
        raise ValueError("Piece asociada no encontrada")

    material = (
        db.query(Material)
        .filter(Material.id == quotation_item.material_id, Material.company_id == company_id)
        .first()
    )
    if not material:
        raise ValueError("Material asociado no encontrado")

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
        raise ValueError("MachineConfig activo no encontrado para el material")

    return piece, material, machine_config


# Paso 10: Motor de cálculo automático de cotización
def calculate_quotation_item(db: Session, quotation_item: QuotationItem, company_id: int) -> None:
    """
    Calcula automáticamente los costos y precios de un QuotationItem
    y actualiza el item y su Quotation asociada. Todas las entidades
    relacionadas se validan contra company_id (defensa en profundidad,
    además de la validación que ya hace el router al crear el item).
    """
    piece, material, machine_config = fetch_item_costing_context(db, quotation_item, company_id)

    # Nota: `or 0` trataría -5 como válido (solo 0 es falsy). quantity/margin_percent
    # ya vienen validados como positivos por el schema; esto es solo el fallback None.
    quantity = quotation_item.quantity if quotation_item.quantity is not None else 0
    margin_percent = quotation_item.margin_percent if quotation_item.margin_percent is not None else 0.0

    costs = compute_item_costs(
        piece.area_mm2, piece.length_cut_mm, material, machine_config, quantity, margin_percent
    )
    quotation_item.cost_material_ars = costs.cost_material_ars
    quotation_item.cost_machine_ars = costs.cost_machine_ars
    quotation_item.cost_labor_ars = costs.cost_labor_ars
    quotation_item.unit_price_ars = costs.unit_price_ars
    quotation_item.total_price_ars = costs.total_price_ars

    quotation = (
        db.query(Quotation)
        .filter(Quotation.id == quotation_item.quotation_id, Quotation.company_id == company_id)
        .first()
    )
    if not quotation:
        raise ValueError("Quotation asociada no encontrada")

    db.flush()
    total_ars = (
        db.query(func.coalesce(func.sum(QuotationItem.total_price_ars), 0.0))
        .filter(QuotationItem.quotation_id == quotation.id)
        .scalar()
    )
    quotation.total_ars = float(total_ars or 0.0)
    if quotation.exchange_rate and quotation.exchange_rate > 0:
        quotation.total_usd = quotation.total_ars / quotation.exchange_rate
    else:
        quotation.total_usd = 0.0

    db.commit()
    db.refresh(quotation_item)
    db.refresh(quotation)
