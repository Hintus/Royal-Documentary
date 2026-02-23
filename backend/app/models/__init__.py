from app.models.user import User, Role, Permission
from app.models.document import JsonDocument, DocumentHistory
from app.models.refresh_token import RefreshToken  # ДОЛЖНО БЫТЬ

__all__ = [
    'User',
    'Role',
    'Permission',
    'JsonDocument',
    'DocumentHistory',
    'RefreshToken',  # И ЗДЕСЬ
]