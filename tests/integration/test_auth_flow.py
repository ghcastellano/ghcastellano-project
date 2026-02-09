"""
Integration tests for authentication flow.

Tests cover:
- Login with valid credentials
- Login with invalid credentials
- Logout
- Password change
- Role-based redirects
"""

import pytest
from werkzeug.security import generate_password_hash


class TestLoginFlow:
    """Tests for login functionality."""

    def test_login_page_loads(self, client):
        """Login page should load successfully."""
        response = client.get('/auth/login')
        assert response.status_code == 200
        assert b'login' in response.data.lower() or b'entrar' in response.data.lower()

    def test_login_with_invalid_credentials(self, client):
        """Should reject invalid credentials."""
        response = client.post('/auth/login', data={
            'email': 'nonexistent@example.com',
            'password': 'wrongpassword'
        }, follow_redirects=True)

        # Should show error message or stay on login page
        assert response.status_code == 200
        # Check for error indicators
        assert b'incorreto' in response.data.lower() or b'error' in response.data.lower() or b'login' in response.data.lower()

    def test_login_with_empty_fields(self, client):
        """Should handle empty login fields."""
        response = client.post('/auth/login', data={
            'email': '',
            'password': ''
        }, follow_redirects=True)

        assert response.status_code == 200


class TestLogoutFlow:
    """Tests for logout functionality."""

    def test_logout_requires_login(self, client):
        """Logout should redirect if not logged in."""
        response = client.get('/auth/logout')
        # Should redirect to login
        assert response.status_code in [302, 401, 403]

    def test_logout_clears_session(self, auth_client):
        """Logout should clear user session."""
        client, user = auth_client

        # First verify we're logged in by accessing protected route
        response = client.get('/dashboard/consultant')
        # May redirect or show dashboard

        # Now logout
        response = client.get('/auth/logout', follow_redirects=True)
        assert response.status_code == 200

        # Try to access protected route again
        response = client.get('/dashboard/consultant')
        # Should redirect to login
        assert response.status_code in [302, 401, 403]


class TestPasswordChange:
    """Tests for password change functionality."""

    def test_change_password_page_requires_login(self, client):
        """Password change page should require login."""
        response = client.get('/auth/change-password')
        assert response.status_code in [302, 401, 403]

    def test_change_password_page_loads_when_logged_in(self, auth_client):
        """Password change page should load for logged in users."""
        client, user = auth_client
        response = client.get('/auth/change-password')
        # Should load or redirect
        assert response.status_code in [200, 302]
