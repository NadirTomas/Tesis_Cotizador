import json
import logging
import sys
from datetime import datetime
from typing import Any


class JSONFormatter(logging.Formatter):
    """Formatter que genera logs en formato JSON para procesamiento en Railway."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Agregar contexto adicional si existe
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        for field in ("user_id", "request_id", "source", "path", "method", "url", "stack"):
            if hasattr(record, field):
                log_obj[field] = getattr(record, field)

        return json.dumps(log_obj, ensure_ascii=False)


def configure_logging(level: int = logging.INFO) -> None:
    """Configura logging estructurado en JSON para toda la aplicación."""
    # Remover handlers existentes para evitar duplicados
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Handler para stdout (Railway lo captura automáticamente)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    handler.setLevel(level)

    root_logger.addHandler(handler)
    root_logger.setLevel(level)

    # Silenciar logs verbosos de librerías externas
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Obtener logger nombrado."""
    return logging.getLogger(name)
