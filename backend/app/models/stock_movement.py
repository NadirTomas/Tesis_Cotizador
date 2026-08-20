from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, func

from app.db.session import Base


class StockMovement(Base):
    """
    Log append-only de auditoría — nunca se lee para decidir el estado
    actual de un stock (eso lo deciden StockSheet.status/StockReservation.status),
    solo sirve para reconstruir el historial ("¿de dónde salió este retazo?").
    """

    __tablename__ = "stock_movements"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    stock_sheet_id = Column(Integer, ForeignKey("stock_sheets.id"), nullable=False, index=True)
    movement_type = Column(String, nullable=False)
    # CREATED | RESERVED | RELEASED | CONSUMED | REMNANT_CREATED | DISCARDED | ADJUSTED
    quotation_id = Column(Integer, ForeignKey("quotations.id"), nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    details = Column(JSON, nullable=True)
