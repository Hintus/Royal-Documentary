from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime


class CompareValue(BaseModel):
    """Value comparison result."""
    old: Optional[Any] = None
    new: Optional[Any] = None


class CompareResult(BaseModel):
    """Comparison result for a single path."""
    path: str
    type: str  # 'added', 'removed', 'changed', 'unchanged'
    value: Optional[CompareValue] = None


class DocumentCompareResponse(BaseModel):
    """Response model for document comparison."""
    doc1_id: str
    doc2_id: str
    doc1_name: str
    doc2_name: str
    doc1_version: int
    doc2_version: int
    doc1_updated_at: Optional[datetime] = None
    doc2_updated_at: Optional[datetime] = None
    changes: List[CompareResult]
    summary: Dict[str, int] = Field(
        default_factory=lambda: {
            "added": 0,
            "removed": 0,
            "changed": 0,
            "unchanged": 0
        }
    )