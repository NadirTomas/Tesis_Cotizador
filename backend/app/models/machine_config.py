from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, func
from sqlalchemy.orm import relationship

from app.db.session import Base


class MachineConfig(Base):
    __tablename__ = "machine_configs"

    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False)
    cut_speed_mm_min = Column(Float, nullable=False)
    machine_cost_per_hour_ars = Column(Float, nullable=False)
    setup_time_min = Column(Float, nullable=False)
    labor_percent = Column(Float, nullable=False, default=30.0)
    kerf_mm = Column(Float, nullable=False, default=0.0)
    minimum_spacing_mm = Column(Float, nullable=False, default=0.0)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    material = relationship("Material")
