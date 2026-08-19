import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1.routes_auth import router as auth_router
from app.api.v1.routes_clients import router as clients_router
from app.api.v1.routes_company import router as company_router
from app.api.v1.routes_health import router as health_router
from app.api.v1.routes_machine_configs import router as machine_configs_router
from app.api.v1.routes_materials import router as materials_router
from app.api.v1.routes_nesting import router as nesting_router
from app.api.v1.routes_pieces import router as pieces_router
from app.api.v1.routes_quotation_items import router as quotation_items_router
from app.api.v1.routes_quotations import router as quotations_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.init_db import init_db


settings = get_settings()
configure_logging(logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up application", extra={"app": settings.APP_NAME})
    init_db()
    yield
    logger.info("Shutting down application")


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

# Rate limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

# CORS: localmente acepta localhost, en producción acepta FRONTEND_URL
origins = ["http://localhost:5173", "http://localhost:5174"]
if settings.FRONTEND_URL:
    origins.append(settings.FRONTEND_URL)

# Confiar en headers X-Forwarded-* de Railway
class TrustProxyHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Railway inyecta X-Forwarded-Proto: https pero uvicorn ve http
        # Esto le dice a Starlette que confíe en esos headers
        request.scope["scheme"] = request.headers.get("x-forwarded-proto", "http")
        return await call_next(request)


app.add_middleware(TrustProxyHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(company_router)
app.include_router(materials_router)
app.include_router(clients_router)
app.include_router(machine_configs_router)
app.include_router(pieces_router)
app.include_router(quotations_router)
app.include_router(quotation_items_router)
app.include_router(nesting_router)


@app.get("/", response_model=dict)
def root():
    return {"app": settings.APP_NAME}
