"""Tests for AdminService."""
import pytest
import uuid
from unittest.mock import MagicMock

from src.application.admin_service import AdminService
from src.repositories.unit_of_work import UnitOfWork
from src.models_db import UserRole


class TestAdminService:

    @pytest.fixture
    def admin_svc(self, db_session):
        uow = UnitOfWork(db_session)
        mock_drive = MagicMock()
        mock_drive.service = None  # Disable Drive in tests
        mock_email = MagicMock()
        return AdminService(uow, drive_service=mock_drive, email_service=mock_email)

    def test_create_company(self, admin_svc):
        result = admin_svc.create_company('Test Corp', cnpj='11111111111111')

        assert result.success is True
        assert 'Test Corp' in result.message
        assert result.data['name'] == 'Test Corp'

    def test_create_company_no_name(self, admin_svc):
        result = admin_svc.create_company('')
        assert result.success is False
        assert result.error == 'MISSING_NAME'

    def test_create_manager(self, db_session, admin_svc, company_factory):
        company = company_factory.create(db_session)
        result = admin_svc.create_manager(
            name='New Manager',
            email='new-manager@test.com',
            company_id=company.id,
        )

        assert result.success is True
        assert result.data['email'] == 'new-manager@test.com'
        assert 'password' in result.data
        assert len(result.data['password']) >= 12

    def test_create_manager_duplicate_email(self, db_session, admin_svc, company_factory, user_factory):
        company = company_factory.create(db_session)
        user_factory.create(db_session, email='dup@test.com', company_id=company.id)

        result = admin_svc.create_manager(
            name='Dup Manager',
            email='dup@test.com',
            company_id=company.id,
        )

        assert result.success is False
        assert result.error == 'DUPLICATE_EMAIL'

    def test_create_manager_missing_fields(self, admin_svc):
        result = admin_svc.create_manager(name='Test', email='', company_id='')
        assert result.success is False
        assert result.error == 'MISSING_FIELDS'

    def test_delete_manager(self, db_session, company_factory, user_factory):
        company = company_factory.create(db_session)
        manager = user_factory.create(
            db_session, role=UserRole.MANAGER, company_id=company.id,
        )

        uow = UnitOfWork(db_session)
        svc = AdminService(uow)
        result = svc.delete_manager(manager.id)

        assert result.success is True
        assert uow.users.get_by_id(manager.id) is None

    def test_delete_manager_not_found(self, db_session):
        uow = UnitOfWork(db_session)
        svc = AdminService(uow)
        result = svc.delete_manager(uuid.uuid4())
        assert result.success is False
        assert result.error == 'NOT_FOUND'

    def test_update_manager(self, db_session, company_factory, user_factory):
        company = company_factory.create(db_session)
        manager = user_factory.create(
            db_session, name='Old Name', role=UserRole.MANAGER, company_id=company.id,
        )

        uow = UnitOfWork(db_session)
        svc = AdminService(uow)
        result = svc.update_manager(manager.id, name='New Name')

        assert result.success is True
        updated = uow.users.get_by_id(manager.id)
        assert updated.name == 'New Name'

    def test_delete_company_cascade(self, db_session, company_factory,
                                     establishment_factory, user_factory,
                                     inspection_factory, action_plan_factory,
                                     action_plan_item_factory):
        """Test that deleting a company cascades through all related records."""
        company = company_factory.create(db_session)
        est = establishment_factory.create(db_session, company=company)
        user = user_factory.create(db_session, company_id=company.id, role=UserRole.MANAGER)
        inspection = inspection_factory.create(db_session, establishment=est)
        plan = action_plan_factory.create(db_session, inspection=inspection)
        action_plan_item_factory.create(db_session, action_plan=plan)

        uow = UnitOfWork(db_session)
        svc = AdminService(uow)
        result = svc.delete_company(company.id)

        assert result.success is True
        assert uow.companies.get_by_id(company.id) is None
        assert uow.users.get_by_id(user.id) is None

    def test_delete_company_not_found(self, db_session):
        uow = UnitOfWork(db_session)
        svc = AdminService(uow)
        result = svc.delete_company(uuid.uuid4())
        assert result.success is False
        assert result.error == 'NOT_FOUND'

    def test_get_monitor_data(self, db_session, company_factory):
        from src.models_db import Job, JobStatus
        company = company_factory.create(db_session)

        job = Job(
            id=uuid.uuid4(),
            company_id=company.id,
            type='PROCESS_REPORT',
            status=JobStatus.COMPLETED,
            input_payload={'filename': 'test.pdf', 'establishment_name': 'Est1'},
        )
        db_session.add(job)
        db_session.commit()

        uow = UnitOfWork(db_session)
        svc = AdminService(uow)
        data = svc.get_monitor_data(limit=10)

        assert len(data) >= 1
        assert data[0]['filename'] == 'test.pdf'
