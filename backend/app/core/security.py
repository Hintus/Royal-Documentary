from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Константы для токенов
ACCESS_TOKEN_EXPIRE_MINUTES = 15  # 15 минут
REFRESH_TOKEN_EXPIRE_DAYS = 7      # 7 дней


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a short-lived JWT access token.

    Args:
        data: Data to encode in token.
        expires_delta: Optional custom expiration time.

    Returns:
        JWT token string.
    """
    to_encode = data.copy()
    to_encode.update({"type": "access"})

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def create_refresh_token(data: Dict[str, Any]) -> str:
    """
    Create a long-lived JWT refresh token.

    Args:
        data: Data to encode in token.

    Returns:
        JWT token string.
    """
    to_encode = data.copy()
    to_encode.update({
        "type": "refresh",
        "exp": datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    })

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and validate JWT token.

    Args:
        token: JWT token string.

    Returns:
        Decoded payload or None if invalid.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError:
        return None