from fastapi import APIRouter
from app.api.endpoints import auth, documents, document_path, compare, updates

router = APIRouter()

router.include_router(auth.router, prefix="/auth", tags=["authentication"])
router.include_router(documents.router, prefix="/documents", tags=["documents"])
router.include_router(document_path.router, tags=["documents"])
router.include_router(compare.router, tags=["documents"])