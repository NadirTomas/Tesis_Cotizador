from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func

from app.db.session import Base


class QuotationEvent(Base):
    __tablename__ = "quotation_events"

    id = Column(Integer, primary_key=True, index=True)
    quotation_id = Column(Integer, ForeignKey("quotations.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String, nullable=False)
    description = Column(String, nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
