from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import get_settings


settings = get_settings()

# Railway a veces provee "postgres://" (formato Heroku); SQLAlchemy requiere "postgresql://"
_db_url = settings.DATABASE_URL
if _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql://", 1)

_is_sqlite = _db_url.startswith("sqlite")

if _is_sqlite:
    engine = create_engine(_db_url, connect_args={"check_same_thread": False})
else:
    # Defaults de SQLAlchemy (pool_size=5, max_overflow=10 => 15 conexiones
    # como maximo) se agotaban con una sola pantalla cargando ~17 previews de
    # pieza en paralelo (cada AuthedImage dispara su propio fetch autenticado),
    # tumbando de paso endpoints sin relacion que competian por el mismo pool
    # (incidente en produccion 2026-09-26, QueuePool TimeoutError). pool_pre_ping
    # evita reusar conexiones que Railway haya cortado silenciosamente por su
    # red privada.
    engine = create_engine(
        _db_url,
        pool_size=10,
        max_overflow=20,
        pool_timeout=30,
        pool_pre_ping=True,
    )

if _is_sqlite:
    # SQLite no enforce foreign keys por defecto (a diferencia de Postgres,
    # que siempre lo hace) — hay que activarlo por conexión. Sin esto, un
    # ON DELETE CASCADE (o cualquier violación de FK) queda completamente
    # invisible en local/tests: un bug así ya llegó a producción sin que
    # ningún test lo detectara.
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
