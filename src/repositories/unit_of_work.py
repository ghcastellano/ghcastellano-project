"""
Unit of Work pattern for managing database transactions.

Provides a single entry point for all repositories within a request,
ensuring consistent transaction management.
"""
from .inspection_repository import InspectionRepository
from .user_repository import UserRepository
from .company_repository import CompanyRepository
from .establishment_repository import EstablishmentRepository
from .job_repository import JobRepository
from .action_plan_repository import ActionPlanRepository
from .config_repository import ConfigRepository


class UnitOfWork:
    """
    Aggregates all repositories and manages the database session lifecycle.

    Usage:
        uow = UnitOfWork(session)
        user = uow.users.get_by_email('test@example.com')
        uow.inspections.add(inspection)
        uow.commit()
    """

    def __init__(self, session):
        self.session = session
        self.inspections = InspectionRepository(session)
        self.users = UserRepository(session)
        self.companies = CompanyRepository(session)
        self.establishments = EstablishmentRepository(session)
        self.jobs = JobRepository(session)
        self.action_plans = ActionPlanRepository(session)
        self.config = ConfigRepository(session)

    def commit(self):
        self.session.commit()

    def rollback(self):
        self.session.rollback()

    def flush(self):
        self.session.flush()

    def close(self):
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        self.close()
        return False
