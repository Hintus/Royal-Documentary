from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import logging
from uuid import UUID

from app.core.database import get_db
from app.api import deps
from app.models.user import User
from app.models.document import JsonDocument
from app.schemas.compare import DocumentCompareResponse
from app.utils.json_diff import compare_json_objects, format_comparison_for_response

router = APIRouter(prefix="/documents/compare")
logger = logging.getLogger(__name__)


@router.get("/{doc1_id}/{doc2_id}", response_model=DocumentCompareResponse)
async def compare_documents(
    doc1_id: str,
    doc2_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Compare two JSON documents and return detailed differences.
    
    Returns a structured diff showing added, removed, and changed paths
    with their old and new values.
    """
    logger.info(f"Comparing documents {doc1_id} and {doc2_id}")
    
    # Validate UUIDs
    try:
        UUID(doc1_id)
        UUID(doc2_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Get documents
    if doc1_id == doc2_id:
        # Same document - get it once
        result = await db.execute(
            select(JsonDocument).where(JsonDocument.id == doc1_id)
        )
        doc = result.scalar_one_or_none()
        
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        doc1 = doc
        doc2 = doc
    else:
        # Different documents - get both
        result = await db.execute(
            select(JsonDocument).where(JsonDocument.id.in_([doc1_id, doc2_id]))
        )
        documents = result.scalars().all()
        
        if len(documents) != 2:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or both documents not found"
            )
        
        # Map documents by ID
        doc_map = {str(doc.id): doc for doc in documents}
        doc1 = doc_map[doc1_id]
        doc2 = doc_map[doc2_id]
    
    # Check permissions for both documents
    for doc in [doc1, doc2]:
        if not doc.is_public:
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required to access private documents"
                )
            if doc.owner_id != current_user.id and not current_user.is_superuser:
                # Check if user has permission to read any document
                has_permission = False
                for role in current_user.roles:
                    for permission in role.permissions:
                        if permission.name == "document:read_any":
                            has_permission = True
                            break
                
                if not has_permission:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Not enough permissions to access private documents"
                    )
    
    try:
        # Явно загружаем все нужные поля
        doc1_id_str = str(doc1.id)
        doc2_id_str = str(doc2.id) if doc1_id != doc2_id else doc1_id_str
        doc1_name = doc1.name
        doc2_name = doc2.name if doc1_id != doc2_id else doc1_name
        doc1_version = doc1.version
        doc2_version = doc2.version if doc1_id != doc2_id else doc1_version
        doc1_updated_at = doc1.updated_at
        doc2_updated_at = doc2.updated_at if doc1_id != doc2_id else doc1_updated_at
        doc1_content = doc1.content
        doc2_content = doc2.content if doc1_id != doc2_id else doc1_content
        
        # Compare documents
        diff_result = compare_json_objects(doc1_content, doc2_content)
        
        # Format changes for response
        changes = format_comparison_for_response(doc1, doc2, diff_result)
        
        # Update access stats
        doc1.last_accessed_at = func.now()
        doc1.access_count += 1
        if doc1_id != doc2_id:
            doc2.last_accessed_at = func.now()
            doc2.access_count += 1
        await db.commit()
        
        # Prepare summary
        summary = {
            "added": len(diff_result["added"]),
            "removed": len(diff_result["removed"]),
            "changed": len(diff_result["changed"]),
            "unchanged": len(diff_result["unchanged"])
        }
        
        return DocumentCompareResponse(
            doc1_id=doc1_id_str,
            doc2_id=doc2_id_str,
            doc1_name=doc1_name,
            doc2_name=doc2_name,
            doc1_version=doc1_version,
            doc2_version=doc2_version,
            doc1_updated_at=doc1_updated_at,
            doc2_updated_at=doc2_updated_at,
            changes=changes,
            summary=summary
        )
        
    except Exception as e:
        logger.error(f"Error comparing documents: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error comparing documents"
        )


@router.post("/", response_model=DocumentCompareResponse)
async def compare_documents_post(
    doc1_id: str = Query(..., description="First document ID"),
    doc2_id: str = Query(..., description="Second document ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Alternative POST endpoint for document comparison.
    Useful when document IDs are long.
    """
    return await compare_documents(doc1_id, doc2_id, db, current_user)