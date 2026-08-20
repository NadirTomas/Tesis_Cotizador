from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.machine_config import MachineConfig
from app.models.material import Material
from app.models.piece import Piece
from app.models.quotation import Quotation
from app.models.quotation_item import QuotationItem


# Paso 10: Motor de cálculo automático de cotización
def calculate_quotation_item(db: Session, quotation_item: QuotationItem, company_id: int) -> None:
    """
    Calcula automáticamente los costos y precios de un QuotationItem
    y actualiza el item y su Quotation asociada. Todas las entidades
    relacionadas se validan contra company_id (defensa en profundidad,
    además de la validación que ya hace el router al crear el item).
    """
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
        .first()
    )
    if not machine_config:
        raise ValueError("MachineConfig activo no encontrado para el material")

    quantity = quotation_item.quantity or 0
    margin_percent = quotation_item.margin_percent or 0.0

    cost_material_total = 0.0
    if piece.area_mm2 and piece.area_mm2 > 0:
        area_chapa = material.sheet_width_mm * material.sheet_height_mm
        porcentaje_uso = piece.area_mm2 / area_chapa if area_chapa > 0 else 0.0
        costo_material_unitario = material.sheet_cost_ars * porcentaje_uso
        cost_material_total = costo_material_unitario * quantity

    cost_machine_total = 0.0
    if piece.length_cut_mm and piece.length_cut_mm > 0:
        tiempo_corte_min = piece.length_cut_mm / machine_config.cut_speed_mm_min
        tiempo_total_horas = (
            tiempo_corte_min + machine_config.setup_time_min
        ) / 60.0
        costo_maquina_unitario = (
            tiempo_total_horas * machine_config.machine_cost_per_hour_ars
        )
        cost_machine_total = costo_maquina_unitario * quantity

    cost_labor = cost_machine_total * (machine_config.labor_percent / 100)

    cost_base = cost_material_total + cost_machine_total + cost_labor
    unit_price_ars = 0.0
    total_price_ars = 0.0
    if quantity > 0:
        unit_price_ars = (cost_base / quantity) * (1 + margin_percent / 100)
        total_price_ars = unit_price_ars * quantity

    quotation_item.cost_material_ars = cost_material_total
    quotation_item.cost_machine_ars = cost_machine_total
    quotation_item.cost_labor_ars = cost_labor
    quotation_item.unit_price_ars = unit_price_ars
    quotation_item.total_price_ars = total_price_ars

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
