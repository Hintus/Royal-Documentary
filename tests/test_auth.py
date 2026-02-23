import pytest
import requests
from typing import Dict, Any
import uuid

BASE_URL = "http://localhost:8000/api"


def test_health_check():
    """Test health endpoint"""
    response = requests.get("http://localhost:8000/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_root_endpoint():
    """Test root endpoint"""
    response = requests.get("http://localhost:8000/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data


class TestAuth:
    """Test authentication endpoints"""
    
    def test_register_new_user(self, base_url):
        """Test user registration"""
        user_data = {
            "username": f"newuser_{uuid.uuid4().hex[:8]}",
            "password": "password123"
        }
        
        response = requests.post(
            f"{base_url}/auth/register",
            json=user_data
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == user_data["username"]
        assert "id" in data
        assert isinstance(data["id"], str)
    
    def test_register_duplicate_user(self, base_url):
        """Test registering same user twice"""
        # Create a fixed username for this test
        fixed_username = f"duplicate_test_{uuid.uuid4().hex[:8]}"
        user_data = {
            "username": fixed_username,
            "password": "password123"
        }
        
        # First registration should succeed
        response1 = requests.post(
            f"{base_url}/auth/register",
            json=user_data
        )
        assert response1.status_code == 200
        
        # Second registration with same username should fail
        response2 = requests.post(
            f"{base_url}/auth/register",
            json=user_data
        )
        assert response2.status_code == 400
        assert "already registered" in response2.text
    
    def test_login_success(self, base_url):
        """Test successful login"""
        # Create a user first
        username = f"login_test_{uuid.uuid4().hex[:8]}"
        user_data = {
            "username": username,
            "password": "password123"
        }
        
        # Register
        reg_response = requests.post(
            f"{base_url}/auth/register",
            json=user_data
        )
        assert reg_response.status_code == 200
        
        # Login
        login_response = requests.post(
            f"{base_url}/auth/login",
            json=user_data
        )
        
        assert login_response.status_code == 200
        data = login_response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert isinstance(data["access_token"], str)
        assert len(data["access_token"]) > 20
    
    def test_login_wrong_password(self, base_url):
        """Test login with wrong password"""
        # Create a user first
        username = f"wrong_pass_{uuid.uuid4().hex[:8]}"
        user_data = {
            "username": username,
            "password": "password123"
        }
        
        # Register
        requests.post(f"{base_url}/auth/register", json=user_data)
        
        # Try login with wrong password
        wrong_data = {
            "username": username,
            "password": "wrongpassword"
        }
        
        response = requests.post(
            f"{base_url}/auth/login",
            json=wrong_data
        )
        
        assert response.status_code == 401
        assert "incorrect" in response.text.lower()
    
    def test_login_nonexistent_user(self, base_url):
        """Test login with non-existent user"""
        nonexistent_data = {
            "username": f"nonexistent_{uuid.uuid4().hex[:8]}",
            "password": "password123"
        }
        
        response = requests.post(
            f"{base_url}/auth/login",
            json=nonexistent_data
        )
        
        assert response.status_code == 401
        assert "incorrect" in response.text.lower()
    
    def test_login_form(self, base_url):
        """Test OAuth2 form login"""
        # Create a user first
        username = f"form_test_{uuid.uuid4().hex[:8]}"
        user_data = {
            "username": username,
            "password": "password123"
        }
        
        # Register
        reg_response = requests.post(
            f"{base_url}/auth/register",
            json=user_data
        )
        assert reg_response.status_code == 200
        
        # Login with form
        response = requests.post(
            f"{base_url}/auth/login/form",
            data=user_data  # Use data, not json for form
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"


class TestProtectedEndpoints:
    """Test protected endpoints"""
    
    def test_get_me_without_token(self, base_url):
        """Test accessing protected endpoint without token"""
        response = requests.get(f"{base_url}/auth/me")
        assert response.status_code == 401
        assert "not authenticated" in response.text.lower()
    
    def test_get_me_with_token(self, base_url, registered_user):
        """Test accessing protected endpoint with valid token"""
        headers = registered_user["headers"]
        response = requests.get(
            f"{base_url}/auth/me",
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == registered_user["user"]["username"]
        assert "id" in data
        assert "is_active" in data
        assert "is_superuser" in data
    
    def test_get_me_with_invalid_token(self, base_url):
        """Test accessing protected endpoint with invalid token"""
        headers = {"Authorization": "Bearer invalid.token.here"}
        response = requests.get(
            f"{base_url}/auth/me",
            headers=headers
        )
        
        # Should be 401 or 403
        assert response.status_code in (401, 403)
    
    def test_logout(self, base_url, registered_user):
        """Test logout endpoint with authentication"""
        headers = registered_user["headers"]
        response = requests.post(
            f"{base_url}/auth/logout",
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Logged out successfully"
        assert "detail" in data  # Опционально


class TestUserInfo:
    """Test user information endpoints"""
    
    def test_user_info_structure(self, registered_user):
        """Test that user info has correct structure"""
        user = registered_user["user"]
        
        assert "id" in user
        assert "username" in user
        assert "is_active" in user
        assert "is_superuser" in user
        
        assert isinstance(user["id"], str)
        assert isinstance(user["username"], str)
        assert isinstance(user["is_active"], bool)
        assert isinstance(user["is_superuser"], bool)
    
    def test_user_id_is_uuid_string(self, registered_user):
        """Test that user ID is a valid UUID string"""
        import uuid
        user_id = registered_user["user"]["id"]
        
        # Should not raise exception
        uuid_obj = uuid.UUID(user_id)
        assert str(uuid_obj) == user_id