from sqlalchemy import Column, DateTime, Integer, LargeBinary, String, func

from app.db.session import Base


# Paso 2: Modelos base de dominio
class CompanyConfig(Base):
    __tablename__ = "company_config"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String, nullable=False)
    legal_name = Column(String, nullable=True)
    cuit = Column(String, nullable=True)
    address = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    logo_data = Column(LargeBinary, nullable=True)
    logo_filename = Column(String, nullable=True)  # Para guardar extensión
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
