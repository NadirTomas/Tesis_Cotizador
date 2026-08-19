from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, func

from app.db.session import Base


class Material(Base):
    __tablename__ = "materials"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    thickness_mm = Column(Float, nullable=False)
    sheet_width_mm = Column(Float, nullable=False)
    sheet_height_mm = Column(Float, nullable=False)
    sheet_cost_ars = Column(Float, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
