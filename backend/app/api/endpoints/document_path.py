from fastapi import APIRouter, Depends, HTTPException, status, Body, Path as PathParam
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, text
import logging
from typing import Any
from uuid import UUID

from app.core.database import get_db
from app.api import deps
from app.models.user import User
from app.models.document import JsonDocument
from app.api.endpoints.auth import _get_lock_key
from app.schemas.document import DocumentPathUpdate, DocumentPathResponse
from app.utils.json_path import (
    parse_json_path, get_value_at_path, 
    set_value_at_path, delete_value_at_path
)


router = APIRouter(prefix="/documents/{document_id}/path")
logger = logging.getLogger(__name__)


@router.get("/{path:path}", response_model=DocumentPathResponse)
async def get_document_path(
    document_id: str,
    path: str = PathParam(..., description="JSON path (e.g., 'customer.name' or 'addresses[0].city')"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Get a specific part of a JSON document by path."""
    logger.info(f"Getting path '{path}' from document {document_id}")
    
    # Validate UUID
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
        if document.owner_id != current_user.id and not current_user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
    
    try:
        path_parts = parse_json_path(path)
        
        # ============ КЛЮЧЕВОЕ ИЗМЕНЕНИЕ ============
        # Явно обновляем объект из БД, отбрасывая все локальные изменения
        logger.info("Refreshing document from database...")
        await db.refresh(document)
        # ============================================
        
        # Теперь читаем свежее значение из документа
        value = get_value_at_path(document.content, path_parts)
        logger.info(f"Value read after refresh: {value}")
        
        # Update access stats
        document.last_accessed_at = func.now()
        document.access_count += 1
        
        # Commit changes
        await db.commit()
        logger.info("Access stats updated and committed")
        
        return DocumentPathResponse(
            path=path,
            value=value,
            document_id=document_id
        )
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error accessing path '{path}': {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid path: {str(e)}"
        )

@router.patch("/{path:path}", response_model=DocumentPathResponse)
async def update_document_path(
    document_id: str,
    path: str = PathParam(..., description="JSON path to update"),
    update_data: DocumentPathUpdate = Body(..., description="Update data"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    logger.info("=" * 60)
    logger.info("PATCH request received")
    logger.info(f"Document ID: {document_id}")
    logger.info(f"Path: {path}")
    logger.info(f"Value to set: {update_data.value}")
    
    # Validate UUID
    try:
        UUID(document_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    try:
        # 1. Acquire advisory lock
        lock_key = _get_lock_key(document_id)
        await db.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": lock_key}
        )
        logger.info("Advisory lock acquired")
        
        # 2. Read document
        result = await db.execute(
            select(JsonDocument).where(JsonDocument.id == document_id)
        )
        document = result.scalar_one_or_none()
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # 3. Check permissions
        if document.owner_id != current_user.id and not current_user.is_superuser:
            raise HTTPException(status_code=403, detail="Permission denied")
        
        # 4. Parse path
        path_parts = parse_json_path(path)
        logger.info(f"Path parts: {path_parts}")
        
        # 5. Попытка прочитать текущее значение (теперь ловим KeyError)
        try:
            current_value = get_value_at_path(document.content, path_parts)
            logger.info(f"Current value at path: {current_value}")
        except KeyError as e:
            logger.info(f"Path does not exist yet - will be created: {e}")
            # Игнорируем - путь будет создан
        
        # 6. Update value (modifies in place!)
        set_value_at_path(document.content, path_parts, update_data.value)
        
        # 7. Явно помечаем поле как изменённое
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(document, "content")
        logger.info("Field 'content' flagged as modified")
        
        # 8. Update metadata
        document.version += 1
        document.updated_at = func.now()
        
        # 9. Commit
        db.add(document)
        await db.commit()
        logger.info("Commit successful")
        
        # 10. Verify (теперь должно работать, т.к. путь уже создан)
        verify_value = get_value_at_path(document.content, path_parts)
        logger.info(f"Verified value after commit: {verify_value}")
        
        return DocumentPathResponse(
            path=path,
            value=update_data.value,
            document_id=document_id
        )
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.delete("/{path:path}", response_model=DocumentPathResponse)
async def delete_document_path(
    document_id: str,
    path: str = PathParam(..., description="JSON path to delete"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    """Delete a specific part of a JSON document by path."""
    logger.info(f"Deleting path '{path}' from document {document_id}")
    
    # Validate UUID
    try:
        UUID(document_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Get document with advisory lock (а не row lock!)
    lock_key = _get_lock_key(document_id)
    await db.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": lock_key}
    )
    
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
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to update this document"
        )
    
    try:
        path_parts = parse_json_path(path)
        
        # Get value before deletion (for response)
        try:
            old_value = get_value_at_path(document.content, path_parts)
        except KeyError:
            # Путь не существует - возвращаем 200 с None (идемпотентность)
            logger.info(f"Path '{path}' does not exist, returning None")
            return DocumentPathResponse(
                path=path,
                value=None,
                document_id=document_id
            )
        
        # ============ КЛЮЧЕВЫЕ ИЗМЕНЕНИЯ ============
        # Удаляем значение на месте, без создания копии
        delete_value_at_path(document.content, path_parts)
        
        # Явно помечаем поле как изменённое
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(document, "content")
        logger.info("Field 'content' flagged as modified")
        
        # Обновляем метаданные
        document.version += 1
        document.updated_at = func.now()
        
        # Сохраняем
        db.add(document)
        await db.commit()
        
        logger.info(f"Deleted path '{path}' from document {document_id}, new version: {document.version}")
        
        return DocumentPathResponse(
            path=path,
            value=old_value,
            document_id=document_id
        )
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting path '{path}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid path: {str(e)}"
        )