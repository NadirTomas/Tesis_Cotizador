import pytest

from app.api.v1.routes_auth import limiter as auth_limiter
from app.api.v1.routes_companies import limiter as companies_limiter
from app.api.v1.routes_pieces import limiter as pieces_limiter
from app.main import limiter as main_limiter

_LIMITERS = (main_limiter, auth_limiter, pieces_limiter, companies_limiter)


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """Cada router instancia su propio Limiter; los tests hacen más
    logins/registros por minuto que un uso real, así que se resetean todos
    antes de cada test."""
    for limiter in _LIMITERS:
        limiter.reset()
