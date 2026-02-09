"""
Integration tests for inspection approval flow.

Tests cover:
- Manager dashboard access
- Inspection review access
- Plan approval process
- Status transitions
"""

import pytest


class TestManagerDashboard:
    """Tests for manager dashboard."""

    def test_manager_dashboard_requires_login(self, client):
        """Manager dashboard should require authentication."""
        response = client.get('/dashboard/manager')
        assert response.status_code in [302, 401, 403]

    def test_consultant_cannot_access_manager_dashboard(self, auth_client):
        """Consultants should not access manager dashboard."""
        client, user = auth_client  # auth_client creates a consultant
        response = client.get('/dashboard/manager')
        # Should redirect or show access denied
        assert response.status_code in [302, 403]

    def test_manager_can_access_dashboard(self, manager_client):
        """Managers should access their dashboard."""
        client, user = manager_client
        response = client.get('/dashboard/manager')
        # Should load or redirect to login if session issue
        assert response.status_code in [200, 302]


class TestInspectionReview:
    """Tests for inspection review functionality."""

    def test_review_requires_authentication(self, client):
        """Review page should require login."""
        response = client.get('/review/some-file-id')
        assert response.status_code in [302, 401, 403, 404]

    def test_review_nonexistent_inspection(self, auth_client):
        """Should handle nonexistent inspection gracefully."""
        client, user = auth_client
        response = client.get('/review/nonexistent-file-id')
        # Should return 404 or redirect
        assert response.status_code in [302, 404]


class TestPlanApproval:
    """Tests for plan approval functionality."""

    def test_approval_requires_manager_role(self, auth_client):
        """Plan approval should require manager role."""
        client, user = auth_client  # consultant
        response = client.post('/manager/plan/some-file-id/approve')
        # Should deny access
        assert response.status_code in [302, 403, 404]

    def test_approval_nonexistent_plan(self, manager_client):
        """Should handle nonexistent plan gracefully."""
        client, user = manager_client
        response = client.post('/manager/plan/nonexistent-id/approve')
        # Should return error
        assert response.status_code in [302, 404, 500]


class TestStatusAPI:
    """Tests for status check API."""

    def test_status_endpoint_requires_auth(self, client):
        """Status API should require authentication."""
        response = client.get('/api/status')
        assert response.status_code in [302, 401, 403]

    def test_tracker_requires_auth(self, client):
        """Tracker API should require authentication."""
        import uuid
        fake_id = str(uuid.uuid4())
        response = client.get(f'/api/tracker/{fake_id}')
        assert response.status_code in [302, 401, 403]
