from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from app.core.database import Base


class JsonDocument(Base):
    __tablename__ = 'json_documents'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(500), nullable=False, index=True)
    content = Column(JSONB, nullable=False, default={})
    version = Column(Integer, default=1)
    owner_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    is_public = Column(Boolean, default=False)
    doc_metadata = Column(JSONB, default={})  # Additional metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_accessed_at = Column(DateTime(timezone=True))
    access_count = Column(Integer, default=0)
    
    # Relationships
    owner = relationship('User', back_populates='documents')
    history = relationship('DocumentHistory', back_populates='document', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f"<JsonDocument {self.name}>"


class DocumentHistory(Base):
    __tablename__ = 'document_history'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey('json_documents.id', ondelete='CASCADE'), nullable=False, index=True)
    content = Column(JSONB, nullable=False)
    version = Column(Integer, nullable=False)
    changed_by_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'))
    change_type = Column(String(50))  # 'CREATE', 'UPDATE', 'DELETE', 'EXTERNAL_UPDATE'
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    document = relationship('JsonDocument', back_populates='history')
    changed_by = relationship('User')
    
    def __repr__(self):
        return f"<DocumentHistory doc={self.document_id} version={self.version}>"