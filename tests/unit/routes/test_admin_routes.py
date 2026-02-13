"""Unit tests for admin routes.

Tests cover:
- Access control (non-admin redirect, unauthenticated redirect)
- Admin index (GET /admin/)
- Company CRUD (create, update, delete)
- Establishment creation
- Manager CRUD (create, update, delete)
- API monitor stats (GET /admin/api/monitor)
- Tracker details (GET /admin/api/tracker/<uuid>)
- Settings GET/POST (GET/POST /admin/api/settings)
"""

import pytest
import uuid
import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from dataclasses import dataclass
from typing import Optional
from werkzeug.security import generate_password_hash


# ---------------------------------------------------------------------------
# AdminResult dataclass (mirroring the real one from admin_service)
# ---------------------------------------------------------------------------

@dataclass
class AdminResult:
    success: bool
    message: str
    data: Optional[dict] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# MockUser for Flask-Login
# ---------------------------------------------------------------------------

class MockUser:
    """Mock user that satisfies Flask-Login requirements."""

    def __init__(self, **kwargs):
        self.id = kwargs.get('id', uuid.uuid4())
        self.email = kwargs.get('email', 'admin@test.com')
        self.name = kwargs.get('name', 'Admin')
        self.role = kwargs.get('role', 'ADMIN')
        self.password_hash = generate_password_hash('admin123')
        self.is_active = True
        self.is_authenticated = True
        self.must_change_password = False
        self.company_id = kwargs.get('company_id', None)

    def get_id(self):
        return str(self.id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _setup_admin_session(client, admin_user, mock_auth_uow):
    """Configure mock auth UoW and set the admin user in the session."""
    auth_uow = MagicMock()
    auth_uow.users.get_by_id.return_value = admin_user
    mock_auth_uow.return_value = auth_uow

    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_user.id)

    return auth_uow


JSON_HEADERS = {'Accept': 'application/json'}


# ===================================================================
#  ACCESS CONTROL
# ===================================================================

class TestAdminAccessControl:
    """Tests for admin route access restrictions."""

    def test_unauthenticated_user_redirected(self, client):
        """Unauthenticated user accessing /admin/ is redirected to login."""
        response = client.get('/admin/')
        assert response.status_code == 302
        assert 'login' in response.location

    @patch('src.container.get_uow')
    @patch('src.auth.get_uow')
    def test_non_admin_user_redirected(self, mock_auth_uow, mock_container_uow, client):
        """Non-admin user accessing /admin/ is redirected to manager dashboard."""
        manager = MockUser(role='MANAGER')
        _setup_admin_session(client, manager, mock_auth_uow)
        mock_container_uow.return_value = MagicMock()

        response = client.get('/admin/')
        assert response.status_code == 302
        assert '/dashboard/manager' in response.location


# ===================================================================
#  ADMIN INDEX
# ===================================================================

class TestAdminIndex:
    """Tests for GET /admin/."""

    @patch('src.container.get_uow')
    @patch('src.auth.get_uow')
    def test_index_success(self, mock_auth_uow, mock_container_uow, client):
        """Admin can access the index page and get 200."""
        admin = MockUser(role='ADMIN')
        _setup_admin_session(client, admin, mock_auth_uow)

        mock_uow = MagicMock()
        mock_uow.companies.get_all.return_value = []
        managers_list = []
        mock_uow.users.get_managers_with_company.return_value = managers_list
        mock_container_uow.return_value = mock_uow

        response = client.get('/admin/')
        assert response.status_code == 200

    @patch('src.container.get_uow')
    @patch('src.auth.get_uow')
    def test_index_exception_returns_500(self, mock_auth_uow, mock_container_uow, client):
        """Exception in index route returns 500."""
        admin = MockUser(role='ADMIN')
        _setup_admin_session(client, admin, mock_auth_uow)

        mock_uow = MagicMock()
        mock_uow.companies.get_all.side_effect = Exception("DB down")
        mock_container_uow.return_value = mock_uow

        response = client.get('/admin/')
        assert response.status_code == 500


# ===================================================================
#  CREATE COMPANY
# ===================================================================

class TestCreateCompany:
    """Tests for POST /admin/company/new."""

    @patch('src.container.get_admin_service')
    @patch('src.auth.get_uow')
    def test_create_company_success(self, mock_auth_uow, mock_get_svc, client):
        """Successful company creation returns 201 with JSON."""
        admin = MockUser(role='ADMIN')
        _setup_admin_session(client, admin, mock_auth_uow)

        mock_svc = MagicMock()
        mock_svc.create_company.return_value = AdminResult(
            success=True,
            message='Empresa criada!',
            data={'id': str(uuid.uuid4()), 'name': 'Corp'},
        )
        mock_get_svc.return_value = mock_svc

        response = client.post(
            '/admin/company/new',
            data={'name': 'Corp', 'cnpj': '12345678000199'},
            headers=JSON_HEADERS,
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data['success'] is True
        assert 'company' in data

    @patch('src.container.get_admin_service')
    @patch('src.auth.get_uow')
    def test_create_company_failure(self, mock_auth_uow, mock_get_svc, client):
        """Failed company creation returns 400 with error."""
        admin = MockUser(role='ADMIN')
        _setup_admin_session(client, admin, mock_auth_uow)

        mock_svc = MagicMock()
        mock_svc.create_company.return_value = AdminResult(
            success=False,
            message='CNPJ duplicado.',
        )
        mock_get_svc.return_value = mock_svc

        response = client.post(
            '/admin/company/new',
            data={'name': 'Corp', 'cnpj': 'dup'},
            headers=JSON_HEADERS,
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data


# ===================================================================
#  DELETE COMPANY
# ===================================================================

class TestDeleteCompany:
    """Tests for POST /admin/company/<uuid>/delete."""

    @patch('src.container.get_admin_service')
    @patch('src.auth.get_uow')
    def test_delete_company_success(self, mock_auth_uow, mock_get_svc, client):
        """Successful company deletion returns 200."""
        admin = MockUser(role='ADMIN')
        _setup_admin_session(client, admin, mock_auth_uow)

        mock_svc = MagicMock()
        mock_svc.delete_company.return_value = AdminResult(
            success=True,
            message='Empresa removida!',
        )
        mock_get_svc.return_value = mock_svc

        cid = uuid.uuid4()
        response = client.post(
            f'/admin/company/{cid}/delete',
            headers=JSON_HEADERS,
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

    @patch('src.container.get_admin_service')
    @patch('src.auth.get_uow')
    def test_delete_company_not_found(self, mock_auth_uow, mock_get_svc, client):
        """Deleting a non-existent company returns 404."""
        admin = MockUser(role='ADMIN')
        _setup_admin_session(client, admin, mock_auth_uow)

        mock_svc = MagicMock()
        mock_svc.delete_company.return_value = AdminResult(
            success=False,
            message='Empresa nao encontrada.',
            error='NOT_FOUND',
        )
        mock_get_svc.return_value = mock_svc

        cid = uuid.uuid4()
        response = client.post(
            f'/admin/company/{cid}/delete',
            headers=JSON_HEADERS,
        )
        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data


# ===================================================================
#  CREATE ESTABLISHMENT
# ===================================================================

class TestCreateEstablishment:
    """Tests for POST /admin/establishment/new."""

    @patch('src.container.get_uow')
    @patch('src.auth.get_uow')
    def test_create_establishment_success(self, mock_auth_uow, mock_container_uow, client):
        """Successful establishment creation returns 201."""
        admin = MockUser(role='ADMIN')
        _setup_admin_session(client, admin, mock_auth_uow)

        mock_uow = MagicMock()
        mock_container_uow.return_value = mock_uow

        cid = uuid.uuid4()
        response = client.post(
            '/admin/establishment/new',
            data={'company_id': str(cid), 'name': 'Restaurante X', 'drive_folder_id': ''},
            headers=JSON_HEADERS,
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data['success'] is True
        assert 'establishment' in data
        mock_uow.establishments.add.assert_called_once()
        mock_uow.commit.assert_called_once()

    @patch('src.container.get_uow')
    @patch('src.auth.get_uow')
    def test_create_establishment_missing_fields_redirects(self, mock_auth_uow, mock_container_uow, client):
        """Missing required fields redirects (no JSON response since redirect happens before UoW)."""
        admin = MockUser(role='ADMIN')
        _setup_admin_session(client, admin, mock_auth_uow)
        mock_container_uow.return_value = MagicMock()

        response = client.post(
            '/admin/establishment/new',
            data={'company_id': '', 'name': ''},
        )
        # Missing fields cause a redirect before JSON check
        assert response.status_code == 302

    @patch('src.container.get_uow')
    @patch('src.auth.get_uow')
    def test_create_establishment_exception(self, mock_auth_uow, mock_container_uow, client):
        """Exception during establishment creation returns 500 JSON."""
        admin = MockUser(role='ADMIN')
        _setup_admin_session(client, admin, mock_auth_uow)

        mock_uow = MagicMock()
        mock_uow.establishments.add.side_effect = Exception("DB constraint error")
        mock_container_uow.return_value = mock_uow

        cid = uuid.uuid4()
        response = client.post(
            '/admin/establishment/new',
            data={'company_id': str(cid), 'name': 'Bad Est'},
            headers=JSON_HEADERS,
        )
        assert response.status_code == 500
        data = response.get_json()
        assert 'error' in data
        mock_uow.rollback.assert_called_once()


# ===================================================================
#  CREATE MANAGER
# ===================================================================

class TestCreateManager:
    """Tests for POST /admin/manager/new."""

    @patch('src.container.get_admin_service')
    @patch('src.auth.get_uow')
    def test_create_manager_success(self, mock_auth_uow, mock_get_svc, client):
        """Successful manager creation returns 201 with manager data."""
        admin = MockUser(role='ADMIN')
        _setup_admin_session(client, admin, mock_auth_uow)

        mgr_id = str(uuid.uuid4())
        mock_svc = MagicMock()
        mock_svc.create_manager.return_value = AdminResult(
            success=True,
            message='Gestor criado!',
            data={'id': mgr_id, 'name': 'New Manager', 'email': 'mgr@test.com'},
        )
        mock_get_svc.return_value = mock_svc

        response = client.post(
            '/admin/manager/new',
            data={
                'name': 'New Manager',
                'email': 'mgr@test.com',
                'company_id': str(uuid.uuid4()),
                'password': 'secret123',
            },
            headers=JSON_HEADERS,
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data['success'] is True
        assert data['manager']['email'] == 'mgr@test.com'

    @patch('src.container.get_admin_service')
    @patch('src.auth.get_uow')
    def test_create_manager_failure(self, mock_auth_uow, mock_get_svc, client):
        """Failed manager creation returns 400."""
        admin = MockUser(role='ADMIN')
        _setup_admin_session(client, admin, mock_auth_uow)

        mock_svc = MagicMock()
        mock_svc.create_manager.return_value = AdminResult(
            success=False,
            message='Email ja cadastrado.',
        )
        mock_get_svc.return_value = mock_svc

        response = client.post(
            '/admin/manager/new',
            data={
                'name': 'Dup Manager',
                'email': 'dup@test.com',
                'company_id': str(uuid.uuid4()),
            },
            headers=JSON_HEADERS,
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data


# ===================================================================
#  DELETE MANAGER
# ===================================================================

class TestDeleteManager:
    """Tests for POST /admin/manager/<uuid>/delete."""

    @patch('src.container.get_admin_service')
    @patch('src.auth.get_uow')
    def test_delete_manager_success(self, mock_auth_uow, mock_get_svc, client):
        """Successful manager deletion returns 200."""
        admin = MockUser(role='ADMIN')
        _setup_admin_session(client, admin, mock_auth_uow)

        mock_svc = MagicMock()
        mock_svc.delete_manager.return_value = AdminResult(
            success=True,
            message='Gestor removido!',
        )
        mock_get_svc.return_value = mock_svc

        uid = uuid.uuid4()
        response = client.post(
            f'/admin/manager/{uid}/delete',
            headers=JSON_HEADERS,
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

    @patch('src.container.get_admin_service')
    @patch('src.auth.get_uow')
    def test_delete_manager_not_found(self, mock_auth_uow, mock_get_svc, client):
        """Deleting a non-existent manager returns 404."""
        admin = MockUser(role='ADMIN')
        _setup_admin_session(client, admin, mock_auth_uow)

        mock_svc = MagicMock()
        mock_svc.delete_manager.return_value = AdminResult(
            success=False,
            message='Gestor nao encontrado.',
            error='NOT_FOUND',
        )
        mock_get_svc.return_value = mock_svc

        uid = uuid.uuid4()
        response = client.post(
            f'/admin/manager/{uid}/delete',
            headers=JSON_HEADERS,
        )
        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data


# ===================================================================
#  UPDATE COMPANY
# ===================================================================

class TestUpdateCompany:
    """Tests for POST /admin/company/<uuid>/update."""

    @patch('src.container.get_uow')
    @patch('src.auth.get_uow')
    def test_update_company_success(self, mock_auth_uow, mock_container_uow, client):
        """Successful company update returns 200."""
        admin = MockUser(role='ADMIN')
        _setup_admin_session(client, admin, mock_auth_uow)

        mock_company = MagicMock()
        mock_company.cnpj = '11111111000100'
        mock_uow = MagicMock()
        mock_uow.companies.get_by_id.return_value = mock_company
        mock_uow.companies.get_by_cnpj.return_value = None
        mock_container_uow.return_value = mock_uow

        cid = uuid.uuid4()
        response = client.post(
            f'/admin/company/{cid}/update',
            data={'name': 'Updated Corp', 'cnpj': '99999999000100'},
            headers=JSON_HEADERS,
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert mock_company.name == 'Updated Corp'
        assert mock_company.cnpj == '99999999000100'
        mock_uow.commit.assert_called_once()

    @patch('src.container.get_uow')
    @patch('src.auth.get_uow')
    def test_update_company_duplicate_cnpj(self, mock_auth_uow, mock_container_uow, client):
        """Updating company with CNPJ already used by another returns 400."""
        admin = MockUser(role='ADMIN')
        _setup_admin_session(client, admin, mock_auth_uow)

        cid = uuid.uuid4()
        other_id = uuid.uuid4()
        mock_company = MagicMock()
        mock_company.id = cid
        mock_company.cnpj = '11111111000100'

        mock_existing = MagicMock()
        mock_existing.id = other_id

        mock_uow = MagicMock()
        mock_uow.companies.get_by_id.return_value = mock_company
        mock_uow.companies.get_by_cnpj.return_value = mock_existing
        mock_container_uow.return_value = mock_uow

        response = client.post(
            f'/admin/company/{cid}/update',
            data={'name': 'My Corp', 'cnpj': '99999999000100'},
            headers=JSON_HEADERS,
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'CNPJ' in data['error']

    @patch('src.container.get_uow')
    @patch('src.auth.get_uow')
    def test_update_company_missing_name(self, mock_auth_uow, mock_container_uow, client):
        """Updating company without name returns 400."""
        admin = MockUser(role='ADMIN')
        _setup_admin_session(client, admin, mock_auth_uow)
        mock_container_uow.return_value = MagicMock()

        cid = uuid.uuid4()
        response = client.post(
            f'/admin/company/{cid}/update',
            data={'name': '', 'cnpj': '123'},
            headers=JSON_HEADERS,
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    @patch('src.container.get_uow')
    @patch('src.auth.get_uow')
    def test_update_company_not_found(self, mock_auth_uow, mock_container_uow, client):
        """Updating a non-existent company returns 404."""
        admin = MockUser(role='ADMIN')
        _setup_admin_session(client, admin, mock_auth_uow)

        mock_uow = MagicMock()
        mock_uow.companies.get_by_id.return_value = None
        mock_container_uow.return_value = mock_uow

        cid = uuid.uuid4()
        response = client.post(
            f'/admin/company/{cid}/update',
            data={'name': 'Ghost Corp', 'cnpj': '000'},
            headers=JSON_HEADERS,
        )
        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data

    @patch('src.container.get_uow')
    @patch('src.auth.get_uow')
    def test_update_company_exception(self, mock_auth_uow, mock_container_uow, client):
        """Exception during update returns 500."""
        admin = MockUser(role='ADMIN')
        _setup_admin_session(client, admin, mock_auth_uow)

        mock_uow = MagicMock()
        mock_uow.companies.get_by_id.side_effect = Exception("DB error")
        mock_container_uow.return_value = mock_uow

        cid = uuid.uuid4()
        response = client.post(
            f'/admin/company/{cid}/update',
            data={'name': 'Fail Corp', 'cnpj': '000'},
            headers=JSON_HEADERS,
        )
        assert response.status_code == 500
        data = response.get_json()
        assert 'error' in data
        mock_uow.rollback.assert_called_once()


# ===================================================================
#  UPDATE MANAGER
# ===================================================================

class TestUpdateManager:
    """Tests for POST /admin/manager/<uuid>/update."""

    @patch('src.container.get_admin_service')
    @patch('src.auth.get_uow')
    def test_update_manager_success(self, mock_auth_uow, mock_get_svc, client):
        """Successful manager update returns 200."""
        admin = MockUser(role='ADMIN')
        _setup_admin_session(client, admin, mock_auth_uow)

        mock_svc = MagicMock()
        mock_svc.update_manager.return_value = AdminResult(
            success=True,
            message='Gestor atualizado!',
        )
        mock_get_svc.return_value = mock_svc

        uid = uuid.uuid4()
        response = client.post(
            f'/admin/manager/{uid}/update',
            data={
                'name': 'Updated Manager',
                'email': 'updated@test.com',
                'company_id': str(uuid.uuid4()),
                'password': '',
            },
            headers=JSON_HEADERS,
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

    @patch('src.container.get_admin_service')
    @patch('src.auth.get_uow')
    def test_update_manager_missing_required_fields(self, mock_auth_uow, mock_get_svc, client):
        """Missing name or email returns 400."""
        admin = MockUser(role='ADMIN')
        _setup_admin_session(client, admin, mock_auth_uow)
        mock_get_svc.return_value = MagicMock()

        uid = uuid.uuid4()
        response = client.post(
            f'/admin/manager/{uid}/update',
            data={'name': '', 'email': ''},
            headers=JSON_HEADERS,
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    @patch('src.container.get_admin_service')
    @patch('src.auth.get_uow')
    def test_update_manager_not_found(self, mock_auth_uow, mock_get_svc, client):
        """Updating a non-existent manager returns 404."""
        admin = MockUser(role='ADMIN')
        _setup_admin_session(client, admin, mock_auth_uow)

        mock_svc = MagicMock()
        mock_svc.update_manager.return_value = AdminResult(
            success=False,
            message='Gestor nao encontrado.',
            error='NOT_FOUND',
        )
        mock_get_svc.return_value = mock_svc

        uid = uuid.uuid4()
        response = client.post(
            f'/admin/manager/{uid}/update',
            data={'name': 'Ghost', 'email': 'ghost@test.com'},
            headers=JSON_HEADERS,
        )
        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data


# ===================================================================
#  API MONITOR STATS
# ===================================================================

class TestApiMonitorStats:
    """Tests for GET /admin/api/monitor."""

    @patch('src.container.get_uow')
    @patch('src.auth.get_uow')
    def test_monitor_empty_list(self, mock_auth_uow, mock_container_uow, client):
        """Monitor with no jobs returns empty items list."""
        admin = MockUser(role='ADMIN')
        _setup_admin_session(client, admin, mock_auth_uow)

        mock_uow = MagicMock()
        mock_uow.jobs.get_for_monitor.return_value = []
        mock_container_uow.return_value = mock_uow

        response = client.get('/admin/api/monitor', headers=JSON_HEADERS)
        assert response.status_code == 200
        data = response.get_json()
        assert 'items' in data
        assert data['items'] == []

    @patch('src.container.get_uow')
    @patch('src.auth.get_uow')
    def test_monitor_with_job_data(self, mock_auth_uow, mock_container_uow, client):
        """Monitor returns properly mapped job data."""
        admin = MockUser(role='ADMIN')
        _setup_admin_session(client, admin, mock_auth_uow)

        now = datetime.utcnow()
        mock_company = MagicMock()
        mock_company.name = 'Test Corp'

        mock_job = MagicMock()
        mock_job.id = uuid.uuid4()
        mock_job.type = 'PROCESS_REPORT'
        mock_job.company = mock_company
        mock_job.input_payload = {
            'filename': 'relatorio.pdf',
            'establishment_name': 'Restaurante A',
            'file_id': None,
        }
        mock_job.status.value = 'COMPLETED'
        mock_job.created_at = now - timedelta(seconds=30)
        mock_job.finished_at = now
        mock_job.cost_input_usd = 0.01
        mock_job.cost_output_usd = 0.02
        mock_job.cost_input_brl = 0.05
        mock_job.cost_output_brl = 0.10
        mock_job.cost_tokens_input = 1000
        mock_job.cost_tokens_output = 500
        mock_job.error_log = None
        mock_job.attempts = 1

        mock_uow = MagicMock()
        mock_uow.jobs.get_for_monitor.return_value = [mock_job]
        mock_container_uow.return_value = mock_uow

        response = client.get('/admin/api/monitor', headers=JSON_HEADERS)
        assert response.status_code == 200
        data = response.get_json()
        assert len(data['items']) == 1

        item = data['items'][0]
        assert item['filename'] == 'relatorio.pdf'
        assert item['company_name'] == 'Test Corp'
        assert item['tokens_total'] == 1500
        assert item['cost_usd'] == 0.03
        assert item['attempts'] == 1

    @patch('src.container.get_uow')
    @patch('src.auth.get_uow')
    def test_monitor_exception_returns_500(self, mock_auth_uow, mock_container_uow, client):
        """Exception in monitor route returns 500 JSON."""
        admin = MockUser(role='ADMIN')
        _setup_admin_session(client, admin, mock_auth_uow)

        mock_uow = MagicMock()
        mock_uow.jobs.get_for_monitor.side_effect = Exception("DB timeout")
        mock_container_uow.return_value = mock_uow

        response = client.get('/admin/api/monitor', headers=JSON_HEADERS)
        assert response.status_code == 500
        data = response.get_json()
        assert 'error' in data


# ===================================================================
#  TRACKER DETAILS
# ===================================================================

class TestTrackerDetails:
    """Tests for GET /admin/api/tracker/<uuid>."""

    @patch('src.container.get_tracker_service')
    @patch('src.container.get_uow')
    @patch('src.auth.get_uow')
    def test_tracker_success(self, mock_auth_uow, mock_container_uow, mock_get_tracker, client):
        """Tracker returns data for a valid inspection."""
        admin = MockUser(role='ADMIN')
        _setup_admin_session(client, admin, mock_auth_uow)

        mock_insp = MagicMock()
        mock_uow = MagicMock()
        mock_uow.inspections.get_by_id.return_value = mock_insp
        mock_container_uow.return_value = mock_uow

        tracker_data = {'status': 'COMPLETED', 'steps': []}
        mock_tracker_svc = MagicMock()
        mock_tracker_svc.get_tracker_data.return_value = tracker_data
        mock_get_tracker.return_value = mock_tracker_svc

        insp_id = uuid.uuid4()
        response = client.get(f'/admin/api/tracker/{insp_id}', headers=JSON_HEADERS)
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'COMPLETED'

    @patch('src.container.get_tracker_service')
    @patch('src.container.get_uow')
    @patch('src.auth.get_uow')
    def test_tracker_not_found(self, mock_auth_uow, mock_container_uow, mock_get_tracker, client):
        """Tracker returns 404 when inspection is not found."""
        admin = MockUser(role='ADMIN')
        _setup_admin_session(client, admin, mock_auth_uow)

        mock_uow = MagicMock()
        mock_uow.inspections.get_by_id.return_value = None
        mock_container_uow.return_value = mock_uow

        insp_id = uuid.uuid4()
        response = client.get(f'/admin/api/tracker/{insp_id}', headers=JSON_HEADERS)
        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data

    @patch('src.container.get_tracker_service')
    @patch('src.container.get_uow')
    @patch('src.auth.get_uow')
    def test_tracker_exception(self, mock_auth_uow, mock_container_uow, mock_get_tracker, client):
        """Exception in tracker returns 500."""
        admin = MockUser(role='ADMIN')
        _setup_admin_session(client, admin, mock_auth_uow)

        mock_uow = MagicMock()
        mock_uow.inspections.get_by_id.side_effect = Exception("DB error")
        mock_container_uow.return_value = mock_uow

        insp_id = uuid.uuid4()
        response = client.get(f'/admin/api/tracker/{insp_id}', headers=JSON_HEADERS)
        assert response.status_code == 500
        data = response.get_json()
        assert 'error' in data


# ===================================================================
#  GET SETTINGS
# ===================================================================

class TestGetSettings:
    """Tests for GET /admin/api/settings."""

    @patch('src.container.get_uow')
    @patch('src.auth.get_uow')
    def test_get_settings_success(self, mock_auth_uow, mock_container_uow, client):
        """Settings endpoint returns grouped config data."""
        admin = MockUser(role='ADMIN')
        _setup_admin_session(client, admin, mock_auth_uow)

        # Mock AppConfig objects
        mock_config_1 = MagicMock()
        mock_config_1.key = 'SMTP_EMAIL'
        mock_config_1.value = 'test@gmail.com'

        mock_config_2 = MagicMock()
        mock_config_2.key = 'OPENAI_API_KEY'
        mock_config_2.value = 'sk-1234567890abcdef'

        mock_uow = MagicMock()
        mock_uow.config.get_all.return_value = [mock_config_1, mock_config_2]
        mock_container_uow.return_value = mock_uow

        response = client.get('/admin/api/settings', headers=JSON_HEADERS)
        assert response.status_code == 200
        data = response.get_json()
        # The response should contain the config groups
        assert 'google_drive' in data
        assert 'email_smtp' in data
        assert 'openai' in data
        # Sensitive key should be masked
        openai_fields = data['openai']['fields']
        api_key_field = [f for f in openai_fields if f['key'] == 'OPENAI_API_KEY'][0]
        assert api_key_field['is_configured'] is True
        assert api_key_field['value_masked'].startswith('****')

    @patch('src.container.get_uow')
    @patch('src.auth.get_uow')
    def test_get_settings_exception(self, mock_auth_uow, mock_container_uow, client):
        """Exception in settings returns 500."""
        admin = MockUser(role='ADMIN')
        _setup_admin_session(client, admin, mock_auth_uow)

        mock_uow = MagicMock()
        mock_uow.config.get_all.side_effect = Exception("DB error")
        mock_container_uow.return_value = mock_uow

        response = client.get('/admin/api/settings', headers=JSON_HEADERS)
        assert response.status_code == 500
        data = response.get_json()
        assert 'error' in data


# ===================================================================
#  SAVE SETTINGS
# ===================================================================

class TestSaveSettings:
    """Tests for POST /admin/api/settings."""

    @patch('src.container.get_uow')
    @patch('src.auth.get_uow')
    def test_save_settings_success(self, mock_auth_uow, mock_container_uow, client):
        """Saving valid settings returns success."""
        admin = MockUser(role='ADMIN')
        _setup_admin_session(client, admin, mock_auth_uow)

        mock_uow = MagicMock()
        mock_container_uow.return_value = mock_uow

        response = client.post(
            '/admin/api/settings',
            json={'SMTP_EMAIL': 'new@gmail.com', 'SMTP_PORT': '465'},
            headers=JSON_HEADERS,
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert '2' in data['message']  # "2 configuracao(oes) salva(s)."
        mock_uow.commit.assert_called_once()

    @patch('src.container.get_uow')
    @patch('src.auth.get_uow')
    def test_save_settings_skips_masked_values(self, mock_auth_uow, mock_container_uow, client):
        """Settings that start with **** are skipped (not saved)."""
        admin = MockUser(role='ADMIN')
        _setup_admin_session(client, admin, mock_auth_uow)

        mock_uow = MagicMock()
        mock_container_uow.return_value = mock_uow

        response = client.post(
            '/admin/api/settings',
            json={'OPENAI_API_KEY': '****cdef', 'SMTP_EMAIL': 'real@test.com'},
            headers=JSON_HEADERS,
        )
        assert response.status_code == 200
        data = response.get_json()
        # Only SMTP_EMAIL should be saved (the masked value is skipped)
        assert '1' in data['message']

    @patch('src.container.get_uow')
    @patch('src.auth.get_uow')
    def test_save_settings_invalid_keys_ignored(self, mock_auth_uow, mock_container_uow, client):
        """Keys not in CONFIG_GROUPS are silently ignored."""
        admin = MockUser(role='ADMIN')
        _setup_admin_session(client, admin, mock_auth_uow)

        mock_uow = MagicMock()
        mock_container_uow.return_value = mock_uow

        response = client.post(
            '/admin/api/settings',
            json={'TOTALLY_INVALID_KEY': 'val'},
            headers=JSON_HEADERS,
        )
        assert response.status_code == 200
        data = response.get_json()
        assert '0' in data['message']

    @patch('src.container.get_uow')
    @patch('src.auth.get_uow')
    def test_save_settings_empty_dict_returns_400(self, mock_auth_uow, mock_container_uow, client):
        """Empty JSON object is treated as invalid data and returns 400."""
        admin = MockUser(role='ADMIN')
        _setup_admin_session(client, admin, mock_auth_uow)
        mock_container_uow.return_value = MagicMock()

        response = client.post(
            '/admin/api/settings',
            json={},
            headers=JSON_HEADERS,
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    @patch('src.container.get_uow')
    @patch('src.auth.get_uow')
    def test_save_settings_no_json_content_type_returns_error(self, mock_auth_uow, mock_container_uow, client):
        """Request without JSON content type returns 500 (caught by exception handler)."""
        admin = MockUser(role='ADMIN')
        _setup_admin_session(client, admin, mock_auth_uow)

        mock_uow = MagicMock()
        mock_container_uow.return_value = mock_uow

        response = client.post(
            '/admin/api/settings',
            data='not json',
            headers=JSON_HEADERS,
        )
        assert response.status_code == 500
        data = response.get_json()
        assert 'error' in data

    @patch('src.container.get_uow')
    @patch('src.auth.get_uow')
    def test_save_settings_exception(self, mock_auth_uow, mock_container_uow, client):
        """Exception during save returns 500."""
        admin = MockUser(role='ADMIN')
        _setup_admin_session(client, admin, mock_auth_uow)

        mock_uow = MagicMock()
        mock_uow.config.set_value.side_effect = Exception("DB write error")
        mock_container_uow.return_value = mock_uow

        response = client.post(
            '/admin/api/settings',
            json={'SMTP_EMAIL': 'fail@test.com'},
            headers=JSON_HEADERS,
        )
        assert response.status_code == 500
        data = response.get_json()
        assert 'error' in data
        mock_uow.rollback.assert_called_once()
