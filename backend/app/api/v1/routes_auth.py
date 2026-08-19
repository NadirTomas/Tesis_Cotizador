import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import Token, UserLogin, UserRegister
from app.services.auth import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def register(request: Request, data: UserRegister, db: Session = Depends(get_db)):
    email_lower = data.email.lower()
    if db.query(User).filter(User.email == email_lower).first():
        logger.warning("Register failed: email already exists", extra={"email": email_lower})
        raise HTTPException(status_code=400, detail="Email ya registrado")
    user = User(email=email_lower, hashed_password=hash_password(data.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token({"sub": user.email, "user_id": user.id})
    logger.info("User registered successfully", extra={"user_id": user.id, "email": email_lower})
    return Token(access_token=token)


@router.post("/login", response_model=Token)
@limiter.limit("10/minute")
def login(request: Request, data: UserLogin, db: Session = Depends(get_db)):
    email_lower = data.email.lower()
    user = db.query(User).filter(User.email == email_lower).first()
    if not user or not verify_password(data.password, user.hashed_password):
        logger.warning("Login failed: invalid credentials", extra={"email": email_lower})
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    if not user.is_active:
        logger.warning("Login failed: user inactive", extra={"user_id": user.id, "email": email_lower})
        raise HTTPException(status_code=403, detail="Usuario inactivo")
    token = create_access_token({"sub": user.email, "user_id": user.id})
    logger.info("Login successful", extra={"user_id": user.id, "email": email_lower})
    return Token(access_token=token)
