from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.services.auth import decode_access_token

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> int:
    """Valida JWT y retorna user_id del usuario autenticado.

    Revalida contra la DB en cada request (no solo el JWT): esto NO es
    revocación de tokens (el JWT sigue siendo criptográficamente válido
    hasta su `exp`, no hay blacklist), pero sin esto un usuario dado de
    baja globalmente (User.is_active=False) podía seguir operando con
    cualquier access_token emitido antes de la baja hasta que expirara
    por su cuenta.
    """
    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload or not payload.get("user_id"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
        )
    user_id = payload.get("user_id")
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario inválido o inactivo",
        )
    return user_id  # user_id (int)
