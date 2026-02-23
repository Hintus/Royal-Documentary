"""Document CRUD operations endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
import logging
from uuid import UUID

from app.core.database import get_db
from app.api import deps
from app.models.user import User
from app.models.document import JsonDocument
from app.schemas.document import (
    DocumentCreate, DocumentUpdate, DocumentResponse, DocumentListResponse
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    document_data: DocumentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user)
) -> DocumentResponse:
    """
    Create a new JSON document.

    Args:
        document_data: Document data for creation.
        db: Database session.
        current_user: Authenticated user creating the document.

    Returns:
        DocumentResponse: Created document data.

    Raises:
        HTTPException: If document creation fails.
    """
    logger.info("Creating document '%s' for user %s",
                document_data.name, current_user.username)

    # Get data using different methods for reliability
    data = document_data.model_dump()
    data_by_alias = document_data.model_dump(by_alias=True)

    db_document = JsonDocument(
        name=data["name"],
        content=data["content"],
        is_public=data["is_public"],
        doc_metadata=data_by_alias.get("doc_metadata", data.get("metadata", {})),
        owner_id=current_user.id,
        version=1
    )

    db.add(db_document)
    await db.commit()
    await db.refresh(db_document)

    logger.info("Document created with ID: %s", db_document.id)
    return db_document


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(deps.get_current_user),
    skip: int = Query(0, ge=0, description="Number of documents to skip"),
    limit: int = Query(20, ge=1, le=100, description="Number of documents to return"),
    search: Optional[str] = Query(None, description="Search in document names"),
    public_only: bool = Query(False, description="Show only public documents"),
    my_docs: bool = Query(False, description="Show only my documents")
) -> DocumentListResponse:
    """
    List documents with pagination and filters.

    Args:
        db: Database session.
        current_user: Currently authenticated user (optional).
        skip: Number of documents to skip for pagination.
        limit: Maximum number of documents to return.
        search: Search term for document names.
        public_only: Filter to show only public documents.
        my_docs: Filter to show only current user's documents.

    Returns:
        DocumentListResponse: Paginated list of documents.
    """
    logger.info("Listing documents - skip: %d, limit: %d", skip, limit)

    # Build query
    query = select(JsonDocument)
    count_query = select(func.count()).select_from(JsonDocument)

    # Apply filters
    if public_only:
        query = query.where(JsonDocument.is_public.is_(True))
        count_query = count_query.where(JsonDocument.is_public.is_(True))
    elif my_docs and current_user:
        query = query.where(JsonDocument.owner_id == current_user.id)
        count_query = count_query.where(JsonDocument.owner_id == current_user.id)
    elif not current_user:
        query = query.where(JsonDocument.is_public.is_(True))
        count_query = count_query.where(JsonDocument.is_public.is_(True))

    # Search in name
    if search:
        search_pattern = f"%{search}%"
        query = query.where(JsonDocument.name.ilike(search_pattern))
        count_query = count_query.where(JsonDocument.name.ilike(search_pattern))

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Add pagination
    query = query.offset(skip).limit(limit).order_by(JsonDocument.created_at.desc())

    # Execute query
    result = await db.execute(query)
    documents = result.scalars().all()

    # Convert SQLAlchemy models to Pydantic models
    document_responses = [DocumentResponse.model_validate(doc) for doc in documents]

    # Calculate total pages
    pages = (total + limit - 1) // limit if total > 0 else 0

    return DocumentListResponse(
        items=document_responses,
        total=total,
        page=(skip // limit) + 1 if limit > 0 else 1,
        size=limit,
        pages=pages
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(deps.get_current_user)
) -> DocumentResponse:
    """
    Get a specific document by ID.

    Args:
        document_id: UUID of the document to retrieve.
        db: Database session.
        current_user: Currently authenticated user (optional).

    Returns:
        DocumentResponse: Document data.

    Raises:
        HTTPException: If document not found or access denied.
    """
    logger.info("Getting document %s", document_id)

    # Validate UUID format
    try:
        UUID(document_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Get document
    result = await db.execute(
        select(JsonDocument).where(JsonDocument.id == document_id)
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Check permissions
    if not document.is_public:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        if document.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )

    # Update access stats only for owner or superuser
    if current_user and (document.owner_id == current_user.id or current_user.is_superuser):
        document.last_accessed_at = func.now()
        document.access_count += 1
        await db.commit()
        await db.refresh(document)

    return document


@router.put("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: str,
    document_data: DocumentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user)
) -> DocumentResponse:
    """
    Update an existing document.

    Args:
        document_id: UUID of the document to update.
        document_data: Updated document data.
        db: Database session.
        current_user: Authenticated user performing the update.

    Returns:
        DocumentResponse: Updated document data.

    Raises:
        HTTPException: If document not found or permission denied.
    """
    logger.info("Updating document %s", document_id)

    # Get document
    result = await db.execute(
        select(JsonDocument).where(JsonDocument.id == document_id)
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Check permissions
    if document.owner_id != current_user.id and not current_user.is_superuser:
        has_permission = False
        for role in current_user.roles:
            for permission in role.permissions:
                if permission.name == "document:update_any":
                    has_permission = True
                    break

        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions to update this document"
            )

    # Update fields
    update_data = document_data.model_dump(exclude_unset=True)

    # Increment version if content changed
    if "content" in update_data and update_data["content"] != document.content:
        document.version += 1

    for field, value in update_data.items():
        setattr(document, field, value)

    document.updated_at = func.now()

    await db.commit()
    await db.refresh(document)

    logger.info("Document %s updated, new version: %d", document_id, document.version)
    return document


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user)
) -> None:
    """
    Delete a document.

    Args:
        document_id: UUID of the document to delete.
        db: Database session.
        current_user: Authenticated user performing the deletion.

    Returns:
        None

    Raises:
        HTTPException: If document not found or permission denied.
    """
    logger.info("Deleting document %s", document_id)

    # Get document
    result = await db.execute(
        select(JsonDocument).where(JsonDocument.id == document_id)
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Check permissions
    if document.owner_id != current_user.id and not current_user.is_superuser:
        has_permission = False
        for role in current_user.roles:
            for permission in role.permissions:
                if permission.name == "document:delete_any":
                    has_permission = True
                    break

        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions to delete this document"
            )

    await db.delete(document)
    await db.commit()

    logger.info("Document %s deleted", document_id)
    return None