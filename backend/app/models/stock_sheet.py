from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func

from app.db.session import Base


class StockSheet(Base):
    __tablename__ = "stock_sheets"
    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_stock_sheet_company_code"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False)
    code = Column(String, nullable=False)  # "CH-0001" / "R-0001", único por empresa
    stock_type = Column(String, nullable=False)  # FULL_SHEET | REMNANT
    status = Column(String, nullable=False, default="AVAILABLE")  # AVAILABLE | RESERVED | CONSUMED | DISCARDED
    original_width_mm = Column(Float, nullable=True)
    original_height_mm = Column(Float, nullable=True)
    original_area_mm2 = Column(Float, nullable=False)
    remaining_area_mm2 = Column(Float, nullable=False)
    geometry = Column(JSON, nullable=False)  # GeoJSON Polygon, coordenadas en mm
    source_sheet_id = Column(Integer, ForeignKey("stock_sheets.id"), nullable=True)
    source_quotation_id = Column(Integer, ForeignKey("quotations.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
