"""Authentication endpoints for user registration, login, and token management."""
from datetime import datetime, timedelta
from typing import Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update, text
import logging

from app.core.database import get_db
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token
)
from app.schemas.user import UserCreate, UserResponse, LoginRequest
from app.schemas.token import RefreshTokenRequest, TokenPair
from app.models.user import User, Role
from app.models.refresh_token import RefreshToken
from app.api import deps

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_lock_key(user_id: UUID) -> int:
    """
    Generate a unique lock key for a user.
    
    PostgreSQL advisory locks use 64-bit integers, so we hash the user_id
    to fit into this range.
    
    Args:
        user_id: UUID of the user.
        
    Returns:
        int: 64-bit integer lock key.
    """
    return hash(f"user_lock:{user_id}") % 2**63


@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
) -> UserResponse:
    """
    Register a new user.

    Creates a new user account with the provided username and password.
    Assigns the default 'user' role to the new account.

    Args:
        user_data: User registration data containing username and password.
        db: Database session dependency.

    Returns:
        UserResponse: Created user information.

    Raises:
        HTTPException: 400 if username already exists.
    """
    # Check if username already exists
    result = await db.execute(
        select(User).where(User.username == user_data.username)
    )
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )

    # Create new user
    hashed_password = get_password_hash(user_data.password)

    # Get default 'user' role
    result = await db.execute(
        select(Role).where(Role.name == "user")
    )
    user_role = result.scalar_one_or_none()

    db_user = User(
        username=user_data.username,
        hashed_password=hashed_password
    )

    if user_role:
        db_user.roles.append(user_role)

    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)

    logger.info(f"New user registered: {db_user.username}")
    return db_user


@router.post("/login", response_model=TokenPair)
async def login(
    login_data: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> TokenPair:
    """
    Authenticate user and return token pair (access + refresh).

    Uses PostgreSQL advisory locks to prevent race conditions when multiple
    workers try to create refresh tokens for the same user simultaneously.

    Args:
        login_data: Login credentials containing username and password.
        request: FastAPI request object for client info.
        db: Database session dependency.

    Returns:
        TokenPair: Access token and refresh token.

    Raises:
        HTTPException: 401 if credentials are invalid or user is inactive.
    """
    # Find user
    result = await db.execute(
        select(User).where(User.username == login_data.username)
    )
    user = result.scalar_one_or_none()

    if not user:
        logger.warning(f"Login attempt with non-existent username: {login_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify password
    if not verify_password(login_data.password, user.hashed_password):
        logger.warning(f"Failed login attempt for user: {user.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user is active
    if not user.is_active:
        logger.warning(f"Inactive user attempted login: {user.username}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )

    # Use advisory lock to serialize access for this user
    lock_key = _get_lock_key(user.id)
    now = datetime.utcnow()
    
    # Acquire exclusive advisory lock for this user
    # This will block other workers trying to process the same user
    await db.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": lock_key}
    )
    
    logger.info(f"Acquired advisory lock for user {user.id}")
    
    # Revoke all existing active refresh tokens for this user
    await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user.id,
            RefreshToken.revoked == False,
            RefreshToken.expires_at > now
        )
        .values(
            revoked=True,
            revoked_at=now
        )
    )
    
    # Create new refresh token
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})
    
    client_info = {
        "ip": request.client.host if request.client else "unknown",
        "user_agent": request.headers.get("user-agent", "unknown")
    }
    
    db_refresh_token = RefreshToken(
        token=refresh_token,
        user_id=user.id,
        expires_at=now + timedelta(days=7),
        client_info=client_info
    )
    
    db.add(db_refresh_token)
    await db.commit()  # Commit releases the advisory lock
    
    logger.info(f"User logged in successfully: {user.username}")

    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=15 * 60
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh_token(
    refresh_request: RefreshTokenRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> TokenPair:
    """
    Get new access token using refresh token.

    Uses PostgreSQL advisory locks to prevent race conditions when multiple
    workers try to refresh tokens for the same user simultaneously.

    Args:
        refresh_request: Refresh token data.
        request: FastAPI request object for client info.
        db: Database session dependency.

    Returns:
        TokenPair: New access token and new refresh token.

    Raises:
        HTTPException: 401 if refresh token is invalid or expired.
    """
    # Decode refresh token
    payload = decode_token(refresh_request.refresh_token)
    if not payload:
        logger.warning("Invalid refresh token format")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    user_id = payload.get("sub")
    if not user_id:
        logger.warning("Refresh token missing user ID")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    # Convert user_id to UUID
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        logger.warning(f"Invalid user ID format in token: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    # Use advisory lock to serialize access for this user
    lock_key = _get_lock_key(user_uuid)
    now = datetime.utcnow()
    
    # Acquire exclusive advisory lock for this user
    await db.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": lock_key}
    )
    
    logger.info(f"Acquired advisory lock for user {user_uuid} during token refresh")
    
    # Get the refresh token from database with row-level lock
    result = await db.execute(
        select(RefreshToken)
        .where(
            RefreshToken.token == refresh_request.refresh_token,
            RefreshToken.user_id == user_uuid,
            RefreshToken.revoked == False,
            RefreshToken.expires_at > now
        )
        .with_for_update()
    )
    db_refresh_token = result.scalar_one_or_none()
    
    if not db_refresh_token:
        logger.warning(f"Refresh token not found or expired for user {user_uuid}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )
    
    # Get user
    result = await db.execute(
        select(User).where(User.id == user_uuid)
    )
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        logger.warning(f"User {user_uuid} not found or inactive during token refresh")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    # Revoke the used refresh token
    db_refresh_token.revoked = True
    db_refresh_token.revoked_at = now
    
    # Create new token pair
    new_access_token = create_access_token(data={"sub": str(user.id)})
    new_refresh_token = create_refresh_token(data={"sub": str(user.id)})
    
    client_info = {
        "ip": request.client.host if request.client else "unknown",
        "user_agent": request.headers.get("user-agent", "unknown")
    }
    
    new_db_refresh_token = RefreshToken(
        token=new_refresh_token,
        user_id=user.id,
        expires_at=now + timedelta(days=7),
        client_info=client_info
    )
    
    db.add(new_db_refresh_token)
    await db.commit()  # Commit releases the advisory lock
    
    logger.info(f"Token refreshed for user: {user.username}")

    return TokenPair(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=15 * 60
    )


@router.post("/logout")
async def logout(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user)
) -> Dict[str, str]:
    """
    Logout the current user by revoking all their refresh tokens.

    Uses advisory lock to ensure consistency during logout.

    Args:
        request: FastAPI request object.
        db: Database session dependency.
        current_user: Currently authenticated user.

    Returns:
        Dict[str, str]: Success message.
    """
    lock_key = _get_lock_key(current_user.id)
    
    # Acquire advisory lock for this user
    await db.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": lock_key}
    )
    
    # Revoke all active refresh tokens
    await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == current_user.id,
            RefreshToken.revoked == False
        )
        .values(
            revoked=True,
            revoked_at=datetime.utcnow()
        )
    )
    
    await db.commit()
    
    logger.info(f"User logged out: {current_user.username}, IP: {request.client.host if request.client else 'unknown'}")

    return {
        "message": "Logged out successfully",
        "detail": "All refresh tokens have been revoked"
    }


@router.post("/logout/all")
async def logout_all_devices(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user)
) -> Dict[str, str]:
    """
    Logout from all devices by revoking all refresh tokens.

    Uses advisory lock to ensure consistency during logout.

    Args:
        request: FastAPI request object.
        db: Database session dependency.
        current_user: Currently authenticated user.

    Returns:
        Dict[str, str]: Success message.
    """
    lock_key = _get_lock_key(current_user.id)
    
    # Acquire advisory lock for this user
    await db.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": lock_key}
    )
    
    # Delete all refresh tokens for this user
    await db.execute(
        delete(RefreshToken).where(RefreshToken.user_id == current_user.id)
    )
    
    await db.commit()
    
    logger.info(f"User logged out from all devices: {current_user.username}")

    return {
        "message": "Logged out from all devices successfully",
        "detail": "All sessions have been terminated"
    }


@router.post("/login/form", response_model=TokenPair)
async def login_form(
    form_data: OAuth2PasswordRequestForm = Depends(),
    request: Request = None,
    db: AsyncSession = Depends(get_db)
) -> TokenPair:
    """
    Login with OAuth2 form data.

    Provides compatibility with OAuth2 password flow for Swagger UI
    and other OAuth2 clients.

    Args:
        form_data: OAuth2 form data containing username and password.
        request: FastAPI request object.
        db: Database session dependency.

    Returns:
        TokenPair: Access token and refresh token.
    """
    login_data = LoginRequest(
        username=form_data.username,
        password=form_data.password
    )
    return await login(login_data, request, db)


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(deps.get_current_active_user)
) -> UserResponse:
    """
    Get information about the currently authenticated user.

    Args:
        current_user: Currently authenticated user from dependency.

    Returns:
        UserResponse: Current user information.
    """
    return current_user


@router.get("/sessions")
async def get_active_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user)
) -> Dict[str, Any]:
    """
    Get list of active sessions (refresh tokens) for the current user.

    This is a read-only operation that doesn't require advisory locks.

    Args:
        db: Database session dependency.
        current_user: Currently authenticated user.

    Returns:
        Dict with list of active sessions.
    """
    result = await db.execute(
        select(RefreshToken)
        .where(
            RefreshToken.user_id == current_user.id,
            RefreshToken.revoked == False,
            RefreshToken.expires_at > datetime.utcnow()
        )
        .order_by(RefreshToken.created_at.desc())
    )
    active_tokens = result.scalars().all()

    sessions = [
        {
            "id": str(token.id),
            "created_at": token.created_at.isoformat() if token.created_at else None,
            "expires_at": token.expires_at.isoformat() if token.expires_at else None,
            "client_info": token.client_info,
            "last_used": token.last_used_at.isoformat() if token.last_used_at else None
        }
        for token in active_tokens
    ]

    return {
        "active_sessions": sessions,
        "total": len(sessions)
    }