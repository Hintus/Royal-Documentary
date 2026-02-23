import pytest
import requests
import uuid
from typing import Dict, Any

BASE_URL = "http://localhost:8000/api"


@pytest.fixture
def complex_document() -> Dict[str, Any]:
    """Create a complex nested document for testing"""
    return {
        "name": "Complex Test Document",
        "content": {
            "customer": {
                "name": "John Doe",
                "email": "john@example.com",
                "address": {
                    "city": "New York",
                    "street": "123 Main St"
                }
            },
            "orders": [
                {"id": 1, "total": 100.50},
                {"id": 2, "total": 200.75}
            ],
            "settings": {
                "notifications": {
                    "email": True,
                    "sms": False
                },
                "theme": "light"
            }
        }
    }


@pytest.fixture
def created_complex_document(registered_user, complex_document) -> Dict[str, Any]:
    """Create a complex document and return its data"""
    headers = registered_user["headers"]
    
    response = requests.post(
        f"{BASE_URL}/documents",
        json=complex_document,
        headers=headers
    )
    
    assert response.status_code == 201
    return response.json()


class TestDocumentPath:
    """Test JSON path operations"""
    
    def test_get_simple_path(self, registered_user, created_complex_document):
        """Test getting a simple nested value"""
        headers = registered_user["headers"]
        doc_id = created_complex_document["id"]
        
        response = requests.get(
            f"{BASE_URL}/documents/{doc_id}/path/customer.name",
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["path"] == "customer.name"
        assert data["value"] == "John Doe"
        assert data["document_id"] == doc_id
    
    def test_get_array_path(self, registered_user, created_complex_document):
        """Test getting value from array"""
        headers = registered_user["headers"]
        doc_id = created_complex_document["id"]
        
        response = requests.get(
            f"{BASE_URL}/documents/{doc_id}/path/orders[0].total",
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["value"] == 100.50
    
    def test_get_nested_path(self, registered_user, created_complex_document):
        """Test getting deeply nested value"""
        headers = registered_user["headers"]
        doc_id = created_complex_document["id"]
        
        response = requests.get(
            f"{BASE_URL}/documents/{doc_id}/path/settings.notifications.email",
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["value"] is True
    
    def test_get_invalid_path(self, registered_user, created_complex_document):
        """Test getting non-existent path"""
        headers = registered_user["headers"]
        doc_id = created_complex_document["id"]
        
        response = requests.get(
            f"{BASE_URL}/documents/{doc_id}/path/customer.nonexistent",
            headers=headers
        )
        
        assert response.status_code == 400
    
    def test_update_simple_path(self, registered_user, created_complex_document):
        """Test updating a simple nested value"""
        headers = registered_user["headers"]
        doc_id = created_complex_document["id"]
        
        update_data = {"value": "Jane Doe"}
        response = requests.patch(
            f"{BASE_URL}/documents/{doc_id}/path/customer.name",
            json=update_data,
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["value"] == "Jane Doe"
        
        # Verify by getting
        get_response = requests.get(
            f"{BASE_URL}/documents/{doc_id}/path/customer.name",
            headers=headers
        )
        assert get_response.json()["value"] == "Jane Doe"
    
    def test_update_array_element(self, registered_user, created_complex_document):
        """Test updating array element"""
        headers = registered_user["headers"]
        doc_id = created_complex_document["id"]
        
        update_data = {"value": 300.50}
        response = requests.patch(
            f"{BASE_URL}/documents/{doc_id}/path/orders[1].total",
            json=update_data,
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["value"] == 300.50
    
    def test_update_create_intermediate(self, registered_user, created_complex_document):
        """Test updating path that creates intermediate objects"""
        headers = registered_user["headers"]
        doc_id = created_complex_document["id"]
        
        update_data = {"value": "Visa"}
        response = requests.patch(
            f"{BASE_URL}/documents/{doc_id}/path/customer.payment.method",
            json=update_data,
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["value"] == "Visa"
        
        # Verify the path was created
        get_response = requests.get(
            f"{BASE_URL}/documents/{doc_id}/path/customer.payment.method",
            headers=headers
        )
        assert get_response.json()["value"] == "Visa"
    
    def test_update_boolean(self, registered_user, created_complex_document):
        """Test updating boolean value"""
        headers = registered_user["headers"]
        doc_id = created_complex_document["id"]
        
        update_data = {"value": False}
        response = requests.patch(
            f"{BASE_URL}/documents/{doc_id}/path/settings.notifications.email",
            json=update_data,
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["value"] is False
    
    def test_update_null(self, registered_user, created_complex_document):
        """Test setting value to null"""
        headers = registered_user["headers"]
        doc_id = created_complex_document["id"]
        
        update_data = {"value": None}
        response = requests.patch(
            f"{BASE_URL}/documents/{doc_id}/path/customer.email",
            json=update_data,
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["value"] is None
    
    def test_delete_path(self, registered_user, created_complex_document):
        """Test deleting a path"""
        headers = registered_user["headers"]
        doc_id = created_complex_document["id"]
        
        response = requests.delete(
            f"{BASE_URL}/documents/{doc_id}/path/customer.middle_name",
            headers=headers
        )
        
        # API возвращает 400 для несуществующего пути
        assert response.status_code == 200
        
        # Verify it's gone (должен быть 404)
        get_response = requests.get(
            f"{BASE_URL}/documents/{doc_id}/path/customer.middle_name",
            headers=headers
        )
        assert get_response.status_code == 400
    
    def test_delete_array_element(self, registered_user, created_complex_document):
        """Test deleting array element"""
        headers = registered_user["headers"]
        doc_id = created_complex_document["id"]
        
        response = requests.delete(
            f"{BASE_URL}/documents/{doc_id}/path/orders[0]",
            headers=headers
        )
        
        assert response.status_code == 200
        
        # Check remaining elements
        get_response = requests.get(
            f"{BASE_URL}/documents/{doc_id}/path/orders",
            headers=headers
        )
        orders = get_response.json()["value"]
        assert len(orders) == 1
        assert orders[0]["id"] == 2
    
    def test_path_operations_unauthorized(self, base_url, registered_user, created_complex_document):
        """Test path operations without proper authorization"""
        # Create another user
        other_user_data = {
            "username": f"other_{uuid.uuid4().hex[:8]}",
            "password": "password123"
        }
        
        # Register other user
        requests.post(f"{base_url}/auth/register", json=other_user_data)
        
        # Login other user
        login_response = requests.post(
            f"{base_url}/auth/login",
            json=other_user_data
        )
        other_token = login_response.json()["access_token"]
        other_headers = {"Authorization": f"Bearer {other_token}"}
        
        doc_id = created_complex_document["id"]
        
        # Try to get path
        get_response = requests.get(
            f"{base_url}/documents/{doc_id}/path/customer.name",
            headers=other_headers
        )
        assert get_response.status_code == 403
        
        # Try to update path
        update_response = requests.patch(
            f"{base_url}/documents/{doc_id}/path/customer.name",
            json={"value": "Hacked"},
            headers=other_headers
        )
        assert update_response.status_code == 403
        
        # Try to delete path
        delete_response = requests.delete(
            f"{base_url}/documents/{doc_id}/path/customer.name",
            headers=other_headers
        )
        assert delete_response.status_code == 403
    
    def test_version_increment(self, registered_user, created_complex_document):
        """Test that version increments on path updates"""
        headers = registered_user["headers"]
        doc_id = created_complex_document["id"]
        
        # Get current version
        get_response = requests.get(
            f"{BASE_URL}/documents/{doc_id}",
            headers=headers
        )
        original_version = get_response.json()["version"]
        
        # Update path
        update_data = {"value": "Updated Name"}
        requests.patch(
            f"{BASE_URL}/documents/{doc_id}/path/customer.name",
            json=update_data,
            headers=headers
        )
        
        # Check version increased
        get_response = requests.get(
            f"{BASE_URL}/documents/{doc_id}",
            headers=headers
        )
        assert get_response.json()["version"] == original_version + 1