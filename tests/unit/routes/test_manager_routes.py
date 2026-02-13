"""Unit tests for manager routes.

Tests cover:
- Access control (non-manager redirect, unauthenticated redirect)
- Dashboard (GET /dashboard/manager)
- Tracker details (GET /api/tracker/<uuid>)
- Consultant CRUD (create, update, delete)
- Establishment CRUD (create, update, delete)
- Plan edit (GET /manager/plan/<file_id>)
- Plan save (POST /manager/plan/<file_id>/save)
- Plan approve (POST /manager/plan/<file_id>/approve)
- API status (GET /api/status)
"""

import pytest
import uuid
import json
from datetime import datetime
from unittest.mock import MagicMock, patch, PropertyMock
from dataclasses import dataclass
from typing import Optional
from werkzeug.security import generate_password_hash


# ---------------------------------------------------------------------------
# PlanResult dataclass (mirroring the real one from plan_service)
# ---------------------------------------------------------------------------

@dataclass
class PlanResult:
    success: bool
    message: str
    whatsapp_link: Optional[str] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# MockUser for Flask-Login
# ---------------------------------------------------------------------------

class MockUser:
    """Mock user that satisfies Flask-Login requirements."""

    def __init__(self, **kwargs):
        self.id = kwargs.get('id', uuid.uuid4())
        self.email = kwargs.get('email', 'manager@test.com')
        self.name = kwargs.get('name', 'Manager')
        self.role = kwargs.get('role', 'MANAGER')
        self.password_hash = generate_password_hash('manager123')
        self.is_active = True
        self.is_authenticated = True
        self.must_change_password = False
        self.company_id = kwargs.get('company_id', uuid.uuid4())
        self.establishments = kwargs.get('establishments', [])

    def get_id(self):
        return str(self.id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _setup_manager_session(client, user, mock_auth_uow):
    """Configure mock auth UoW and set the user in the session."""
    auth_uow = MagicMock()
    auth_uow.users.get_by_id.return_value = user
    mock_auth_uow.return_value = auth_uow

    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)

    return auth_uow


JSON_HEADERS = {'Accept': 'application/json'}


# ===================================================================
#  ACCESS CONTROL
# ===================================================================

class TestManagerAccessControl:
    """Tests for manager route access restrictions."""

    def test_unauthenticated_user_redirected_to_login(self, client):
        """Unauthenticated user accessing /dashboard/manager is redirected to login."""
        response = client.get('/dashboard/manager')
        assert response.status_code == 302
        assert 'login' in response.location

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_non_manager_user_redirected(self, mock_auth_uow, mock_mgr_uow, client):
        """Non-manager user (CONSULTANT) accessing dashboard is redirected."""
        consultant = MockUser(role='CONSULTANT')
        _setup_manager_session(client, consultant, mock_auth_uow)
        mock_mgr_uow.return_value = MagicMock()

        response = client.get('/dashboard/manager')
        assert response.status_code == 302

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_non_manager_tracker_returns_403(self, mock_auth_uow, mock_mgr_uow, client):
        """Non-manager user accessing tracker returns 403."""
        consultant = MockUser(role='CONSULTANT')
        _setup_manager_session(client, consultant, mock_auth_uow)
        mock_mgr_uow.return_value = MagicMock()

        insp_id = uuid.uuid4()
        response = client.get(f'/api/tracker/{insp_id}', headers=JSON_HEADERS)
        assert response.status_code == 403


# ===================================================================
#  DASHBOARD MANAGER
# ===================================================================

class TestDashboardManager:
    """Tests for GET /dashboard/manager."""

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_dashboard_success(self, mock_auth_uow, mock_mgr_uow, client):
        """Manager can access dashboard successfully."""
        manager = MockUser(role='MANAGER')
        _setup_manager_session(client, manager, mock_auth_uow)

        mock_company = MagicMock()
        mock_company.establishments = []

        mock_uow = MagicMock()
        mock_uow.companies.get_by_id.return_value = mock_company
        mock_uow.users.get_consultants_for_company.return_value = []
        mock_mgr_uow.return_value = mock_uow

        response = client.get('/dashboard/manager')
        assert response.status_code == 200

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_dashboard_with_establishment_filter(self, mock_auth_uow, mock_mgr_uow, client):
        """Dashboard filters by establishment_id query param."""
        manager = MockUser(role='MANAGER')
        _setup_manager_session(client, manager, mock_auth_uow)

        est_id = uuid.uuid4()
        mock_est = MagicMock()
        mock_est.id = est_id
        mock_est.name = 'Test Establishment'

        mock_company = MagicMock()
        mock_company.establishments = [mock_est]

        mock_consultant = MagicMock()
        mock_consultant.establishments = [mock_est]

        mock_uow = MagicMock()
        mock_uow.companies.get_by_id.return_value = mock_company
        mock_uow.users.get_consultants_for_company.return_value = [mock_consultant]
        mock_mgr_uow.return_value = mock_uow

        response = client.get(f'/dashboard/manager?establishment_id={est_id}')
        assert response.status_code == 200

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_dashboard_no_company(self, mock_auth_uow, mock_mgr_uow, client):
        """Dashboard handles manager with no company."""
        manager = MockUser(role='MANAGER', company_id=None)
        _setup_manager_session(client, manager, mock_auth_uow)

        mock_uow = MagicMock()
        mock_uow.users.get_consultants_for_company.return_value = []
        mock_mgr_uow.return_value = mock_uow

        response = client.get('/dashboard/manager')
        assert response.status_code == 200


# ===================================================================
#  TRACKER DETAILS
# ===================================================================

class TestTrackerDetails:
    """Tests for GET /api/tracker/<uuid:inspection_id>."""

    @patch('src.manager_routes.get_tracker_service')
    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_tracker_success(self, mock_auth_uow, mock_mgr_uow, mock_get_tracker, client):
        """Tracker returns data for a valid inspection."""
        company_id = uuid.uuid4()
        manager = MockUser(role='MANAGER', company_id=company_id)
        _setup_manager_session(client, manager, mock_auth_uow)

        mock_est = MagicMock()
        mock_est.company_id = company_id

        mock_insp = MagicMock()
        mock_insp.establishment = mock_est

        mock_uow = MagicMock()
        mock_uow.inspections.get_by_id.return_value = mock_insp
        mock_mgr_uow.return_value = mock_uow

        tracker_data = {'status': 'COMPLETED', 'steps': []}
        mock_tracker_svc = MagicMock()
        mock_tracker_svc.get_tracker_data.return_value = tracker_data
        mock_get_tracker.return_value = mock_tracker_svc

        insp_id = uuid.uuid4()
        response = client.get(f'/api/tracker/{insp_id}', headers=JSON_HEADERS)
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'COMPLETED'

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_tracker_not_found(self, mock_auth_uow, mock_mgr_uow, client):
        """Tracker returns 404 when inspection not found."""
        manager = MockUser(role='MANAGER')
        _setup_manager_session(client, manager, mock_auth_uow)

        mock_uow = MagicMock()
        mock_uow.inspections.get_by_id.return_value = None
        mock_mgr_uow.return_value = mock_uow

        insp_id = uuid.uuid4()
        response = client.get(f'/api/tracker/{insp_id}', headers=JSON_HEADERS)
        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_tracker_wrong_company_returns_403(self, mock_auth_uow, mock_mgr_uow, client):
        """Tracker returns 403 when inspection belongs to different company."""
        manager = MockUser(role='MANAGER', company_id=uuid.uuid4())
        _setup_manager_session(client, manager, mock_auth_uow)

        mock_est = MagicMock()
        mock_est.company_id = uuid.uuid4()  # Different company

        mock_insp = MagicMock()
        mock_insp.establishment = mock_est

        mock_uow = MagicMock()
        mock_uow.inspections.get_by_id.return_value = mock_insp
        mock_mgr_uow.return_value = mock_uow

        insp_id = uuid.uuid4()
        response = client.get(f'/api/tracker/{insp_id}', headers=JSON_HEADERS)
        assert response.status_code == 403

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_tracker_no_establishment_returns_403(self, mock_auth_uow, mock_mgr_uow, client):
        """Tracker returns 403 when inspection has no establishment."""
        manager = MockUser(role='MANAGER')
        _setup_manager_session(client, manager, mock_auth_uow)

        mock_insp = MagicMock()
        mock_insp.establishment = None

        mock_uow = MagicMock()
        mock_uow.inspections.get_by_id.return_value = mock_insp
        mock_mgr_uow.return_value = mock_uow

        insp_id = uuid.uuid4()
        response = client.get(f'/api/tracker/{insp_id}', headers=JSON_HEADERS)
        assert response.status_code == 403


# ===================================================================
#  CREATE CONSULTANT
# ===================================================================

class TestCreateConsultant:
    """Tests for POST /manager/consultant/new."""

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_create_consultant_success(self, mock_auth_uow, mock_mgr_uow, client):
        """Successful consultant creation returns 201."""
        manager = MockUser(role='MANAGER')
        _setup_manager_session(client, manager, mock_auth_uow)

        est_id = uuid.uuid4()
        mock_est = MagicMock()
        mock_est.id = est_id
        mock_est.name = 'Test Store'

        mock_uow = MagicMock()
        mock_uow.establishments.get_by_id.return_value = mock_est
        mock_uow.users.get_by_email.return_value = None
        mock_mgr_uow.return_value = mock_uow

        response = client.post(
            '/manager/consultant/new',
            data={
                'name': 'New Consultant',
                'email': 'consultant@test.com',
                'establishment_ids': [str(est_id)],
            },
            headers=JSON_HEADERS,
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data['success'] is True
        assert 'consultant' in data
        assert data['consultant']['establishments'][0]['name'] == 'Test Store'
        mock_uow.users.add.assert_called_once()
        mock_uow.commit.assert_called_once()

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_create_consultant_missing_fields(self, mock_auth_uow, mock_mgr_uow, client):
        """Missing required fields returns 400."""
        manager = MockUser(role='MANAGER')
        _setup_manager_session(client, manager, mock_auth_uow)
        mock_mgr_uow.return_value = MagicMock()

        response = client.post(
            '/manager/consultant/new',
            data={'name': '', 'email': '', 'establishment_ids': []},
            headers=JSON_HEADERS,
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_create_consultant_duplicate_email(self, mock_auth_uow, mock_mgr_uow, client):
        """Duplicate email returns 400."""
        manager = MockUser(role='MANAGER')
        _setup_manager_session(client, manager, mock_auth_uow)

        est_id = uuid.uuid4()
        mock_est = MagicMock()
        mock_est.id = est_id

        existing_user = MagicMock()

        mock_uow = MagicMock()
        mock_uow.establishments.get_by_id.return_value = mock_est
        mock_uow.users.get_by_email.return_value = existing_user
        mock_mgr_uow.return_value = mock_uow

        response = client.post(
            '/manager/consultant/new',
            data={
                'name': 'Dup Consultant',
                'email': 'existing@test.com',
                'establishment_ids': [str(est_id)],
            },
            headers=JSON_HEADERS,
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_create_consultant_invalid_establishments(self, mock_auth_uow, mock_mgr_uow, client):
        """No valid establishments returns 400."""
        manager = MockUser(role='MANAGER')
        _setup_manager_session(client, manager, mock_auth_uow)

        mock_uow = MagicMock()
        mock_uow.establishments.get_by_id.return_value = None
        mock_mgr_uow.return_value = mock_uow

        response = client.post(
            '/manager/consultant/new',
            data={
                'name': 'Bad Consultant',
                'email': 'bad@test.com',
                'establishment_ids': [str(uuid.uuid4())],
            },
            headers=JSON_HEADERS,
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_create_consultant_exception_returns_500(self, mock_auth_uow, mock_mgr_uow, client):
        """Exception during creation returns 500."""
        manager = MockUser(role='MANAGER')
        _setup_manager_session(client, manager, mock_auth_uow)

        est_id = uuid.uuid4()
        mock_est = MagicMock()
        mock_est.id = est_id

        mock_uow = MagicMock()
        mock_uow.establishments.get_by_id.return_value = mock_est
        mock_uow.users.get_by_email.return_value = None
        mock_uow.commit.side_effect = Exception("DB error")
        mock_mgr_uow.return_value = mock_uow

        response = client.post(
            '/manager/consultant/new',
            data={
                'name': 'Fail Consultant',
                'email': 'fail@test.com',
                'establishment_ids': [str(est_id)],
            },
            headers=JSON_HEADERS,
        )
        assert response.status_code == 500
        data = response.get_json()
        assert 'error' in data
        mock_uow.rollback.assert_called_once()

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_create_consultant_non_manager_redirected(self, mock_auth_uow, mock_mgr_uow, client):
        """Non-manager user is redirected when creating consultant."""
        consultant = MockUser(role='CONSULTANT')
        _setup_manager_session(client, consultant, mock_auth_uow)
        mock_mgr_uow.return_value = MagicMock()

        response = client.post(
            '/manager/consultant/new',
            data={'name': 'X', 'email': 'x@test.com', 'establishment_ids': ['123']},
        )
        assert response.status_code == 302


# ===================================================================
#  UPDATE CONSULTANT
# ===================================================================

class TestUpdateConsultant:
    """Tests for POST /manager/consultant/<uuid>/update."""

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_update_consultant_success(self, mock_auth_uow, mock_mgr_uow, client):
        """Successful consultant update returns 200."""
        company_id = uuid.uuid4()
        manager = MockUser(role='MANAGER', company_id=company_id)
        _setup_manager_session(client, manager, mock_auth_uow)

        user_id = uuid.uuid4()
        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.role = 'CONSULTANT'
        mock_user.company_id = company_id
        mock_user.name = 'Old Name'
        mock_user.email = 'old@test.com'
        mock_user.establishments = []

        mock_uow = MagicMock()
        mock_uow.users.get_by_id.return_value = mock_user
        mock_uow.users.get_by_email.return_value = None
        mock_mgr_uow.return_value = mock_uow

        response = client.post(
            f'/manager/consultant/{user_id}/update',
            data={'name': 'New Name', 'email': 'new@test.com'},
            headers=JSON_HEADERS,
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        mock_uow.commit.assert_called_once()

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_update_consultant_missing_fields(self, mock_auth_uow, mock_mgr_uow, client):
        """Missing name or email returns 400."""
        manager = MockUser(role='MANAGER')
        _setup_manager_session(client, manager, mock_auth_uow)
        mock_mgr_uow.return_value = MagicMock()

        user_id = uuid.uuid4()
        response = client.post(
            f'/manager/consultant/{user_id}/update',
            data={'name': '', 'email': ''},
            headers=JSON_HEADERS,
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_update_consultant_not_found(self, mock_auth_uow, mock_mgr_uow, client):
        """Updating non-existent consultant returns 404."""
        manager = MockUser(role='MANAGER')
        _setup_manager_session(client, manager, mock_auth_uow)

        mock_uow = MagicMock()
        mock_uow.users.get_by_id.return_value = None
        mock_mgr_uow.return_value = mock_uow

        user_id = uuid.uuid4()
        response = client.post(
            f'/manager/consultant/{user_id}/update',
            data={'name': 'Ghost', 'email': 'ghost@test.com'},
            headers=JSON_HEADERS,
        )
        assert response.status_code == 404

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_update_consultant_wrong_company(self, mock_auth_uow, mock_mgr_uow, client):
        """Consultant from different company returns 403."""
        manager = MockUser(role='MANAGER', company_id=uuid.uuid4())
        _setup_manager_session(client, manager, mock_auth_uow)

        user_id = uuid.uuid4()
        mock_user = MagicMock()
        mock_user.role = 'CONSULTANT'
        mock_user.company_id = uuid.uuid4()  # Different company

        mock_uow = MagicMock()
        mock_uow.users.get_by_id.return_value = mock_user
        mock_mgr_uow.return_value = mock_uow

        response = client.post(
            f'/manager/consultant/{user_id}/update',
            data={'name': 'X', 'email': 'x@test.com'},
            headers=JSON_HEADERS,
        )
        assert response.status_code == 403

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_update_consultant_non_manager_returns_403(self, mock_auth_uow, mock_mgr_uow, client):
        """Non-manager user returns 403."""
        consultant = MockUser(role='CONSULTANT')
        _setup_manager_session(client, consultant, mock_auth_uow)
        mock_mgr_uow.return_value = MagicMock()

        user_id = uuid.uuid4()
        response = client.post(
            f'/manager/consultant/{user_id}/update',
            data={'name': 'X', 'email': 'x@test.com'},
            headers=JSON_HEADERS,
        )
        assert response.status_code == 403


# ===================================================================
#  DELETE CONSULTANT
# ===================================================================

class TestDeleteConsultant:
    """Tests for POST /manager/consultant/<uuid>/delete."""

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_delete_consultant_success(self, mock_auth_uow, mock_mgr_uow, client):
        """Successful consultant deletion returns 200."""
        company_id = uuid.uuid4()
        manager = MockUser(role='MANAGER', company_id=company_id)
        _setup_manager_session(client, manager, mock_auth_uow)

        user_id = uuid.uuid4()
        mock_user = MagicMock()
        mock_user.role = 'CONSULTANT'
        mock_user.company_id = company_id

        mock_uow = MagicMock()
        mock_uow.users.get_by_id.return_value = mock_user
        mock_mgr_uow.return_value = mock_uow

        response = client.post(
            f'/manager/consultant/{user_id}/delete',
            headers=JSON_HEADERS,
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        mock_uow.users.delete.assert_called_once_with(mock_user)
        mock_uow.commit.assert_called_once()

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_delete_consultant_not_found(self, mock_auth_uow, mock_mgr_uow, client):
        """Deleting non-existent consultant returns 404."""
        manager = MockUser(role='MANAGER')
        _setup_manager_session(client, manager, mock_auth_uow)

        mock_uow = MagicMock()
        mock_uow.users.get_by_id.return_value = None
        mock_mgr_uow.return_value = mock_uow

        user_id = uuid.uuid4()
        response = client.post(
            f'/manager/consultant/{user_id}/delete',
            headers=JSON_HEADERS,
        )
        assert response.status_code == 404

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_delete_consultant_wrong_company(self, mock_auth_uow, mock_mgr_uow, client):
        """Deleting consultant from different company returns 403."""
        manager = MockUser(role='MANAGER', company_id=uuid.uuid4())
        _setup_manager_session(client, manager, mock_auth_uow)

        user_id = uuid.uuid4()
        mock_user = MagicMock()
        mock_user.role = 'CONSULTANT'
        mock_user.company_id = uuid.uuid4()

        mock_uow = MagicMock()
        mock_uow.users.get_by_id.return_value = mock_user
        mock_mgr_uow.return_value = mock_uow

        response = client.post(
            f'/manager/consultant/{user_id}/delete',
            headers=JSON_HEADERS,
        )
        assert response.status_code == 403

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_delete_consultant_exception(self, mock_auth_uow, mock_mgr_uow, client):
        """Exception during deletion returns 500."""
        company_id = uuid.uuid4()
        manager = MockUser(role='MANAGER', company_id=company_id)
        _setup_manager_session(client, manager, mock_auth_uow)

        user_id = uuid.uuid4()
        mock_user = MagicMock()
        mock_user.role = 'CONSULTANT'
        mock_user.company_id = company_id

        mock_uow = MagicMock()
        mock_uow.users.get_by_id.return_value = mock_user
        mock_uow.users.delete.side_effect = Exception("DB error")
        mock_mgr_uow.return_value = mock_uow

        response = client.post(
            f'/manager/consultant/{user_id}/delete',
            headers=JSON_HEADERS,
        )
        assert response.status_code == 500
        mock_uow.rollback.assert_called_once()


# ===================================================================
#  CREATE ESTABLISHMENT
# ===================================================================

class TestCreateEstablishment:
    """Tests for POST /manager/establishment/new."""

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_create_establishment_success(self, mock_auth_uow, mock_mgr_uow, client):
        """Successful establishment creation returns 201."""
        company_id = uuid.uuid4()
        manager = MockUser(role='MANAGER', company_id=company_id)
        _setup_manager_session(client, manager, mock_auth_uow)

        mock_company = MagicMock()
        mock_company.name = 'Test Corp'
        mock_company.drive_folder_id = None

        mock_uow = MagicMock()
        mock_uow.companies.get_by_id.return_value = mock_company
        mock_mgr_uow.return_value = mock_uow

        response = client.post(
            '/manager/establishment/new',
            data={'name': 'New Establishment', 'code': 'EST001'},
            headers=JSON_HEADERS,
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data['success'] is True
        assert 'establishment' in data
        mock_uow.establishments.add.assert_called_once()
        mock_uow.commit.assert_called_once()

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_create_establishment_missing_name(self, mock_auth_uow, mock_mgr_uow, client):
        """Missing name returns 400."""
        manager = MockUser(role='MANAGER')
        _setup_manager_session(client, manager, mock_auth_uow)
        mock_mgr_uow.return_value = MagicMock()

        response = client.post(
            '/manager/establishment/new',
            data={'name': '', 'code': 'X'},
            headers=JSON_HEADERS,
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_create_establishment_no_company(self, mock_auth_uow, mock_mgr_uow, client):
        """Manager without company_id returns 400."""
        manager = MockUser(role='MANAGER', company_id=None)
        _setup_manager_session(client, manager, mock_auth_uow)
        mock_mgr_uow.return_value = MagicMock()

        response = client.post(
            '/manager/establishment/new',
            data={'name': 'Test Est'},
            headers=JSON_HEADERS,
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_create_establishment_exception(self, mock_auth_uow, mock_mgr_uow, client):
        """Exception during creation returns 500."""
        company_id = uuid.uuid4()
        manager = MockUser(role='MANAGER', company_id=company_id)
        _setup_manager_session(client, manager, mock_auth_uow)

        mock_uow = MagicMock()
        mock_uow.companies.get_by_id.return_value = MagicMock(drive_folder_id=None)
        mock_uow.establishments.add.side_effect = Exception("DB constraint")
        mock_mgr_uow.return_value = mock_uow

        response = client.post(
            '/manager/establishment/new',
            data={'name': 'Bad Est'},
            headers=JSON_HEADERS,
        )
        assert response.status_code == 500
        data = response.get_json()
        assert 'error' in data
        mock_uow.rollback.assert_called_once()

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_create_establishment_non_manager_redirected(self, mock_auth_uow, mock_mgr_uow, client):
        """Non-manager is redirected."""
        consultant = MockUser(role='CONSULTANT')
        _setup_manager_session(client, consultant, mock_auth_uow)
        mock_mgr_uow.return_value = MagicMock()

        response = client.post(
            '/manager/establishment/new',
            data={'name': 'X'},
        )
        assert response.status_code == 302


# ===================================================================
#  UPDATE ESTABLISHMENT
# ===================================================================

class TestUpdateEstablishment:
    """Tests for POST /manager/establishment/<uuid>/update."""

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_update_establishment_success(self, mock_auth_uow, mock_mgr_uow, client):
        """Successful establishment update returns 200."""
        company_id = uuid.uuid4()
        manager = MockUser(role='MANAGER', company_id=company_id)
        _setup_manager_session(client, manager, mock_auth_uow)

        est_id = uuid.uuid4()
        mock_est = MagicMock()
        mock_est.id = est_id
        mock_est.company_id = company_id
        mock_est.name = 'Old Name'
        mock_est.code = 'OLD'
        mock_est.responsible_name = None
        mock_est.responsible_email = None
        mock_est.responsible_phone = None

        mock_uow = MagicMock()
        mock_uow.establishments.get_by_id.return_value = mock_est
        mock_mgr_uow.return_value = mock_uow

        response = client.post(
            f'/manager/establishment/{est_id}/update',
            data={'name': 'Updated Name', 'code': 'NEW'},
            headers=JSON_HEADERS,
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        mock_uow.commit.assert_called_once()

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_update_establishment_missing_name(self, mock_auth_uow, mock_mgr_uow, client):
        """Missing name returns 400."""
        manager = MockUser(role='MANAGER')
        _setup_manager_session(client, manager, mock_auth_uow)
        mock_mgr_uow.return_value = MagicMock()

        est_id = uuid.uuid4()
        response = client.post(
            f'/manager/establishment/{est_id}/update',
            data={'name': ''},
            headers=JSON_HEADERS,
        )
        assert response.status_code == 400

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_update_establishment_not_found(self, mock_auth_uow, mock_mgr_uow, client):
        """Updating non-existent establishment returns 404."""
        manager = MockUser(role='MANAGER')
        _setup_manager_session(client, manager, mock_auth_uow)

        mock_uow = MagicMock()
        mock_uow.establishments.get_by_id.return_value = None
        mock_mgr_uow.return_value = mock_uow

        est_id = uuid.uuid4()
        response = client.post(
            f'/manager/establishment/{est_id}/update',
            data={'name': 'Ghost'},
            headers=JSON_HEADERS,
        )
        assert response.status_code == 404

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_update_establishment_wrong_company(self, mock_auth_uow, mock_mgr_uow, client):
        """Establishment from different company returns 403."""
        manager = MockUser(role='MANAGER', company_id=uuid.uuid4())
        _setup_manager_session(client, manager, mock_auth_uow)

        mock_est = MagicMock()
        mock_est.company_id = uuid.uuid4()

        mock_uow = MagicMock()
        mock_uow.establishments.get_by_id.return_value = mock_est
        mock_mgr_uow.return_value = mock_uow

        est_id = uuid.uuid4()
        response = client.post(
            f'/manager/establishment/{est_id}/update',
            data={'name': 'Other'},
            headers=JSON_HEADERS,
        )
        assert response.status_code == 403

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_update_establishment_non_manager_returns_403(self, mock_auth_uow, mock_mgr_uow, client):
        """Non-manager returns 403."""
        consultant = MockUser(role='CONSULTANT')
        _setup_manager_session(client, consultant, mock_auth_uow)
        mock_mgr_uow.return_value = MagicMock()

        est_id = uuid.uuid4()
        response = client.post(
            f'/manager/establishment/{est_id}/update',
            data={'name': 'X'},
            headers=JSON_HEADERS,
        )
        assert response.status_code == 403


# ===================================================================
#  DELETE ESTABLISHMENT
# ===================================================================

class TestDeleteEstablishment:
    """Tests for POST /manager/establishment/<uuid>/delete."""

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_delete_establishment_success(self, mock_auth_uow, mock_mgr_uow, client):
        """Successful establishment deletion returns 200."""
        company_id = uuid.uuid4()
        manager = MockUser(role='MANAGER', company_id=company_id)
        _setup_manager_session(client, manager, mock_auth_uow)

        est_id = uuid.uuid4()
        mock_est = MagicMock()
        mock_est.id = est_id
        mock_est.company_id = company_id
        mock_est.drive_folder_id = None

        mock_uow = MagicMock()
        mock_uow.establishments.get_by_id.return_value = mock_est
        mock_mgr_uow.return_value = mock_uow

        response = client.post(
            f'/manager/establishment/{est_id}/delete',
            headers=JSON_HEADERS,
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        mock_uow.establishments.delete.assert_called_once_with(mock_est)
        mock_uow.commit.assert_called_once()

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_delete_establishment_not_found(self, mock_auth_uow, mock_mgr_uow, client):
        """Deleting non-existent establishment returns 404."""
        manager = MockUser(role='MANAGER')
        _setup_manager_session(client, manager, mock_auth_uow)

        mock_uow = MagicMock()
        mock_uow.establishments.get_by_id.return_value = None
        mock_mgr_uow.return_value = mock_uow

        est_id = uuid.uuid4()
        response = client.post(
            f'/manager/establishment/{est_id}/delete',
            headers=JSON_HEADERS,
        )
        assert response.status_code == 404

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_delete_establishment_wrong_company(self, mock_auth_uow, mock_mgr_uow, client):
        """Deleting establishment from different company returns 403."""
        manager = MockUser(role='MANAGER', company_id=uuid.uuid4())
        _setup_manager_session(client, manager, mock_auth_uow)

        mock_est = MagicMock()
        mock_est.company_id = uuid.uuid4()

        mock_uow = MagicMock()
        mock_uow.establishments.get_by_id.return_value = mock_est
        mock_mgr_uow.return_value = mock_uow

        est_id = uuid.uuid4()
        response = client.post(
            f'/manager/establishment/{est_id}/delete',
            headers=JSON_HEADERS,
        )
        assert response.status_code == 403

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_delete_establishment_exception(self, mock_auth_uow, mock_mgr_uow, client):
        """Exception during deletion returns 500."""
        company_id = uuid.uuid4()
        manager = MockUser(role='MANAGER', company_id=company_id)
        _setup_manager_session(client, manager, mock_auth_uow)

        mock_est = MagicMock()
        mock_est.company_id = company_id
        mock_est.drive_folder_id = None

        mock_uow = MagicMock()
        mock_uow.establishments.get_by_id.return_value = mock_est
        mock_uow.establishments.delete.side_effect = Exception("FK constraint")
        mock_mgr_uow.return_value = mock_uow

        est_id = uuid.uuid4()
        response = client.post(
            f'/manager/establishment/{est_id}/delete',
            headers=JSON_HEADERS,
        )
        assert response.status_code == 500
        mock_uow.rollback.assert_called_once()


# ===================================================================
#  EDIT PLAN
# ===================================================================

class TestEditPlan:
    """Tests for GET /manager/plan/<file_id>."""

    @patch('src.manager_routes.render_template')
    @patch('src.manager_routes.get_inspection_data_service')
    @patch('src.auth.get_uow')
    def test_edit_plan_success(self, mock_auth_uow, mock_get_data_svc, mock_render, client):
        """Successful plan edit renders template."""
        mock_render.return_value = 'rendered'
        manager = MockUser(role='MANAGER')
        _setup_manager_session(client, manager, mock_auth_uow)

        mock_est = MagicMock()
        mock_est.name = 'Restaurante A'
        mock_est.responsible_name = 'Joao'
        mock_est.responsible_email = 'j@test.com'
        mock_est.responsible_phone = '11999999999'

        mock_inspection = MagicMock()
        mock_inspection.establishment = mock_est
        mock_inspection.created_at = datetime(2025, 1, 15, 10, 0, 0)
        mock_inspection.ai_raw_response = {}
        mock_inspection.status.value = 'PENDING_MANAGER_REVIEW'

        mock_plan = MagicMock()
        mock_plan.summary_text = 'Resumo teste'

        report_data = {
            'resumo_geral': 'Resumo',
            'areas_inspecionadas': [
                {'pontuacao_obtida': 7, 'pontuacao_maxima': 10},
                {'pontuacao_obtida': 8, 'pontuacao_maxima': 10},
            ],
        }

        mock_svc = MagicMock()
        mock_svc.get_plan_edit_data.return_value = {
            'inspection': mock_inspection,
            'plan': mock_plan,
            'data': report_data,
        }
        mock_get_data_svc.return_value = mock_svc

        response = client.get('/manager/plan/test-file-id')
        assert response.status_code == 200
        mock_render.assert_called_once()
        call_kwargs = mock_render.call_args
        assert call_kwargs[0][0] == 'manager_plan_edit.html'

    @patch('src.manager_routes.get_inspection_data_service')
    @patch('src.auth.get_uow')
    def test_edit_plan_not_found_redirects(self, mock_auth_uow, mock_get_data_svc, client):
        """Plan not found redirects to dashboard."""
        manager = MockUser(role='MANAGER')
        _setup_manager_session(client, manager, mock_auth_uow)

        mock_svc = MagicMock()
        mock_svc.get_plan_edit_data.return_value = None
        mock_get_data_svc.return_value = mock_svc

        # Also mock _try_migrate_from_drive to return None
        with patch('src.manager_routes._try_migrate_from_drive', return_value=None):
            response = client.get('/manager/plan/nonexistent-id')
            assert response.status_code == 302

    @patch('src.manager_routes.render_template')
    @patch('src.manager_routes.get_inspection_data_service')
    @patch('src.auth.get_uow')
    def test_edit_plan_normalizes_missing_keys(self, mock_auth_uow, mock_get_data_svc, mock_render, client):
        """Plan edit normalizes missing template keys."""
        mock_render.return_value = 'rendered'
        manager = MockUser(role='MANAGER')
        _setup_manager_session(client, manager, mock_auth_uow)

        mock_est = MagicMock()
        mock_est.name = 'Test Est'
        mock_est.responsible_name = None
        mock_est.responsible_email = None
        mock_est.responsible_phone = None

        mock_inspection = MagicMock()
        mock_inspection.establishment = mock_est
        mock_inspection.created_at = datetime(2025, 1, 15)
        mock_inspection.ai_raw_response = {'summary': 'AI summary'}
        mock_inspection.status.value = 'PENDING_MANAGER_REVIEW'

        mock_plan = MagicMock()
        mock_plan.summary_text = None

        # Provide minimal data without template-expected keys
        report_data = {}

        mock_svc = MagicMock()
        mock_svc.get_plan_edit_data.return_value = {
            'inspection': mock_inspection,
            'plan': mock_plan,
            'data': report_data,
        }
        mock_get_data_svc.return_value = mock_svc

        response = client.get('/manager/plan/normalize-test')
        assert response.status_code == 200
        # Verify normalization happened: the route should have set these keys
        call_kwargs = mock_render.call_args[1]
        assert call_kwargs['report_data'].get('nome_estabelecimento') == 'Test Est'
        assert call_kwargs['report_data'].get('aproveitamento_geral') == 0
        # resumo_geral should fall back to AI summary
        assert call_kwargs['report_data'].get('resumo_geral') == 'AI summary'

    @patch('src.manager_routes.render_template')
    @patch('src.manager_routes.get_inspection_data_service')
    @patch('src.auth.get_uow')
    def test_edit_plan_score_calculation(self, mock_auth_uow, mock_get_data_svc, mock_render, client):
        """Plan edit recalculates scores from areas."""
        mock_render.return_value = 'rendered'
        manager = MockUser(role='MANAGER')
        _setup_manager_session(client, manager, mock_auth_uow)

        mock_est = MagicMock()
        mock_est.name = 'Score Est'
        mock_est.responsible_name = None
        mock_est.responsible_email = None
        mock_est.responsible_phone = None

        mock_inspection = MagicMock()
        mock_inspection.establishment = mock_est
        mock_inspection.created_at = datetime(2025, 3, 1)
        mock_inspection.ai_raw_response = {}
        mock_inspection.status.value = 'PENDING_MANAGER_REVIEW'

        mock_plan = MagicMock()
        mock_plan.summary_text = 'Resumo'

        report_data = {
            'resumo_geral': 'Test',
            'areas_inspecionadas': [
                {'pontuacao_obtida': 5, 'pontuacao_maxima': 10},
                {'pontuacao_obtida': 5, 'pontuacao_maxima': 10},
            ],
            # pontuacao_geral and pontuacao_maxima_geral deliberately missing
        }

        mock_svc = MagicMock()
        mock_svc.get_plan_edit_data.return_value = {
            'inspection': mock_inspection,
            'plan': mock_plan,
            'data': report_data,
        }
        mock_get_data_svc.return_value = mock_svc

        response = client.get('/manager/plan/score-calc')
        assert response.status_code == 200
        # Verify score recalculation happened
        call_kwargs = mock_render.call_args[1]
        rd = call_kwargs['report_data']
        assert rd['pontuacao_geral'] == 10.0
        assert rd['pontuacao_maxima_geral'] == 20.0
        assert rd['aproveitamento_geral'] == 50.0

    @patch('src.manager_routes.get_inspection_data_service')
    @patch('src.auth.get_uow')
    def test_edit_plan_exception_redirects(self, mock_auth_uow, mock_get_data_svc, client):
        """Exception during plan edit redirects to dashboard."""
        manager = MockUser(role='MANAGER')
        _setup_manager_session(client, manager, mock_auth_uow)

        mock_svc = MagicMock()
        mock_svc.get_plan_edit_data.side_effect = Exception("Service error")
        mock_get_data_svc.return_value = mock_svc

        response = client.get('/manager/plan/error-id')
        assert response.status_code == 302


# ===================================================================
#  SAVE PLAN
# ===================================================================

class TestSavePlan:
    """Tests for POST /manager/plan/<file_id>/save."""

    @patch('src.manager_routes.get_plan_service')
    @patch('src.auth.get_uow')
    def test_save_plan_success(self, mock_auth_uow, mock_get_plan_svc, client):
        """Successful plan save returns JSON with whatsapp_link."""
        manager = MockUser(role='MANAGER')
        _setup_manager_session(client, manager, mock_auth_uow)

        mock_svc = MagicMock()
        mock_svc.save_plan.return_value = PlanResult(
            success=True,
            message='Plano salvo!',
            whatsapp_link='https://wa.me/5511999999999',
        )
        mock_get_plan_svc.return_value = mock_svc

        response = client.post(
            '/manager/plan/test-file/save',
            json={'items': [], 'summary': 'test'},
            headers=JSON_HEADERS,
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'whatsapp_link' in data

    @patch('src.manager_routes.get_plan_service')
    @patch('src.auth.get_uow')
    def test_save_plan_not_found(self, mock_auth_uow, mock_get_plan_svc, client):
        """Plan not found returns 404."""
        manager = MockUser(role='MANAGER')
        _setup_manager_session(client, manager, mock_auth_uow)

        mock_svc = MagicMock()
        mock_svc.save_plan.return_value = PlanResult(
            success=False,
            message='Plano nao encontrado.',
            error='NOT_FOUND',
        )
        mock_get_plan_svc.return_value = mock_svc

        response = client.post(
            '/manager/plan/missing-file/save',
            json={'items': []},
            headers=JSON_HEADERS,
        )
        assert response.status_code == 404

    @patch('src.manager_routes.get_plan_service')
    @patch('src.auth.get_uow')
    def test_save_plan_forbidden(self, mock_auth_uow, mock_get_plan_svc, client):
        """Save plan with unauthorized error returns 403."""
        manager = MockUser(role='MANAGER')
        _setup_manager_session(client, manager, mock_auth_uow)

        mock_svc = MagicMock()
        mock_svc.save_plan.return_value = PlanResult(
            success=False,
            message='Acesso negado.',
            error='FORBIDDEN',
        )
        mock_get_plan_svc.return_value = mock_svc

        response = client.post(
            '/manager/plan/forbidden-file/save',
            json={'items': []},
            headers=JSON_HEADERS,
        )
        assert response.status_code == 403

    @patch('src.manager_routes.get_plan_service')
    @patch('src.auth.get_uow')
    def test_save_plan_no_data(self, mock_auth_uow, mock_get_plan_svc, client):
        """Save plan without JSON data returns 400."""
        manager = MockUser(role='MANAGER')
        _setup_manager_session(client, manager, mock_auth_uow)
        mock_get_plan_svc.return_value = MagicMock()

        response = client.post(
            '/manager/plan/test-file/save',
            data='null',
            content_type='application/json',
            headers=JSON_HEADERS,
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    @patch('src.auth.get_uow')
    def test_save_plan_non_manager_non_admin_non_consultant(self, mock_auth_uow, client):
        """User with invalid role gets 403."""
        user = MockUser(role='OTHER')
        _setup_manager_session(client, user, mock_auth_uow)

        response = client.post(
            '/manager/plan/test-file/save',
            json={'items': []},
            headers=JSON_HEADERS,
        )
        assert response.status_code == 403


# ===================================================================
#  APPROVE PLAN
# ===================================================================

class TestApprovePlan:
    """Tests for POST /manager/plan/<file_id>/approve."""

    @patch('src.manager_routes.get_plan_service')
    @patch('src.auth.get_uow')
    def test_approve_plan_success(self, mock_auth_uow, mock_get_plan_svc, client):
        """Successful plan approval returns 200."""
        manager = MockUser(role='MANAGER')
        _setup_manager_session(client, manager, mock_auth_uow)

        mock_svc = MagicMock()
        mock_svc.approve_plan.return_value = PlanResult(
            success=True,
            message='Plano aprovado!',
        )
        mock_get_plan_svc.return_value = mock_svc

        response = client.post(
            '/manager/plan/test-file/approve',
            headers=JSON_HEADERS,
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

    @patch('src.manager_routes.get_plan_service')
    @patch('src.auth.get_uow')
    def test_approve_plan_admin_allowed(self, mock_auth_uow, mock_get_plan_svc, client):
        """Admin can also approve plans."""
        admin = MockUser(role='ADMIN')
        _setup_manager_session(client, admin, mock_auth_uow)

        mock_svc = MagicMock()
        mock_svc.approve_plan.return_value = PlanResult(
            success=True,
            message='Plano aprovado pelo admin!',
        )
        mock_get_plan_svc.return_value = mock_svc

        response = client.post(
            '/manager/plan/test-file/approve',
            headers=JSON_HEADERS,
        )
        assert response.status_code == 200

    @patch('src.manager_routes.get_plan_service')
    @patch('src.auth.get_uow')
    def test_approve_plan_not_found(self, mock_auth_uow, mock_get_plan_svc, client):
        """Approving non-existent plan returns 404."""
        manager = MockUser(role='MANAGER')
        _setup_manager_session(client, manager, mock_auth_uow)

        mock_svc = MagicMock()
        mock_svc.approve_plan.return_value = PlanResult(
            success=False,
            message='Plano nao encontrado.',
        )
        mock_get_plan_svc.return_value = mock_svc

        response = client.post(
            '/manager/plan/missing/approve',
            headers=JSON_HEADERS,
        )
        assert response.status_code == 404

    @patch('src.auth.get_uow')
    def test_approve_plan_consultant_denied(self, mock_auth_uow, client):
        """Consultant cannot approve plans."""
        consultant = MockUser(role='CONSULTANT')
        _setup_manager_session(client, consultant, mock_auth_uow)

        response = client.post(
            '/manager/plan/test-file/approve',
            headers=JSON_HEADERS,
        )
        assert response.status_code == 403


# ===================================================================
#  API STATUS
# ===================================================================

class TestApiStatus:
    """Tests for GET /api/status."""

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_api_status_success(self, mock_auth_uow, mock_mgr_uow, client):
        """API status returns pending and processed lists."""
        company_id = uuid.uuid4()
        manager = MockUser(role='MANAGER', company_id=company_id)
        _setup_manager_session(client, manager, mock_auth_uow)

        mock_uow = MagicMock()
        mock_uow.inspections.get_for_manager.return_value = []
        mock_uow.establishments.get_by_company.return_value = []
        mock_uow.jobs.get_pending_for_company.return_value = []
        mock_mgr_uow.return_value = mock_uow

        response = client.get('/api/status', headers=JSON_HEADERS)
        assert response.status_code == 200
        data = response.get_json()
        assert 'pending' in data
        assert 'processed_raw' in data

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_api_status_with_inspections(self, mock_auth_uow, mock_mgr_uow, client):
        """API status maps inspections correctly."""
        company_id = uuid.uuid4()
        manager = MockUser(role='MANAGER', company_id=company_id)
        _setup_manager_session(client, manager, mock_auth_uow)

        mock_est = MagicMock()
        mock_est.name = 'Rest A'
        mock_est.id = uuid.uuid4()

        mock_insp = MagicMock()
        mock_insp.id = uuid.uuid4()
        mock_insp.establishment = mock_est
        mock_insp.created_at = datetime(2025, 6, 15, 14, 30, 0)
        mock_insp.status = MagicMock()
        mock_insp.status.value = 'PENDING_MANAGER_REVIEW'
        mock_insp.status.__eq__ = lambda self, other: self.value == (other.value if hasattr(other, 'value') else other)
        mock_insp.drive_file_id = 'file-123'

        mock_uow = MagicMock()
        mock_uow.inspections.get_for_manager.return_value = [mock_insp]
        mock_uow.establishments.get_by_company.return_value = [mock_est]
        mock_uow.jobs.get_pending_for_company.return_value = []
        mock_uow.jobs.get_job_info_map.return_value = {'file-123': {'filename': 'report.pdf', 'uploaded_by_name': 'Ana Consultora'}}
        mock_mgr_uow.return_value = mock_uow

        response = client.get('/api/status', headers=JSON_HEADERS)
        assert response.status_code == 200
        data = response.get_json()
        assert len(data['processed_raw']) == 1
        assert data['processed_raw'][0]['establishment'] == 'Rest A'
        assert data['processed_raw'][0]['filename'] == 'report.pdf'
        assert data['processed_raw'][0]['consultant'] == 'Ana Consultora'

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_api_status_skips_processing_inspections(self, mock_auth_uow, mock_mgr_uow, client):
        """API status skips inspections with PROCESSING status."""
        from src.models_db import InspectionStatus

        company_id = uuid.uuid4()
        manager = MockUser(role='MANAGER', company_id=company_id)
        _setup_manager_session(client, manager, mock_auth_uow)

        mock_insp = MagicMock()
        mock_insp.status = InspectionStatus.PROCESSING

        mock_uow = MagicMock()
        mock_uow.inspections.get_for_manager.return_value = [mock_insp]
        mock_uow.establishments.get_by_company.return_value = []
        mock_uow.jobs.get_pending_for_company.return_value = []
        mock_uow.jobs.get_job_info_map.return_value = {}
        mock_mgr_uow.return_value = mock_uow

        response = client.get('/api/status', headers=JSON_HEADERS)
        assert response.status_code == 200
        data = response.get_json()
        assert len(data['processed_raw']) == 0

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_api_status_exception(self, mock_auth_uow, mock_mgr_uow, client):
        """Exception in API status returns 500."""
        manager = MockUser(role='MANAGER')
        _setup_manager_session(client, manager, mock_auth_uow)

        mock_uow = MagicMock()
        mock_uow.inspections.get_for_manager.side_effect = Exception("DB timeout")
        mock_mgr_uow.return_value = mock_uow

        response = client.get('/api/status', headers=JSON_HEADERS)
        assert response.status_code == 500
        data = response.get_json()
        assert 'error' in data
