from app.db.session import Base, engine
from app.core.config import get_settings
from app.models.client import Client
from app.models.company import Company
from app.models.company_member import CompanyMember
from app.models.machine_config import MachineConfig
from app.models.material import Material
from app.models.piece import Piece
from app.models.quotation import Quotation
from app.models.quotation_event import QuotationEvent
from app.models.quotation_item import QuotationItem
from app.models.stock_movement import StockMovement
from app.models.stock_reservation import StockReservation
from app.models.stock_sheet import StockSheet
from app.models.user import User


# Paso 3: Inicialización de base de datos
def init_db() -> None:
    """
    Initialize database. In production, Alembic handles migrations.
    In development with SQLite, this creates tables directly.
    """
    settings = get_settings()
    # Only use create_all for SQLite (local development)
    # Production (PostgreSQL on Railway) uses Alembic migrations
    if settings.DATABASE_URL.startswith("sqlite"):
        Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
