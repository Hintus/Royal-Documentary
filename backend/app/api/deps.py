from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User, Role
from app.schemas.user import TokenPayload
import logging
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login",
    auto_error=False
)


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """Get current user from token with roles and permissions loaded"""
    if not token:
        return None
    
    payload = decode_token(token)
    if not payload:
        return None
    
    user_id = payload.get("sub")
    if not user_id:
        return None
    
    # Загружаем пользователя с ролями и правами
    result = await db.execute(
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.roles).selectinload(Role.permissions)
        )
    )
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        return None
    
    return user

async def get_current_active_user(
    current_user: Optional[User] = Depends(get_current_user)
) -> User:
    """Get current active user or raise 401"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    return current_user


async def get_current_superuser(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Get current superuser or raise 403"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user


def require_permission(permission_name: str):
    """Dependency factory to check user permissions"""
    async def permission_checker(
        current_user: User = Depends(get_current_active_user)
    ) -> User:
        # Check if user has permission through roles
        for role in current_user.roles:
            for permission in role.permissions:
                if permission.name == permission_name:
                    return current_user
        
        # Check if superuser (has all permissions)
        if current_user.is_superuser:
            return current_user
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing permission: {permission_name}"
        )
    
    return permission_checker