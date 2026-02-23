from sqlalchemy import Column, String, Boolean, DateTime, Table, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from app.core.database import Base

# Association tables for many-to-many relationships
user_roles = Table(
    'user_roles',
    Base.metadata,
    Column('user_id', UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    Column('role_id', UUID(as_uuid=True), ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True)
)

role_permissions = Table(
    'role_permissions',
    Base.metadata,
    Column('role_id', UUID(as_uuid=True), ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True),
    Column('permission_id', UUID(as_uuid=True), ForeignKey('permissions.id', ondelete='CASCADE'), primary_key=True)
)


class User(Base):
    __tablename__ = 'users'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    roles = relationship('Role', secondary=user_roles, back_populates='users')
    documents = relationship('JsonDocument', back_populates='owner', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f"<User {self.username}>"


class Role(Base):
    __tablename__ = 'roles'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    users = relationship('User', secondary=user_roles, back_populates='roles')
    permissions = relationship('Permission', secondary=role_permissions, back_populates='roles')
    
    def __repr__(self):
        return f"<Role {self.name}>"


class Permission(Base):
    __tablename__ = 'permissions'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False, index=True)
    resource = Column(String(100), nullable=False)
    action = Column(String(50), nullable=False)
    description = Column(String(255))
    
    # Relationships
    roles = relationship('Role', secondary=role_permissions, back_populates='permissions')
    
    def __repr__(self):
        return f"<Permission {self.name}>"