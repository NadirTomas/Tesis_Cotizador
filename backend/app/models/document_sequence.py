from sqlalchemy import Column, ForeignKey, Integer, String, UniqueConstraint

from app.db.session import Base


class DocumentSequence(Base):
    """Contador de numeración consecutiva por empresa y tipo de documento.

    Se incrementa con un UPDATE atómico (ver services/document_numbering.py):
    la fila queda bloqueada hasta el fin de la transacción, así dos emisiones
    simultáneas nunca obtienen el mismo número, y si la transacción se revierte
    el número vuelve a quedar libre (sin huecos)."""

    __tablename__ = "document_sequences"
    __table_args__ = (UniqueConstraint("company_id", "doc_type", name="uq_document_sequence_company_type"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    doc_type = Column(String, nullable=False)
    last_number = Column(Integer, nullable=False, default=0)
