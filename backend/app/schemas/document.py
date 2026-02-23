from pydantic import BaseModel, Field, ConfigDict, validator 
from typing import Optional, Any, Dict, List
from uuid import UUID
from datetime import datetime


class DocumentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)
    content: Dict[str, Any] = Field(default_factory=dict)
    is_public: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict, alias="doc_metadata")
    
    model_config = ConfigDict(
        populate_by_name=True,  # разрешает использовать как metadata так и doc_metadata
        json_encoders={
            UUID: str,
            datetime: lambda v: v.isoformat()
        }
    )


class DocumentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=500)
    content: Optional[Dict[str, Any]] = None
    is_public: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = Field(None, alias="doc_metadata")
    
    model_config = ConfigDict(populate_by_name=True)


class DocumentResponse(DocumentBase):
    id: UUID
    version: int
    owner_id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_accessed_at: Optional[datetime] = None
    access_count: int = 0
    
    model_config = ConfigDict(
        from_attributes=True,  # Важно для работы с SQLAlchemy моделями
        populate_by_name=True,
        json_encoders={
            UUID: str,
            datetime: lambda v: v.isoformat()
        }
    )

class DocumentCreate(DocumentBase):
    pass

class DocumentListResponse(BaseModel):
    items: List[DocumentResponse]
    total: int
    page: int
    size: int
    pages: int

class DocumentPathUpdate(BaseModel):
    """Update a specific path in a JSON document."""
    
    value: Any = Field(..., description="New value for the specified path")
    
    @validator('value')
    def validate_value(cls, v):
        # Любое JSON-значение допустимо
        return v


class DocumentPathResponse(BaseModel):
    """Response for path-based operations."""
    
    path: str
    value: Any
    document_id: str