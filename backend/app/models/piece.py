from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, LargeBinary, String, func
from sqlalchemy.orm import relationship

from app.db.session import Base


# Paso 6: Modelo de Piece
class Piece(Base):
    __tablename__ = "pieces"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=True)
    dxf_data = Column(LargeBinary, nullable=True)  # Archivo DXF en bytes
    dxf_filename = Column(String, nullable=True)  # Nombre original del DXF
    preview_data = Column(LargeBinary, nullable=True)  # PNG preview en bytes
    length_cut_mm = Column(Float, nullable=True)
    area_mm2 = Column(Float, nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    material = relationship("Material", backref="pieces")
