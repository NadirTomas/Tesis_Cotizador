from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, func
from sqlalchemy.orm import relationship

from app.db.session import Base


# Paso 8: Modelo de QuotationItem (detalle de presupuesto)
class QuotationItem(Base):
    __tablename__ = "quotation_items"

    id = Column(Integer, primary_key=True, index=True)
    quotation_id = Column(Integer, ForeignKey("quotations.id"), nullable=False)
    piece_id = Column(Integer, ForeignKey("pieces.id"), nullable=False)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    cost_material_ars = Column(Float, nullable=False, default=0.0)
    cost_machine_ars = Column(Float, nullable=False, default=0.0)
    cost_labor_ars = Column(Float, nullable=False, default=0.0)
    margin_percent = Column(Float, nullable=False, default=0.0)
    unit_price_ars = Column(Float, nullable=False, default=0.0)
    total_price_ars = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    quotation = relationship("Quotation", overlaps="items")
    piece = relationship("Piece")
    material = relationship("Material")
