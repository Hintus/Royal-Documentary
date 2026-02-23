"""Token schemas for authentication."""
from pydantic import BaseModel, Field
from typing import Optional


class TokenPair(BaseModel):
    """Token pair response model."""

    access_token: str = Field(..., description="JWT access token (short-lived)")
    refresh_token: str = Field(..., description="JWT refresh token (long-lived)")
    token_type: str = Field("bearer", description="Token type")
    expires_in: int = Field(900, description="Access token expiration in seconds")


class RefreshTokenRequest(BaseModel):
    """Refresh token request model."""

    refresh_token: str = Field(..., description="Refresh token to exchange for new access token")


class TokenData(BaseModel):
    """Token payload data."""

    user_id: str
    exp: Optional[int] = None
    type: Optional[str] = None

