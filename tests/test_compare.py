import pytest
import requests
from typing import Dict, Any

BASE_URL = "http://localhost:8000/api"


@pytest.fixture
def doc1_data() -> Dict[str, Any]:
    """First test document."""
    return {
        "name": "Document 1",
        "content": {
            "name": "John",
            "age": 30,
            "address": {
                "city": "New York",
                "zip": 10001
            },
            "phones": ["123-4567", "890-1234"],
            "settings": {
                "theme": "dark",
                "notifications": True
            }
        }
    }


@pytest.fixture
def doc2_data() -> Dict[str, Any]:
    """Second test document with differences."""
    return {
        "name": "Document 2",
        "content": {
            "name": "John",
            "age": 31,
            "address": {
                "city": "Boston",
                "zip": 10001
            },
            "phones": ["123-4567", "555-1234"],
            "settings": {
                "theme": "light",
                "notifications": True,
                "language": "en"
            },
            "new_field": "value"
        }
    }


@pytest.fixture
def created_doc1(registered_user, doc1_data) -> str:
    """Create first document and return ID."""
    headers = registered_user["headers"]
    response = requests.post(
        f"{BASE_URL}/documents",
        json=doc1_data,
        headers=headers
    )
    assert response.status_code == 201
    return response.json()["id"]


@pytest.fixture
def created_doc2(registered_user, doc2_data) -> str:
    """Create second document and return ID."""
    headers = registered_user["headers"]
    response = requests.post(
        f"{BASE_URL}/documents",
        json=doc2_data,
        headers=headers
    )
    assert response.status_code == 201
    return response.json()["id"]


class TestDocumentCompare:
    """Test document comparison."""
    
    def test_compare_documents(self, registered_user, created_doc1, created_doc2):
        """Test comparing two documents."""
        headers = registered_user["headers"]
        
        response = requests.get(
            f"{BASE_URL}/documents/compare/{created_doc1}/{created_doc2}",
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check basic structure
        assert data["doc1_id"] == created_doc1
        assert data["doc2_id"] == created_doc2
        assert "doc1_name" in data
        assert "doc2_name" in data
        assert "changes" in data
        assert "summary" in data
        
        # Check summary
        summary = data["summary"]
        assert summary["added"] >= 1  # new_field added
        assert summary["removed"] >= 0
        assert summary["changed"] >= 3  # age, address.city, phones[1], settings.theme
        assert summary["unchanged"] >= 2  # name, phones[0], etc.
    
    def test_compare_changed_values(self, registered_user, created_doc1, created_doc2):
        """Test that changed values are correctly reported."""
        headers = registered_user["headers"]
        
        response = requests.get(
            f"{BASE_URL}/documents/compare/{created_doc1}/{created_doc2}",
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Find specific changes
        changes = {c["path"]: c for c in data["changes"]}
        
        # Age changed
        assert "age" in changes
        assert changes["age"]["type"] == "changed"
        assert changes["age"]["value"]["old"] == 30
        assert changes["age"]["value"]["new"] == 31
        
        # City changed
        assert "address.city" in changes
        assert changes["address.city"]["value"]["old"] == "New York"
        assert changes["address.city"]["value"]["new"] == "Boston"
        
        # Phone changed
        assert "phones[1]" in changes
        assert changes["phones[1]"]["value"]["old"] == "890-1234"
        assert changes["phones[1]"]["value"]["new"] == "555-1234"
        
        # Theme changed
        assert "settings.theme" in changes
        assert changes["settings.theme"]["value"]["old"] == "dark"
        assert changes["settings.theme"]["value"]["new"] == "light"
    
    def test_compare_added_field(self, registered_user, created_doc1, created_doc2):
        """Test that added fields are correctly reported."""
        headers = registered_user["headers"]
        
        response = requests.get(
            f"{BASE_URL}/documents/compare/{created_doc1}/{created_doc2}",
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        changes = {c["path"]: c for c in data["changes"]}
        
        # new_field added
        assert "new_field" in changes
        assert changes["new_field"]["type"] == "added"
        assert changes["new_field"]["value"]["new"] == "value"
    
    def test_compare_identical_documents(self, registered_user, created_doc1):
        """Test comparing a document with itself."""
        headers = registered_user["headers"]
        
        response = requests.get(
            f"{BASE_URL}/documents/compare/{created_doc1}/{created_doc1}",
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have no changes
        assert len(data["changes"]) == 0
        assert data["summary"]["added"] == 0
        assert data["summary"]["removed"] == 0
        assert data["summary"]["changed"] == 0
        assert data["summary"]["unchanged"] > 0
    
    def test_compare_different_owners(self, base_url, registered_user, another_user, created_doc1):
        """Test comparing documents with different owners."""
        # Create document for another user
        other_doc_data = {
            "name": "Other's Document",
            "content": {"data": "test"}
        }
        other_headers = another_user["headers"]
        create_response = requests.post(
            f"{base_url}/documents",
            json=other_doc_data,
            headers=other_headers
        )
        assert create_response.status_code == 201
        other_doc_id = create_response.json()["id"]
        
        # Try to compare as first user
        headers = registered_user["headers"]
        response = requests.get(
            f"{base_url}/documents/compare/{created_doc1}/{other_doc_id}",
            headers=headers
        )
        
        # Should be forbidden if other doc is not public
        assert response.status_code == 403
    
    def test_compare_nonexistent(self, registered_user):
        """Test comparing with non-existent document."""
        headers = registered_user["headers"]
        fake_id = "00000000-0000-0000-0000-000000000000"
        
        response = requests.get(
            f"{BASE_URL}/documents/compare/{fake_id}/{fake_id}",
            headers=headers
        )
        
        assert response.status_code == 404