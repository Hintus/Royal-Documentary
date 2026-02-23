import pytest
import requests
from typing import Dict, Any
import uuid
import sys
import os

# Добавляем корневую папку проекта в путь
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = "http://localhost:8000/api"


@pytest.fixture(scope="session")
def base_url() -> str:
    """Base URL for API"""
    return BASE_URL


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def cleanup():
    """Clean up database before each test"""
    # Это будет вызвано перед каждым тестом
    yield
    # После теста можно выполнить cleanup если нужно
    # Но лучше использовать уникальные имена пользователей в тестах

@pytest.fixture(autouse=True)
async def clean_refresh_tokens():
    """Clean refresh tokens before each test to avoid duplicates"""
    import asyncpg
    from app.core.config import settings
    
    conn = await asyncpg.connect(settings.DATABASE_URL.replace('+asyncpg', ''))
    await conn.execute("DELETE FROM refresh_tokens")
    await conn.close()
    yield

@pytest.fixture
def test_user_data() -> Dict[str, str]:
    """Test user data with unique username"""
    unique_id = str(uuid.uuid4())[:8]
    return {
        "username": f"testuser_{unique_id}",
        "password": "password123"
    }


@pytest.fixture
def registered_user(base_url, test_user_data) -> Dict[str, Any]:
    """Register and return user data"""
    # Register new user (always unique)
    response = requests.post(
        f"{base_url}/auth/register",
        json=test_user_data
    )
    
    # Should always succeed with unique username
    assert response.status_code == 200, f"Registration failed: {response.text}"
    
    # Login to get token
    login_response = requests.post(
        f"{base_url}/auth/login",
        json=test_user_data
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get user info
    me_response = requests.get(
        f"{base_url}/auth/me",
        headers=headers
    )
    assert me_response.status_code == 200
    user_info = me_response.json()
    
    return {
        "user": user_info,
        "token": token,
        "headers": headers,
        "user_data": test_user_data
    }


@pytest.fixture
def another_user(base_url) -> Dict[str, Any]:
    """Create another unique user for testing permissions."""
    import uuid
    user_data = {
        "username": f"otheruser_{uuid.uuid4().hex[:8]}",
        "password": "password123"
    }
    
    response = requests.post(f"{base_url}/auth/register", json=user_data)
    assert response.status_code == 200
    
    login_response = requests.post(f"{base_url}/auth/login", json=user_data)
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    
    headers = {"Authorization": f"Bearer {token}"}
    
    return {
        "user_data": user_data,
        "token": token,
        "headers": headers
    }

@pytest.fixture
async def test_documents(db_session, registered_user):
    """Создаёт несколько тестовых документов."""
    from app.models.document import JsonDocument
    from uuid import uuid4
    
    documents = []
    for i in range(5):
        doc = JsonDocument(
            id=uuid4(),
            name=f"Test Document {i}",
            content={"index": i, "data": f"content_{i}"},
            owner_id=registered_user["user"]["id"],
            version=1
        )
        db_session.add(doc)
        documents.append(doc)
    
    await db_session.commit()
    
    # Возвращаем список документов
    return documents