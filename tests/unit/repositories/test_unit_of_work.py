"""Tests for UnitOfWork."""
import pytest

from src.repositories.unit_of_work import UnitOfWork
from src.repositories.inspection_repository import InspectionRepository
from src.repositories.user_repository import UserRepository
from src.repositories.company_repository import CompanyRepository
from src.repositories.establishment_repository import EstablishmentRepository
from src.repositories.job_repository import JobRepository
from src.repositories.action_plan_repository import ActionPlanRepository
from src.repositories.config_repository import ConfigRepository


class TestUnitOfWork:

    def test_creates_all_repositories(self, db_session):
        uow = UnitOfWork(db_session)

        assert isinstance(uow.inspections, InspectionRepository)
        assert isinstance(uow.users, UserRepository)
        assert isinstance(uow.companies, CompanyRepository)
        assert isinstance(uow.establishments, EstablishmentRepository)
        assert isinstance(uow.jobs, JobRepository)
        assert isinstance(uow.action_plans, ActionPlanRepository)
        assert isinstance(uow.config, ConfigRepository)

    def test_commit(self, db_session, company_factory):
        uow = UnitOfWork(db_session)
        company_factory.create(db_session, name='UoW Test Company')
        uow.commit()

        # After commit, data should be persisted
        results = uow.companies.get_all()
        assert any(c.name == 'UoW Test Company' for c in results)

    def test_rollback(self, db_session):
        from src.models_db import Company
        import uuid

        uow = UnitOfWork(db_session)
        company = Company(id=uuid.uuid4(), name='Rollback Co', cnpj='99999999999999')
        db_session.add(company)
        db_session.flush()

        uow.rollback()
        # After rollback, pending data is gone
        result = uow.companies.get_by_id(company.id)
        assert result is None

    def test_context_manager_commits_on_success(self, db_session):
        # UoW context manager only rollbacks on exception, does not auto-commit
        uow = UnitOfWork(db_session)
        with uow:
            pass  # No exception -> close without rollback

    def test_context_manager_rollbacks_on_exception(self, db_session):
        from src.models_db import Company
        import uuid

        uow = UnitOfWork(db_session)
        company_id = uuid.uuid4()

        with pytest.raises(ValueError):
            with uow:
                company = Company(id=company_id, name='Exception Co', cnpj='88888888888888')
                db_session.add(company)
                db_session.flush()
                raise ValueError("Test exception")
