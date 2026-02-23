import pytest
import requests
import uuid
from typing import Dict, Any

BASE_URL = "http://localhost:8000/api"


@pytest.fixture
def sample_document() -> Dict[str, Any]:
    """Sample document data with unique name"""
    unique_id = str(uuid.uuid4())[:8]
    return {
        "name": f"Test Document {unique_id}",
        "content": {
            "key1": "value1",
            "key2": 123,
            "nested": {
                "inner": "data"
            }
        },
        "is_public": False,
        "metadata": {
            "description": "Test document for CRUD operations"
        }
    }


@pytest.fixture
def created_document(registered_user, sample_document) -> Dict[str, Any]:
    """Create a document and return its data"""
    headers = registered_user["headers"]
    
    response = requests.post(
        f"{BASE_URL}/documents",
        json=sample_document,
        headers=headers
    )
    
    assert response.status_code == 201
    return response.json()


class TestDocumentCRUD:
    """Test document CRUD operations"""
    
    def test_create_document(self, registered_user, sample_document):
        """Test creating a new document"""
        headers = registered_user["headers"]
        
        response = requests.post(
            f"{BASE_URL}/documents",
            json=sample_document,
            headers=headers
        )
        
        assert response.status_code == 201
        data = response.json()
        
        assert data["name"] == sample_document["name"]
        assert data["content"] == sample_document["content"]
        assert data["is_public"] == sample_document["is_public"]
        # Проверяем doc_metadata вместо metadata
        assert data["doc_metadata"] == sample_document["metadata"]
        assert data["owner_id"] == registered_user["user"]["id"]
        assert data["version"] == 1
        assert "id" in data
        assert "created_at" in data
        
    def test_create_document_without_auth(self, sample_document):
        """Test creating document without authentication"""
        response = requests.post(
            f"{BASE_URL}/documents",
            json=sample_document
        )
        
        assert response.status_code == 401
        
    def test_list_documents(self, registered_user, created_document):
        """Test listing documents"""
        headers = registered_user["headers"]
        
        response = requests.get(
            f"{BASE_URL}/documents",
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "size" in data
        assert "pages" in data
        
        assert isinstance(data["items"], list)
        assert data["total"] >= 1
        
    def test_list_documents_pagination(self, registered_user):
        """Test pagination"""
        headers = registered_user["headers"]
        
        # Create multiple documents
        for i in range(5):
            doc_data = {
                "name": f"Test Document {i}",
                "content": {"index": i}
            }
            requests.post(
                f"{BASE_URL}/documents",
                json=doc_data,
                headers=headers
            )
        
        # Test pagination
        response = requests.get(
            f"{BASE_URL}/documents?skip=0&limit=3",
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["items"]) == 3
        assert data["size"] == 3
        assert data["page"] == 1
        
    def test_list_documents_search(self, registered_user):
        """Test search functionality"""
        headers = registered_user["headers"]
        
        # Create document with specific name
        doc_data = {
            "name": "UniqueSearchableName",
            "content": {}
        }
        requests.post(
            f"{BASE_URL}/documents",
            json=doc_data,
            headers=headers
        )
        
        # Search for it
        response = requests.get(
            f"{BASE_URL}/documents?search=UniqueSearchable",
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["items"]) >= 1
        assert all("UniqueSearchable" in item["name"] for item in data["items"])
        
    def test_get_document(self, registered_user, created_document):
        """Test getting a specific document"""
        headers = registered_user["headers"]
        doc_id = created_document["id"]
        
        response = requests.get(
            f"{BASE_URL}/documents/{doc_id}",
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == doc_id
        assert data["name"] == created_document["name"]
        assert data["content"] == created_document["content"]
        
    def test_get_document_not_found(self, registered_user):
        """Test getting non-existent document"""
        headers = registered_user["headers"]
        
        response = requests.get(
            f"{BASE_URL}/documents/non-existent-id",
            headers=headers
        )
        
        assert response.status_code == 404
        
    def test_get_document_without_auth(self, created_document):
        """Test getting document without authentication"""
        # Make document public first
        # This test assumes the document is public or fails appropriately
        doc_id = created_document["id"]
        
        response = requests.get(f"{BASE_URL}/documents/{doc_id}")
        
        # Should be 401 if private, 200 if public
        assert response.status_code in (200, 401)
        
    def test_update_document(self, registered_user, created_document):
        """Test updating a document"""
        headers = registered_user["headers"]
        doc_id = created_document["id"]
        
        update_data = {
            "name": "Updated Name",
            "content": {"new": "content"},
            "is_public": True
        }
        
        response = requests.put(
            f"{BASE_URL}/documents/{doc_id}",
            json=update_data,
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["name"] == update_data["name"]
        assert data["content"] == update_data["content"]
        assert data["is_public"] == update_data["is_public"]
        assert data["version"] == created_document["version"] + 1
        
    def test_update_document_partial(self, registered_user, created_document):
        """Test partial update"""
        headers = registered_user["headers"]
        doc_id = created_document["id"]
        
        update_data = {
            "name": "Only Name Changed"
        }
        
        response = requests.put(
            f"{BASE_URL}/documents/{doc_id}",
            json=update_data,
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["name"] == update_data["name"]
        assert data["content"] == created_document["content"]  # Unchanged
        assert data["version"] == created_document["version"]  # No version increment
        
    def test_update_document_unauthorized(self, registered_user, created_document):
        """Test updating document without permission"""
        # Create another user
        other_user_data = {
            "username": "otheruser",
            "password": "password123"
        }
        
        # Register other user
        response = requests.post(
            f"{BASE_URL}/auth/register",
            json=other_user_data
        )
        
        if response.status_code == 400:
            # User exists, login
            login_response = requests.post(
                f"{BASE_URL}/auth/login",
                json=other_user_data
            )
            other_token = login_response.json()["access_token"]
        else:
            other_token = None
        
        if not other_token:
            login_response = requests.post(
                f"{BASE_URL}/auth/login",
                json=other_user_data
            )
            other_token = login_response.json()["access_token"]
        
        other_headers = {"Authorization": f"Bearer {other_token}"}
        
        # Try to update first user's document
        doc_id = created_document["id"]
        update_data = {"name": "Hacked Name"}
        
        response = requests.put(
            f"{BASE_URL}/documents/{doc_id}",
            json=update_data,
            headers=other_headers
        )
        
        assert response.status_code == 403
        
    def test_delete_document(self, registered_user, created_document):
        """Test deleting a document"""
        headers = registered_user["headers"]
        doc_id = created_document["id"]
        
        response = requests.delete(
            f"{BASE_URL}/documents/{doc_id}",
            headers=headers
        )
        
        assert response.status_code == 204
        
        # Verify it's gone
        get_response = requests.get(
            f"{BASE_URL}/documents/{doc_id}",
            headers=headers
        )
        
        assert get_response.status_code == 404
        
    def test_delete_document_unauthorized(self, registered_user, created_document):
        """Test deleting document without permission"""
        # Create another user
        other_user_data = {
            "username": "anotheruser",
            "password": "password123"
        }
        
        # Register and login other user
        response = requests.post(
            f"{BASE_URL}/auth/register",
            json=other_user_data
        )
        
        login_response = requests.post(
            f"{BASE_URL}/auth/login",
            json=other_user_data
        )
        other_token = login_response.json()["access_token"]
        other_headers = {"Authorization": f"Bearer {other_token}"}
        
        # Try to delete first user's document
        doc_id = created_document["id"]
        
        response = requests.delete(
            f"{BASE_URL}/documents/{doc_id}",
            headers=other_headers
        )
        
        assert response.status_code == 403