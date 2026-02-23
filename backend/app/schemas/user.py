from pydantic import BaseModel, Field, validator
from typing import Optional
import re
from uuid import UUID


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)


class UserCreate(UserBase):
    password: str = Field(..., min_length=6)
    
    @validator('username')
    def username_alphanumeric(cls, v):
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError('Username must be alphanumeric')
        return v


class UserInDB(UserBase):
    id: str  # <-- ДОЛЖНО БЫТЬ STR, НЕ UUID
    is_active: bool = True
    is_superuser: bool = False
    
    @validator('id', pre=True)
    def convert_uuid_to_str(cls, v):
        """Convert UUID to string for serialization"""
        if isinstance(v, UUID):
            return str(v)
        return v
    
    class Config:
        from_attributes = True


class UserResponse(UserInDB):
    pass


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: Optional[str] = None
    exp: Optional[int] = None


class LoginRequest(BaseModel):
    username: str
    password: str