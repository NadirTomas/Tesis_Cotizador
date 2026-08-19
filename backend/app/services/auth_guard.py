from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.services.auth import decode_access_token

security = HTTPBearer()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Valida JWT y retorna user_id del usuario autenticado."""
    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload or not payload.get("user_id"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
        )
    return payload.get("user_id")  # user_id (int)
