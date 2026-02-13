"""Extra unit tests for uncovered branches in manager_routes.py and patcher.py.

Covers:
- Dashboard session filter: empty string clears session, session persistence
- create_consultant HTML fallbacks (missing fields, invalid UUID, no valid
  establishments, duplicate email, email send failure, success, exception)
- update_consultant: password update, establishment_ids update, exception
- _try_migrate_from_drive via edit_plan route
- approve_plan error handling
- patcher.run_auto_patch: success, connection error, individual patch failure,
  google.auth detection, metadata server fallback
"""

import sys
import uuid
import json
import logging
from datetime import datetime
from unittest.mock import MagicMock, patch, PropertyMock
from dataclasses import dataclass
from typing import Optional

import pytest
from werkzeug.security import generate_password_hash


# ---------------------------------------------------------------------------
# PlanResult dataclass (mirrors src.application.plan_service.PlanResult)
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
    """Mock user satisfying Flask-Login requirements."""

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

def _setup_auth(client, user, mock_auth_uow):
    """Configure mock auth UoW and set user in session."""
    auth_uow = MagicMock()
    auth_uow.users.get_by_id.return_value = user
    mock_auth_uow.return_value = auth_uow

    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)

    return auth_uow


# HTML form headers -- deliberately omit Accept: application/json
HTML_HEADERS = {'Content-Type': 'application/x-www-form-urlencoded'}


# ===================================================================
#  DASHBOARD SESSION FILTER (lines 56-57, 59)
# ===================================================================

class TestDashboardSessionFilter:
    """Tests for session-based establishment filter persistence."""

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_empty_establishment_id_clears_session(
        self, mock_auth_uow, mock_mgr_uow, client
    ):
        """When establishment_id is empty string, session key is cleared."""
        manager = MockUser(role='MANAGER')
        _setup_auth(client, manager, mock_auth_uow)

        mock_company = MagicMock()
        mock_company.establishments = []
        mock_uow = MagicMock()
        mock_uow.companies.get_by_id.return_value = mock_company
        mock_uow.users.get_consultants_for_company.return_value = []
        mock_mgr_uow.return_value = mock_uow

        # Pre-set session with a selected establishment
        with client.session_transaction() as sess:
            sess['selected_est_id'] = str(uuid.uuid4())

        # Send empty string to clear
        response = client.get('/dashboard/manager?establishment_id=')
        assert response.status_code == 200

        with client.session_transaction() as sess:
            assert 'selected_est_id' not in sess

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_session_persists_establishment_filter(
        self, mock_auth_uow, mock_mgr_uow, client
    ):
        """When no param but session has selected_est_id, it is used."""
        manager = MockUser(role='MANAGER')
        _setup_auth(client, manager, mock_auth_uow)

        est_id = uuid.uuid4()
        mock_est = MagicMock()
        mock_est.id = est_id
        mock_est.name = 'Session Est'

        mock_company = MagicMock()
        mock_company.establishments = [mock_est]
        mock_uow = MagicMock()
        mock_uow.companies.get_by_id.return_value = mock_company
        mock_uow.users.get_consultants_for_company.return_value = []
        mock_mgr_uow.return_value = mock_uow

        # Set session value
        with client.session_transaction() as sess:
            sess['selected_est_id'] = str(est_id)

        # Request without query param -- uses session value
        response = client.get('/dashboard/manager')
        assert response.status_code == 200

        # Verify session still has the value
        with client.session_transaction() as sess:
            assert sess.get('selected_est_id') == str(est_id)


# ===================================================================
#  CREATE CONSULTANT -- HTML FALLBACKS
# ===================================================================

class TestCreateConsultantHTML:
    """Tests for create_consultant HTML form responses (no Accept: JSON)."""

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_missing_fields_html_flash_redirect(
        self, mock_auth_uow, mock_mgr_uow, client
    ):
        """Missing fields with HTML form -> flash + redirect (lines 121-122)."""
        manager = MockUser(role='MANAGER')
        _setup_auth(client, manager, mock_auth_uow)
        mock_mgr_uow.return_value = MagicMock()

        response = client.post(
            '/manager/consultant/new',
            data={'name': '', 'email': '', 'establishment_ids': []},
            headers=HTML_HEADERS,
        )
        assert response.status_code == 302
        assert '/dashboard/manager' in response.location

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_invalid_establishment_uuid_html(
        self, mock_auth_uow, mock_mgr_uow, client
    ):
        """Invalid UUID for establishment_id -> caught, no valid ests (lines 133-134)."""
        manager = MockUser(role='MANAGER')
        _setup_auth(client, manager, mock_auth_uow)

        mock_uow = MagicMock()
        # get_by_id will never be called for invalid UUID because uuid.UUID() raises
        mock_mgr_uow.return_value = mock_uow

        response = client.post(
            '/manager/consultant/new',
            data={
                'name': 'Test',
                'email': 'test@test.com',
                'establishment_ids': ['not-a-valid-uuid'],
            },
            headers=HTML_HEADERS,
        )
        assert response.status_code == 302
        assert '/dashboard/manager' in response.location

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_no_valid_establishments_html(
        self, mock_auth_uow, mock_mgr_uow, client
    ):
        """No valid establishments with HTML form -> flash + redirect (lines 140-141)."""
        manager = MockUser(role='MANAGER')
        _setup_auth(client, manager, mock_auth_uow)

        mock_uow = MagicMock()
        mock_uow.establishments.get_by_id.return_value = None
        mock_mgr_uow.return_value = mock_uow

        response = client.post(
            '/manager/consultant/new',
            data={
                'name': 'Test',
                'email': 'test@test.com',
                'establishment_ids': [str(uuid.uuid4())],
            },
            headers=HTML_HEADERS,
        )
        assert response.status_code == 302
        assert '/dashboard/manager' in response.location

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_duplicate_email_html(
        self, mock_auth_uow, mock_mgr_uow, client
    ):
        """Duplicate email with HTML form -> flash + redirect (lines 147-148)."""
        manager = MockUser(role='MANAGER')
        _setup_auth(client, manager, mock_auth_uow)

        est_id = uuid.uuid4()
        mock_est = MagicMock()
        mock_est.id = est_id

        mock_uow = MagicMock()
        mock_uow.establishments.get_by_id.return_value = mock_est
        mock_uow.users.get_by_email.return_value = MagicMock()  # existing user
        mock_mgr_uow.return_value = mock_uow

        response = client.post(
            '/manager/consultant/new',
            data={
                'name': 'Dup',
                'email': 'existing@test.com',
                'establishment_ids': [str(est_id)],
            },
            headers=HTML_HEADERS,
        )
        assert response.status_code == 302
        assert '/dashboard/manager' in response.location

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_email_send_failure_still_succeeds(
        self, mock_auth_uow, mock_mgr_uow, client, app
    ):
        """Email send failure logs warning but consultant is still created (lines 166-167)."""
        manager = MockUser(role='MANAGER')
        _setup_auth(client, manager, mock_auth_uow)

        est_id = uuid.uuid4()
        mock_est = MagicMock()
        mock_est.id = est_id

        mock_uow = MagicMock()
        mock_uow.establishments.get_by_id.return_value = mock_est
        mock_uow.users.get_by_email.return_value = None
        mock_mgr_uow.return_value = mock_uow

        # Mock email service to raise
        mock_email = MagicMock()
        mock_email.send_welcome_email.side_effect = Exception("SMTP error")
        app.email_service = mock_email

        response = client.post(
            '/manager/consultant/new',
            data={
                'name': 'Email Fail',
                'email': 'fail@test.com',
                'establishment_ids': [str(est_id)],
            },
            headers=HTML_HEADERS,
        )
        # Should still redirect (success path with flash)
        assert response.status_code == 302
        assert '/dashboard/manager' in response.location
        mock_uow.commit.assert_called_once()

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_success_html_flash_redirect(
        self, mock_auth_uow, mock_mgr_uow, client, app
    ):
        """Successful creation with HTML form -> flash + redirect (line 182)."""
        manager = MockUser(role='MANAGER')
        _setup_auth(client, manager, mock_auth_uow)

        est_id = uuid.uuid4()
        mock_est = MagicMock()
        mock_est.id = est_id

        mock_uow = MagicMock()
        mock_uow.establishments.get_by_id.return_value = mock_est
        mock_uow.users.get_by_email.return_value = None
        mock_mgr_uow.return_value = mock_uow

        # Mock email service -- succeed
        mock_email = MagicMock()
        app.email_service = mock_email

        response = client.post(
            '/manager/consultant/new',
            data={
                'name': 'New Consultant',
                'email': 'new@test.com',
                'establishment_ids': [str(est_id)],
            },
            headers=HTML_HEADERS,
        )
        assert response.status_code == 302
        assert '/dashboard/manager' in response.location
        mock_uow.users.add.assert_called_once()
        mock_uow.commit.assert_called_once()

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_exception_html_flash_redirect(
        self, mock_auth_uow, mock_mgr_uow, client
    ):
        """Exception during creation with HTML form -> flash + redirect (lines 188-190)."""
        manager = MockUser(role='MANAGER')
        _setup_auth(client, manager, mock_auth_uow)

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
                'name': 'Fail',
                'email': 'fail@test.com',
                'establishment_ids': [str(est_id)],
            },
            headers=HTML_HEADERS,
        )
        assert response.status_code == 302
        assert '/dashboard/manager' in response.location
        mock_uow.rollback.assert_called_once()


# ===================================================================
#  UPDATE CONSULTANT -- EXTRA BRANCHES
# ===================================================================

class TestUpdateConsultantExtra:
    """Tests for update_consultant uncovered branches."""

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_update_with_password(
        self, mock_auth_uow, mock_mgr_uow, client
    ):
        """Update consultant with password field sets new hash (line 219)."""
        company_id = uuid.uuid4()
        manager = MockUser(role='MANAGER', company_id=company_id)
        _setup_auth(client, manager, mock_auth_uow)

        user_id = uuid.uuid4()
        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.role = 'CONSULTANT'
        mock_user.company_id = company_id
        mock_user.name = 'Old Name'
        mock_user.email = 'old@test.com'
        mock_user.establishments = []
        mock_user.password_hash = 'old_hash'

        mock_uow = MagicMock()
        mock_uow.users.get_by_id.return_value = mock_user
        mock_uow.users.get_by_email.return_value = None
        mock_mgr_uow.return_value = mock_uow

        response = client.post(
            f'/manager/consultant/{user_id}/update',
            data={
                'name': 'New Name',
                'email': 'new@test.com',
                'password': 'newpassword123',
            },
            headers={'Accept': 'application/json'},
        )
        assert response.status_code == 200
        # Verify password_hash was changed
        assert mock_user.password_hash != 'old_hash'

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_update_with_establishment_ids(
        self, mock_auth_uow, mock_mgr_uow, client
    ):
        """Update consultant with establishment_ids re-assigns establishments (lines 222-227)."""
        company_id = uuid.uuid4()
        manager = MockUser(role='MANAGER', company_id=company_id)
        _setup_auth(client, manager, mock_auth_uow)

        user_id = uuid.uuid4()
        est_id = uuid.uuid4()

        mock_est = MagicMock()
        mock_est.id = est_id
        mock_est.name = 'Loja 1'
        mock_est.company_id = company_id

        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.role = 'CONSULTANT'
        mock_user.company_id = company_id
        mock_user.name = 'Consultant'
        mock_user.email = 'c@test.com'
        mock_user.establishments = []

        mock_uow = MagicMock()
        mock_uow.users.get_by_id.return_value = mock_user
        mock_uow.users.get_by_email.return_value = None
        mock_uow.establishments.get_by_id.return_value = mock_est
        mock_mgr_uow.return_value = mock_uow

        response = client.post(
            f'/manager/consultant/{user_id}/update',
            data={
                'name': 'Consultant',
                'email': 'c@test.com',
                'establishment_ids': [str(est_id)],
            },
            headers={'Accept': 'application/json'},
        )
        assert response.status_code == 200
        # Establishments should have been reassigned
        assert mock_est in mock_user.establishments

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_update_with_establishment_wrong_company_filtered(
        self, mock_auth_uow, mock_mgr_uow, client
    ):
        """Update with establishment from wrong company is filtered out (line 225)."""
        company_id = uuid.uuid4()
        manager = MockUser(role='MANAGER', company_id=company_id)
        _setup_auth(client, manager, mock_auth_uow)

        user_id = uuid.uuid4()
        est_id = uuid.uuid4()

        mock_est = MagicMock()
        mock_est.id = est_id
        mock_est.company_id = uuid.uuid4()  # Different company

        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.role = 'CONSULTANT'
        mock_user.company_id = company_id
        mock_user.name = 'Consultant'
        mock_user.email = 'c@test.com'
        mock_user.establishments = []

        mock_uow = MagicMock()
        mock_uow.users.get_by_id.return_value = mock_user
        mock_uow.establishments.get_by_id.return_value = mock_est
        mock_mgr_uow.return_value = mock_uow

        response = client.post(
            f'/manager/consultant/{user_id}/update',
            data={
                'name': 'Consultant',
                'email': 'c@test.com',
                'establishment_ids': [str(est_id)],
            },
            headers={'Accept': 'application/json'},
        )
        assert response.status_code == 200
        # Establishment from wrong company should NOT be in the list
        assert mock_user.establishments == []

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_update_exception_returns_500(
        self, mock_auth_uow, mock_mgr_uow, client
    ):
        """Exception during update returns 500 and calls rollback (lines 242-244)."""
        company_id = uuid.uuid4()
        manager = MockUser(role='MANAGER', company_id=company_id)
        _setup_auth(client, manager, mock_auth_uow)

        user_id = uuid.uuid4()
        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.role = 'CONSULTANT'
        mock_user.company_id = company_id

        mock_uow = MagicMock()
        mock_uow.users.get_by_id.return_value = mock_user
        mock_uow.users.get_by_email.return_value = None
        # Simulate exception on commit
        mock_uow.commit.side_effect = Exception("DB constraint violation")
        mock_mgr_uow.return_value = mock_uow

        response = client.post(
            f'/manager/consultant/{user_id}/update',
            data={'name': 'Name', 'email': 'e@test.com'},
            headers={'Accept': 'application/json'},
        )
        assert response.status_code == 500
        data = response.get_json()
        assert 'error' in data
        mock_uow.rollback.assert_called_once()


# ===================================================================
#  _try_migrate_from_drive  (lines 533-590)
# ===================================================================

class TestTryMigrateFromDrive:
    """Tests for _try_migrate_from_drive called via edit_plan route."""

    @patch('src.manager_routes._try_migrate_from_drive')
    @patch('src.manager_routes.get_inspection_data_service')
    @patch('src.auth.get_uow')
    def test_edit_plan_calls_drive_migration_when_not_found(
        self, mock_auth_uow, mock_get_data_svc, mock_migrate, client
    ):
        """When get_plan_edit_data returns None, _try_migrate_from_drive is called."""
        manager = MockUser(role='MANAGER')
        _setup_auth(client, manager, mock_auth_uow)

        mock_svc = MagicMock()
        mock_svc.get_plan_edit_data.return_value = None
        mock_get_data_svc.return_value = mock_svc

        mock_migrate.return_value = None

        response = client.get('/manager/plan/legacy-file-id')
        assert response.status_code == 302
        mock_migrate.assert_called_once_with('legacy-file-id')

    @patch('src.manager_routes.render_template')
    @patch('src.manager_routes._try_migrate_from_drive')
    @patch('src.manager_routes.get_inspection_data_service')
    @patch('src.auth.get_uow')
    def test_edit_plan_uses_migrated_data(
        self, mock_auth_uow, mock_get_data_svc, mock_migrate, mock_render, client
    ):
        """When migration succeeds, the migrated data is used for rendering."""
        mock_render.return_value = 'rendered'
        manager = MockUser(role='MANAGER')
        _setup_auth(client, manager, mock_auth_uow)

        mock_svc = MagicMock()
        mock_svc.get_plan_edit_data.return_value = None
        mock_get_data_svc.return_value = mock_svc

        mock_est = MagicMock()
        mock_est.name = 'Migrated Est'
        mock_est.responsible_name = None
        mock_est.responsible_email = None
        mock_est.responsible_phone = None

        mock_inspection = MagicMock()
        mock_inspection.establishment = mock_est
        mock_inspection.created_at = datetime(2025, 3, 1)
        mock_inspection.ai_raw_response = {}
        mock_inspection.status.value = 'PENDING_MANAGER_REVIEW'

        mock_plan = MagicMock()
        mock_plan.summary_text = 'Migrated summary'

        mock_migrate.return_value = {
            'inspection': mock_inspection,
            'plan': mock_plan,
            'data': {'resumo_geral': 'Migrated'},
        }

        response = client.get('/manager/plan/migrated-file')
        assert response.status_code == 200
        mock_render.assert_called_once()

    def test_try_migrate_no_drive_service(self, app):
        """_try_migrate_from_drive returns None when no drive_service exists."""
        from src.manager_routes import _try_migrate_from_drive

        # Ensure drive_service is not set
        if hasattr(app, 'drive_service'):
            old = app.drive_service
            delattr(app, 'drive_service')
        else:
            old = None

        with app.app_context():
            result = _try_migrate_from_drive('some-file-id')
            assert result is None

        if old is not None:
            app.drive_service = old

    @patch('src.container.get_inspection_data_service')
    @patch('src.manager_routes.get_uow')
    def test_try_migrate_drive_read_succeeds(
        self, mock_uow_fn, mock_get_data_svc, app
    ):
        """_try_migrate_from_drive creates inspection from Drive JSON."""
        from src.manager_routes import _try_migrate_from_drive

        mock_drive = MagicMock()
        mock_drive.read_json.return_value = {
            'estabelecimento': 'Restaurant ABC',
            'nao_conformidades': [
                {'problema': 'Issue 1', 'acao_corretiva': 'Fix 1', 'gravidade': 'HIGH'},
                {'problema': 'Issue 2', 'acao_corretiva': 'Fix 2', 'gravidade': 'INVALID'},
            ],
        }

        mock_uow = MagicMock()
        mock_uow.session.query.return_value.filter_by.return_value.first.return_value = None
        mock_uow_fn.return_value = mock_uow

        mock_svc = MagicMock()
        mock_svc.get_plan_edit_data.return_value = {'inspection': MagicMock(), 'plan': MagicMock(), 'data': {}}
        mock_get_data_svc.return_value = mock_svc

        app.drive_service = mock_drive

        with app.app_context():
            result = _try_migrate_from_drive('drive-file-123')

        assert result is not None
        mock_uow.inspections.add.assert_called_once()
        mock_uow.commit.assert_called_once()
        # Two items should have been added
        assert mock_uow.action_plans.add_item.call_count == 2

    @patch('src.container.get_inspection_data_service')
    @patch('src.manager_routes.get_uow')
    def test_try_migrate_drive_read_returns_none(self, mock_uow_fn, mock_get_data_svc, app):
        """_try_migrate_from_drive handles None from drive.read_json (line 540)."""
        from src.manager_routes import _try_migrate_from_drive

        mock_drive = MagicMock()
        mock_drive.read_json.return_value = None

        mock_uow = MagicMock()
        mock_uow.session.query.return_value.filter_by.return_value.first.return_value = None
        mock_uow_fn.return_value = mock_uow

        mock_svc = MagicMock()
        mock_svc.get_plan_edit_data.return_value = {'inspection': MagicMock(), 'plan': MagicMock(), 'data': {}}
        mock_get_data_svc.return_value = mock_svc

        app.drive_service = mock_drive

        with app.app_context():
            result = _try_migrate_from_drive('null-file')

        assert result is not None
        mock_uow.inspections.add.assert_called_once()

    @patch('src.manager_routes.get_uow')
    def test_try_migrate_exception_returns_none(self, mock_uow_fn, app):
        """_try_migrate_from_drive catches exception and returns None (lines 588-590)."""
        from src.manager_routes import _try_migrate_from_drive

        mock_drive = MagicMock()
        mock_drive.read_json.side_effect = Exception("Drive API error")

        app.drive_service = mock_drive

        with app.app_context():
            result = _try_migrate_from_drive('error-file')

        assert result is None


# ===================================================================
#  APPROVE PLAN -- ERROR HANDLING
# ===================================================================

class TestApprovePlanErrors:
    """Tests for approve_plan error handling branches."""

    @patch('src.manager_routes.get_plan_service')
    @patch('src.auth.get_uow')
    def test_approve_plan_not_found_returns_404(
        self, mock_auth_uow, mock_get_plan_svc, client
    ):
        """Approve plan with not found result returns 404 (lines 663-664)."""
        manager = MockUser(role='MANAGER')
        _setup_auth(client, manager, mock_auth_uow)

        mock_svc = MagicMock()
        mock_svc.approve_plan.return_value = PlanResult(
            success=False,
            message='Plano nao encontrado.',
            error='NOT_FOUND',
        )
        mock_get_plan_svc.return_value = mock_svc

        response = client.post(
            '/manager/plan/nonexistent/approve',
            headers={'Accept': 'application/json'},
        )
        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data
        assert 'encontrado' in data['error']

    @patch('src.manager_routes.get_plan_service')
    @patch('src.auth.get_uow')
    def test_approve_plan_success_returns_200(
        self, mock_auth_uow, mock_get_plan_svc, client
    ):
        """Approve plan success returns 200 with message."""
        manager = MockUser(role='ADMIN')
        _setup_auth(client, manager, mock_auth_uow)

        mock_svc = MagicMock()
        mock_svc.approve_plan.return_value = PlanResult(
            success=True,
            message='Plano aprovado com sucesso!',
        )
        mock_get_plan_svc.return_value = mock_svc

        response = client.post(
            '/manager/plan/approved-file/approve',
            headers={'Accept': 'application/json'},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['message'] == 'Plano aprovado com sucesso!'


# ===================================================================
#  API STATUS -- EXTRA BRANCHES
# ===================================================================

class TestApiStatusExtra:
    """Extra tests for api_status branches."""

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_api_status_invalid_establishment_uuid(
        self, mock_auth_uow, mock_mgr_uow, client
    ):
        """Invalid UUID for establishment_id param is handled gracefully (lines 663-664)."""
        manager = MockUser(role='MANAGER')
        _setup_auth(client, manager, mock_auth_uow)

        mock_uow = MagicMock()
        mock_uow.inspections.get_for_manager.return_value = []
        mock_uow.establishments.get_by_company.return_value = []
        mock_uow.jobs.get_pending_for_company.return_value = []
        mock_mgr_uow.return_value = mock_uow

        response = client.get('/api/status?establishment_id=not-a-uuid')
        assert response.status_code == 200
        # The invalid UUID should be caught and est_id_filter remains None
        call_kwargs = mock_uow.inspections.get_for_manager.call_args
        assert call_kwargs[1]['establishment_id'] is None

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_api_status_with_failed_job(
        self, mock_auth_uow, mock_mgr_uow, client
    ):
        """API status includes failed jobs in pending list."""
        from src.models_db import JobStatus

        company_id = uuid.uuid4()
        manager = MockUser(role='MANAGER', company_id=company_id)
        _setup_auth(client, manager, mock_auth_uow)

        mock_est = MagicMock()
        mock_est.id = uuid.uuid4()

        mock_job = MagicMock()
        mock_job.status = JobStatus.FAILED
        mock_job.input_payload = {'filename': 'bad_report.pdf'}
        mock_job.error_log = 'Processing failed: out of memory'

        mock_uow = MagicMock()
        mock_uow.inspections.get_for_manager.return_value = []
        mock_uow.establishments.get_by_company.return_value = [mock_est]
        mock_uow.jobs.get_pending_for_company.return_value = [mock_job]
        mock_mgr_uow.return_value = mock_uow

        response = client.get('/api/status')
        assert response.status_code == 200
        data = response.get_json()
        assert len(data['pending']) == 1
        assert data['pending'][0]['error'] is True
        assert 'out of memory' in data['pending'][0]['message']

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_api_status_job_filtered_by_establishment(
        self, mock_auth_uow, mock_mgr_uow, client
    ):
        """Jobs are filtered by establishment_id when specified."""
        company_id = uuid.uuid4()
        est_id = uuid.uuid4()
        manager = MockUser(role='MANAGER', company_id=company_id)
        _setup_auth(client, manager, mock_auth_uow)

        mock_est = MagicMock()
        mock_est.id = est_id

        mock_job = MagicMock()
        mock_job.status = MagicMock()
        mock_job.status.value = 'PENDING'
        mock_job.status.__eq__ = lambda s, o: False
        mock_job.input_payload = {
            'filename': 'report.pdf',
            'establishment_id': str(uuid.uuid4()),  # Different est
        }

        mock_uow = MagicMock()
        mock_uow.inspections.get_for_manager.return_value = []
        mock_uow.establishments.get_by_company.return_value = [mock_est]
        mock_uow.jobs.get_pending_for_company.return_value = [mock_job]
        mock_mgr_uow.return_value = mock_uow

        response = client.get(f'/api/status?establishment_id={est_id}')
        assert response.status_code == 200
        data = response.get_json()
        # Job should be filtered out because its establishment doesn't match
        assert len(data['pending']) == 0

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_api_status_no_company_id(
        self, mock_auth_uow, mock_mgr_uow, client
    ):
        """API status with no company_id skips pending jobs."""
        manager = MockUser(role='MANAGER', company_id=None)
        _setup_auth(client, manager, mock_auth_uow)

        mock_uow = MagicMock()
        mock_uow.inspections.get_for_manager.return_value = []
        mock_mgr_uow.return_value = mock_uow

        response = client.get('/api/status')
        assert response.status_code == 200
        data = response.get_json()
        assert data['pending'] == []

    @patch('src.manager_routes.get_uow')
    @patch('src.auth.get_uow')
    def test_api_status_inspection_no_drive_file_id(
        self, mock_auth_uow, mock_mgr_uow, client
    ):
        """Inspection without drive_file_id shows '#' as review_link."""
        company_id = uuid.uuid4()
        manager = MockUser(role='MANAGER', company_id=company_id)
        _setup_auth(client, manager, mock_auth_uow)

        mock_est = MagicMock()
        mock_est.name = 'Est X'

        mock_insp = MagicMock()
        mock_insp.id = uuid.uuid4()
        mock_insp.establishment = mock_est
        mock_insp.created_at = datetime(2025, 1, 1)
        mock_insp.status = MagicMock()
        mock_insp.status.value = 'APPROVED'
        mock_insp.status.__eq__ = lambda s, o: False
        mock_insp.drive_file_id = None

        mock_uow = MagicMock()
        mock_uow.inspections.get_for_manager.return_value = [mock_insp]
        mock_uow.establishments.get_by_company.return_value = []
        mock_uow.jobs.get_pending_for_company.return_value = []
        mock_uow.jobs.get_job_info_map.return_value = {}
        mock_mgr_uow.return_value = mock_uow

        response = client.get('/api/status')
        assert response.status_code == 200
        data = response.get_json()
        assert data['processed_raw'][0]['review_link'] == '#'


# ===================================================================
#  PATCHER TESTS  (src/patcher.py)
# ===================================================================

class TestPatcher:
    """Tests for run_auto_patch in src/patcher.py."""

    @patch('src.patcher.engine')
    def test_run_auto_patch_success(self, mock_engine, app):
        """All patches execute successfully (lines 64-73)."""
        from src.patcher import run_auto_patch

        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        with app.app_context():
            run_auto_patch()

        # Verify execute was called for each SQL patch
        assert mock_conn.execute.call_count >= 1
        mock_conn.commit.assert_called_once()

    @patch('src.patcher.engine')
    def test_run_auto_patch_connection_error(self, mock_engine, app, caplog):
        """Connection error is caught and logged (lines 74-75)."""
        from src.patcher import run_auto_patch

        mock_engine.connect.side_effect = Exception("Connection refused")

        with app.app_context():
            with caplog.at_level(logging.ERROR):
                run_auto_patch()

        assert any('Connection refused' in r.message for r in caplog.records)

    @patch('src.patcher.engine')
    def test_run_auto_patch_individual_patch_fails(self, mock_engine, app, caplog):
        """Individual SQL failure logs warning but continues (lines 69-71)."""
        from src.patcher import run_auto_patch

        mock_conn = MagicMock()
        # First call succeeds, second fails, rest succeed
        call_count = [0]
        def execute_side_effect(sql):
            call_count[0] += 1
            if call_count[0] == 2:
                raise Exception("column already exists")

        mock_conn.execute.side_effect = execute_side_effect
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        with app.app_context():
            with caplog.at_level(logging.WARNING):
                run_auto_patch()

        # Should have logged a warning for the failing patch
        assert any('column already exists' in r.message for r in caplog.records)
        # Commit should still be called
        mock_conn.commit.assert_called_once()

    @patch('src.patcher.engine')
    def test_run_auto_patch_sa_email_detected_via_google_auth(
        self, mock_engine, app, caplog
    ):
        """Service account email detected via google.auth (lines 20-24)."""
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        mock_creds = MagicMock()
        mock_creds.service_account_email = 'test@project.iam.gserviceaccount.com'

        mock_google_auth = MagicMock()
        mock_google_auth.default.return_value = (mock_creds, 'project-id')

        # Patch sys.modules so `import google.auth` inside run_auto_patch finds our mock
        mock_google = MagicMock()
        mock_google.auth = mock_google_auth
        with patch.dict('sys.modules', {'google': mock_google, 'google.auth': mock_google_auth}):
            import importlib
            import src.patcher
            importlib.reload(src.patcher)
            src.patcher.engine = mock_engine
            with app.app_context():
                with caplog.at_level(logging.INFO):
                    src.patcher.run_auto_patch()

            assert any('test@project.iam.gserviceaccount.com' in r.message for r in caplog.records)
            # Reload again to restore original state
            importlib.reload(src.patcher)

    @patch('requests.get')
    @patch('src.patcher.engine')
    def test_run_auto_patch_metadata_server_fallback(
        self, mock_engine, mock_requests_get, app, caplog
    ):
        """SA email from metadata server when google.auth not available (lines 29-34)."""
        from src.patcher import run_auto_patch

        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '  svc@project.iam.gserviceaccount.com  '
        mock_requests_get.return_value = mock_resp

        # Make google.auth import fail
        original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

        def mock_import(name, *args, **kwargs):
            if name == 'google.auth':
                raise ImportError("No module named google.auth")
            return original_import(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=mock_import):
            with app.app_context():
                with caplog.at_level(logging.INFO):
                    import importlib
                    import src.patcher
                    importlib.reload(src.patcher)
                    src.patcher.engine = mock_engine
                    src.patcher.run_auto_patch()

        assert any('svc@project.iam.gserviceaccount.com' in r.message for r in caplog.records)

    @patch('src.patcher.engine')
    def test_run_auto_patch_no_sa_email_detected(self, mock_engine, app, caplog):
        """When neither google.auth nor metadata server work, logs info (lines 39-40)."""
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        # Make both detection methods fail
        original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

        def mock_import(name, *args, **kwargs):
            if name == 'google.auth':
                raise ImportError("No module named google.auth")
            if name == 'requests':
                raise ImportError("No module named requests")
            return original_import(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=mock_import):
            with app.app_context():
                with caplog.at_level(logging.INFO):
                    import importlib
                    import src.patcher
                    importlib.reload(src.patcher)
                    src.patcher.engine = mock_engine
                    src.patcher.run_auto_patch()

        assert any('detectar email' in r.message for r in caplog.records)

    @patch('src.patcher.engine')
    def test_run_auto_patch_sa_email_line_37(self, mock_engine, app, caplog):
        """When sa_email is found, it is logged (line 37-38)."""
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        mock_creds = MagicMock()
        mock_creds.service_account_email = 'auto@project.iam.gserviceaccount.com'

        mock_google_auth = MagicMock()
        mock_google_auth.default.return_value = (mock_creds, 'project')

        mock_google = MagicMock()
        mock_google.auth = mock_google_auth
        with patch.dict('sys.modules', {'google': mock_google, 'google.auth': mock_google_auth}):
            import importlib
            import src.patcher
            importlib.reload(src.patcher)
            src.patcher.engine = mock_engine
            with app.app_context():
                with caplog.at_level(logging.INFO):
                    src.patcher.run_auto_patch()

            # Verify the SHARE DRIVE log message appears
            assert any('SERVICE ACCOUNT EMAIL' in r.message for r in caplog.records)
            importlib.reload(src.patcher)


# ===================================================================
#  EDIT PLAN -- EXTRA BRANCHES
# ===================================================================

class TestEditPlanExtra:
    """Extra tests for edit_plan to cover remaining branches."""

    @patch('src.auth.get_uow')
    def test_edit_plan_non_authorized_role_redirected(self, mock_auth_uow, client):
        """User with invalid role is redirected from edit_plan."""
        user = MockUser(role='OTHER')
        _setup_auth(client, user, mock_auth_uow)

        response = client.get('/manager/plan/some-file')
        assert response.status_code == 302

    @patch('src.manager_routes.render_template')
    @patch('src.manager_routes.get_inspection_data_service')
    @patch('src.auth.get_uow')
    def test_edit_plan_consultant_allowed(
        self, mock_auth_uow, mock_get_data_svc, mock_render, client
    ):
        """Consultant can access edit_plan."""
        mock_render.return_value = 'rendered'
        consultant = MockUser(role='CONSULTANT')
        _setup_auth(client, consultant, mock_auth_uow)

        mock_est = MagicMock()
        mock_est.name = 'Test'
        mock_est.responsible_name = None
        mock_est.responsible_email = None
        mock_est.responsible_phone = None

        mock_inspection = MagicMock()
        mock_inspection.establishment = mock_est
        mock_inspection.created_at = datetime(2025, 6, 1)
        mock_inspection.ai_raw_response = {}
        mock_inspection.status.value = 'APPROVED'

        mock_plan = MagicMock()
        mock_plan.summary_text = 'Summary'

        mock_svc = MagicMock()
        mock_svc.get_plan_edit_data.return_value = {
            'inspection': mock_inspection,
            'plan': mock_plan,
            'data': {'resumo_geral': 'Test'},
        }
        mock_get_data_svc.return_value = mock_svc

        response = client.get('/manager/plan/consultant-file')
        assert response.status_code == 200

    @patch('src.manager_routes.render_template')
    @patch('src.manager_routes.get_inspection_data_service')
    @patch('src.auth.get_uow')
    def test_edit_plan_locked_when_approved(
        self, mock_auth_uow, mock_get_data_svc, mock_render, client
    ):
        """Plan with APPROVED status shows is_locked=True."""
        mock_render.return_value = 'rendered'
        manager = MockUser(role='MANAGER')
        _setup_auth(client, manager, mock_auth_uow)

        mock_est = MagicMock()
        mock_est.name = 'Locked Est'
        mock_est.responsible_name = None
        mock_est.responsible_email = None
        mock_est.responsible_phone = None

        mock_inspection = MagicMock()
        mock_inspection.establishment = mock_est
        mock_inspection.created_at = datetime(2025, 6, 1)
        mock_inspection.ai_raw_response = {}
        mock_inspection.status.value = 'APPROVED'

        mock_plan = MagicMock()
        mock_plan.summary_text = 'Approved plan'

        mock_svc = MagicMock()
        mock_svc.get_plan_edit_data.return_value = {
            'inspection': mock_inspection,
            'plan': mock_plan,
            'data': {'resumo_geral': 'Test'},
        }
        mock_get_data_svc.return_value = mock_svc

        response = client.get('/manager/plan/approved-plan')
        assert response.status_code == 200
        call_kwargs = mock_render.call_args[1]
        assert call_kwargs['is_locked'] is True
        assert call_kwargs['is_approved'] is True

    @patch('src.manager_routes.render_template')
    @patch('src.manager_routes.get_inspection_data_service')
    @patch('src.auth.get_uow')
    def test_edit_plan_no_establishment(
        self, mock_auth_uow, mock_get_data_svc, mock_render, client
    ):
        """Plan with no establishment uses fallback name."""
        mock_render.return_value = 'rendered'
        manager = MockUser(role='MANAGER')
        _setup_auth(client, manager, mock_auth_uow)

        mock_inspection = MagicMock()
        mock_inspection.establishment = None
        mock_inspection.created_at = None
        mock_inspection.ai_raw_response = {'summary_text': 'Fallback summary'}
        mock_inspection.status.value = 'PENDING_MANAGER_REVIEW'

        mock_plan = MagicMock()
        mock_plan.summary_text = None

        mock_svc = MagicMock()
        mock_svc.get_plan_edit_data.return_value = {
            'inspection': mock_inspection,
            'plan': mock_plan,
            'data': {},
        }
        mock_get_data_svc.return_value = mock_svc

        response = client.get('/manager/plan/no-est-file')
        assert response.status_code == 200
        call_kwargs = mock_render.call_args[1]
        rd = call_kwargs['report_data']
        assert rd['nome_estabelecimento'] == 'Estabelecimento'
        assert rd['data_inspecao'] == ''
