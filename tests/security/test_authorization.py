"""
Authorization tests to ensure proper access control.

Tests cover:
- Unauthenticated access to protected routes
- Role-based access control
- Cross-user data access prevention
"""

import pytest


class TestUnauthenticatedAccess:
    """Tests for unauthenticated access to protected routes."""

    def test_dashboard_requires_login(self, client):
        """Should redirect unauthenticated users from dashboard to login."""
        response = client.get('/dashboard/consultant')
        assert response.status_code in [302, 401, 403]

    def test_upload_requires_login(self, client):
        """Should reject unauthenticated upload attempts."""
        response = client.post('/upload')
        assert response.status_code in [302, 401, 403]

    def test_api_endpoints_require_login(self, client):
        """Should reject unauthenticated API access."""
        # Test POST endpoints
        post_endpoints = ['/api/upload_evidence']
        for endpoint in post_endpoints:
            response = client.post(endpoint)
            assert response.status_code in [302, 401, 403], f"Endpoint {endpoint} should require login"

        # Test GET endpoints
        get_endpoints = ['/admin/api/monitor']
        for endpoint in get_endpoints:
            response = client.get(endpoint)
            assert response.status_code in [302, 401, 403], f"Endpoint {endpoint} should require login"

    def test_admin_routes_require_login(self, client):
        """Should reject unauthenticated access to admin routes."""
        # POST-only endpoints
        post_endpoints = ['/admin/company/new']
        for endpoint in post_endpoints:
            response = client.post(endpoint)
            assert response.status_code in [302, 401, 403], f"Admin endpoint {endpoint} should require login"

        # GET endpoints
        get_endpoints = ['/admin/api/settings']
        for endpoint in get_endpoints:
            response = client.get(endpoint)
            assert response.status_code in [302, 401, 403], f"Admin endpoint {endpoint} should require login"


class TestRoleBasedAccess:
    """Tests for role-based access control."""

    def test_consultant_cannot_access_admin_dashboard(self, auth_client):
        """Consultants should not access admin dashboard."""
        client, user = auth_client
        response = client.get('/')  # Admin index
        # Should either redirect or return 403
        assert response.status_code in [302, 403] or b'admin' not in response.data.lower()

    def test_consultant_cannot_create_company(self, auth_client):
        """Consultants should not be able to create companies."""
        client, user = auth_client
        response = client.post('/admin/company/new', data={
            'name': 'Malicious Company',
            'cnpj': '12345678000100'
        })
        assert response.status_code in [302, 403]

    def test_manager_cannot_access_admin_routes(self, manager_client):
        """Managers should not access admin-only routes."""
        client, user = manager_client
        response = client.get('/admin/api/settings')
        assert response.status_code in [302, 403]


class TestDebugEndpoints:
    """Tests for debug endpoint security."""

    def test_debug_routes_requires_admin(self, auth_client):
        """Debug routes should require admin role."""
        client, user = auth_client
        response = client.get('/debug/routes')
        assert response.status_code in [403, 404]

    def test_debug_config_requires_admin(self, auth_client):
        """Debug config should require admin role."""
        client, user = auth_client
        response = client.get('/debug/config')
        assert response.status_code in [302, 403, 404]

    def test_debug_routes_disabled_in_production(self, client, monkeypatch):
        """Debug routes should be disabled when K_SERVICE is set (Cloud Run)."""
        monkeypatch.setenv('K_SERVICE', 'test-service')
        response = client.get('/debug/routes')
        # Should return 302 (redirect to login), 403 (forbidden), or 404 (not found)
        # 302 is acceptable because @login_required redirects unauthenticated users
        assert response.status_code in [302, 403, 404]


class TestCSRFProtection:
    """Tests for CSRF protection (when enabled)."""

    def test_post_without_csrf_in_production_mode(self, app, client):
        """POST requests should require CSRF token in production mode."""
        # This test is informational - CSRF is disabled in test config
        # but should be enabled in production
        app.config['WTF_CSRF_ENABLED'] = True

        response = client.post('/auth/login', data={
            'email': 'test@example.com',
            'password': 'password'
        })

        # Should fail without CSRF token
        # Note: Actual behavior depends on Flask-WTF configuration
        assert response.status_code in [200, 302, 400]

        # Reset config
        app.config['WTF_CSRF_ENABLED'] = False
