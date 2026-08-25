from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, func

from app.db.session import Base


class StockReservation(Base):
    """
    Reserva de un StockSheet contra una cotización aceptada. A lo sumo una
    reserva ACTIVE por stock_sheet a la vez (seguridad antes que
    complejidad — nada de múltiples piezas por chapa en esta versión).
    """

    __tablename__ = "stock_reservations"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    stock_sheet_id = Column(Integer, ForeignKey("stock_sheets.id"), nullable=False, index=True)
    piece_id = Column(Integer, ForeignKey("pieces.id"), nullable=False)
    quotation_id = Column(Integer, ForeignKey("quotations.id"), nullable=False)
    quotation_item_id = Column(Integer, ForeignKey("quotation_items.id", ondelete="SET NULL"), nullable=True)
    rotation = Column(Integer, nullable=False)
    x = Column(Float, nullable=False)
    y = Column(Float, nullable=False)
    status = Column(String, nullable=False, default="ACTIVE")  # ACTIVE | RELEASED | CONSUMED
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
