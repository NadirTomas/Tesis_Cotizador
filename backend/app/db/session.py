from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import get_settings


settings = get_settings()

# Railway a veces provee "postgres://" (formato Heroku); SQLAlchemy requiere "postgresql://"
_db_url = settings.DATABASE_URL
if _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    _db_url,
    connect_args={"check_same_thread": False}
    if _db_url.startswith("sqlite")
    else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
