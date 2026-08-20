from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.db.session import Base


# Paso 8: Modelo de Quotation (cabecera de presupuesto)
class Quotation(Base):
    __tablename__ = "quotations"
    __table_args__ = (UniqueConstraint("company_id", "number", name="uq_quotation_company_number"),)

    id = Column(Integer, primary_key=True, index=True)
    number = Column(String, nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    issue_date = Column(DateTime, nullable=False)
    due_date = Column(DateTime, nullable=True)
    currency = Column(String, nullable=False, default="ARS")
    exchange_rate = Column(Float, nullable=True)
    notes = Column(String, nullable=True)
    status = Column(String, nullable=False, default="draft")
    total_ars = Column(Float, nullable=False, default=0.0)
    total_usd = Column(Float, nullable=False, default=0.0)
    pdf_data = Column(LargeBinary, nullable=True)  # PDF generado
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    client = relationship("Client")
    items = relationship(
        "QuotationItem", lazy="select", cascade="all, delete-orphan"
    )
