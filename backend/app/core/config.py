from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "CotizaLaser"
    ENVIRONMENT: str = "local"
    # Railway inyecta DATABASE_URL directamente (postgres://...)
    # Localmente cae a SQLite
    DATABASE_URL: str = "sqlite:///./cotizalaser.db"
    DXF_STORAGE_DIR: str = "data/dxf"
    PDF_STORAGE_DIR: str = "data/pdfs"
    # URL del frontend en producción (para CORS)
    FRONTEND_URL: str = ""
    # JWT — CRÍTICO: en producción DEBE venir de variable de entorno
    # Si no está seteada, lanza error en startup (no defaults inseguros)
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 días
    # File upload limits (in bytes)
    MAX_DXF_SIZE: int = 10 * 1024 * 1024  # 10MB
    MAX_LOGO_SIZE: int = 5 * 1024 * 1024  # 5MB
    # Cost calculation
    LABOR_COST_PERCENT: float = 0.30  # 30% del costo de máquina

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        # Sin prefijo para que Railway pueda inyectar DATABASE_URL directamente
        env_prefix = ""
        # También acepta COTIZALASER_ como prefijo para variables propias
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
