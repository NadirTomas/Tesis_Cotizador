from sqlalchemy import Boolean, Column, DateTime, Integer, LargeBinary, String, func
from sqlalchemy.orm import relationship

from app.db.session import Base


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String, nullable=False)
    legal_name = Column(String, nullable=True)
    cuit = Column(String, nullable=True)
    address = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    logo_data = Column(LargeBinary, nullable=True)
    logo_filename = Column(String, nullable=True)  # Para guardar extensión
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    members = relationship("CompanyMember", back_populates="company")
