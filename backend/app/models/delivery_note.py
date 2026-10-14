from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.db.session import Base

DRAFT = "DRAFT"
ISSUED = "ISSUED"
VOIDED = "VOIDED"
DELIVERY_NOTE_STATUSES = (DRAFT, ISSUED, VOIDED)


class DeliveryNote(Base):
    """Remito de entrega asociado a una cotización aceptada.

    Solo los remitos ISSUED cuentan como entrega efectiva. Los datos del
    cliente y de la cotización se copian ("foto") al emitir, para que el
    documento histórico no cambie si después se edita el cliente."""

    __tablename__ = "delivery_notes"
    __table_args__ = (
        UniqueConstraint("company_id", "number", name="uq_delivery_note_company_number"),
        CheckConstraint("status IN ('DRAFT', 'ISSUED', 'VOIDED')", name="ck_delivery_note_status"),
        Index("ix_delivery_notes_company_quotation", "company_id", "quotation_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    quotation_id = Column(Integer, ForeignKey("quotations.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    # NULL mientras es borrador: el número se asigna al emitir (sin huecos).
    number = Column(String, nullable=True)
    status = Column(String, nullable=False, default=DRAFT)
    issue_date = Column(DateTime, nullable=True)
    notes = Column(String, nullable=True)

    quotation_number = Column(String, nullable=False)
    client_name = Column(String, nullable=False)
    client_tax_id = Column(String, nullable=True)
    client_address = Column(String, nullable=True)

    issued_at = Column(DateTime, nullable=True)
    issued_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    voided_at = Column(DateTime, nullable=True)
    voided_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    void_reason = Column(String, nullable=True)

    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    items = relationship(
        "DeliveryNoteItem",
        cascade="all, delete-orphan",
        order_by="DeliveryNoteItem.id",
        lazy="select",
    )
    quotation = relationship("Quotation")


class DeliveryNoteItem(Base):
    __tablename__ = "delivery_note_items"
    __table_args__ = (
        UniqueConstraint("delivery_note_id", "quotation_item_id", name="uq_delivery_note_item_line"),
        CheckConstraint("quantity > 0", name="ck_delivery_note_item_quantity_positive"),
    )

    id = Column(Integer, primary_key=True, index=True)
    delivery_note_id = Column(Integer, ForeignKey("delivery_notes.id", ondelete="CASCADE"), nullable=False, index=True)
    quotation_item_id = Column(Integer, ForeignKey("quotation_items.id"), nullable=False, index=True)
    piece_id = Column(Integer, ForeignKey("pieces.id"), nullable=True)
    piece_name = Column(String, nullable=False)
    piece_description = Column(String, nullable=True)
    quantity = Column(Integer, nullable=False)
    unit = Column(String, nullable=False, default="un")
