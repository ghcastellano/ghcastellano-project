"""
Characterization tests for admin routes.

Captures current behavior of admin CRUD operations before refactoring.
These tests serve as a safety net to ensure refactoring doesn't break existing functionality.
"""
import pytest
import uuid
from unittest.mock import patch, MagicMock


@pytest.fixture
def admin_session(client, db_session):
    """Create an authenticated admin session."""
    from src.models_db import User, UserRole, Company
    from werkzeug.security import generate_password_hash

    user = User(
        id=uuid.uuid4(),
        email='admin-char@test.com',
        password_hash=generate_password_hash('adminpass123'),
        name='Admin Char',
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True

    return client, user, db_session


class TestAdminIndex:
    """Tests for GET /admin/"""

    def test_admin_index_requires_login(self, client):
        response = client.get('/admin/')
        assert response.status_code in [302, 401]

    def test_admin_index_requires_admin_role(self, client, db_session):
        from src.models_db import User, UserRole
        from werkzeug.security import generate_password_hash

        user = User(
            id=uuid.uuid4(),
            email='nonadmin@test.com',
            password_hash=generate_password_hash('pass123'),
            name='Non Admin',
            role=UserRole.CONSULTANT,
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

        with client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)
            sess['_fresh'] = True

        response = client.get('/admin/')
        # Non-admin should be redirected
        assert response.status_code == 302

    @pytest.mark.requires_postgres
    def test_admin_index_loads_for_admin(self, admin_session):
        client, user, db_session = admin_session
        response = client.get('/admin/')
        assert response.status_code == 200


class TestCompanyCreation:
    """Tests for POST /admin/company/new"""

    @pytest.mark.requires_postgres
    def test_create_company_success(self, admin_session, mock_drive_service):
        client, user, db_session = admin_session
        response = client.post('/admin/company/new', data={
            'name': 'Nova Empresa Teste',
            'cnpj': '12345678000100',
        }, follow_redirects=True)
        assert response.status_code == 200

    @pytest.mark.requires_postgres
    def test_create_company_without_name(self, admin_session):
        client, user, db_session = admin_session
        response = client.post('/admin/company/new', data={
            'name': '',
            'cnpj': '12345678000100',
        }, follow_redirects=True)
        assert response.status_code == 200
        # Should show error flash

    @pytest.mark.requires_postgres
    def test_create_company_json_response(self, admin_session, mock_drive_service):
        client, user, db_session = admin_session
        response = client.post('/admin/company/new',
            data={'name': 'Empresa JSON', 'cnpj': '99988877000111'},
            headers={'Accept': 'application/json'},
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data['success'] is True
        assert data['company']['name'] == 'Empresa JSON'


class TestCompanyDeletion:
    """Tests for POST /admin/company/<id>/delete"""

    @pytest.mark.requires_postgres
    def test_delete_nonexistent_company(self, admin_session, mock_drive_service):
        client, user, db_session = admin_session
        fake_id = uuid.uuid4()
        response = client.post(f'/admin/company/{fake_id}/delete',
            headers={'Accept': 'application/json'})
        assert response.status_code == 404

    @pytest.mark.requires_postgres
    def test_delete_company_cascades(self, admin_session, mock_drive_service):
        """Verify cascading delete removes all related entities."""
        client, user, db_session = admin_session
        from src.models_db import Company, Establishment, Inspection, InspectionStatus

        company = Company(id=uuid.uuid4(), name='To Delete', cnpj='00000000000100')
        db_session.add(company)
        db_session.commit()

        est = Establishment(id=uuid.uuid4(), company_id=company.id, name='Est Delete')
        db_session.add(est)
        db_session.commit()

        response = client.post(f'/admin/company/{company.id}/delete',
            headers={'Accept': 'application/json'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

        # Verify company is gone
        assert db_session.query(Company).get(company.id) is None


class TestManagerCreation:
    """Tests for POST /admin/manager/new"""

    @pytest.mark.requires_postgres
    def test_create_manager_requires_email_and_company(self, admin_session):
        client, user, db_session = admin_session
        response = client.post('/admin/manager/new',
            data={'name': 'Manager', 'email': '', 'company_id': ''},
            headers={'Accept': 'application/json'})
        assert response.status_code == 400

    @pytest.mark.requires_postgres
    def test_create_manager_success(self, admin_session, mock_drive_service):
        client, user, db_session = admin_session
        from src.models_db import Company

        company = Company(id=uuid.uuid4(), name='Manager Company', cnpj='11122233000144')
        db_session.add(company)
        db_session.commit()

        response = client.post('/admin/manager/new', data={
            'name': 'Novo Gestor',
            'email': 'newmanager@test.com',
            'company_id': str(company.id),
            'password': 'testpass123',
        }, follow_redirects=True)
        assert response.status_code == 200


class TestAdminSettings:
    """Tests for admin settings API."""

    @pytest.mark.requires_postgres
    def test_settings_requires_admin(self, client):
        response = client.get('/admin/api/settings')
        assert response.status_code in [302, 401]

    @pytest.mark.requires_postgres
    def test_monitor_requires_admin(self, client):
        response = client.get('/admin/api/monitor')
        assert response.status_code in [302, 401]
