"""Tests for UserRepository."""
import pytest
import uuid

from src.repositories.user_repository import UserRepository
from src.models_db import User, UserRole
from werkzeug.security import generate_password_hash


class TestUserRepository:

    def test_get_by_id(self, db_session, user_factory):
        user = user_factory.create(db_session)
        repo = UserRepository(db_session)

        result = repo.get_by_id(user.id)
        assert result is not None
        assert result.id == user.id

    def test_get_by_id_not_found(self, db_session):
        repo = UserRepository(db_session)
        assert repo.get_by_id(uuid.uuid4()) is None

    def test_get_by_email(self, db_session, user_factory):
        user = user_factory.create(db_session, email='findme@test.com')
        repo = UserRepository(db_session)

        result = repo.get_by_email('findme@test.com')
        assert result is not None
        assert result.id == user.id

    def test_get_by_email_not_found(self, db_session):
        repo = UserRepository(db_session)
        assert repo.get_by_email('nobody@test.com') is None

    def test_get_consultants_for_company(self, db_session, company_factory, user_factory):
        company = company_factory.create(db_session)
        consultant = user_factory.create(
            db_session,
            role=UserRole.CONSULTANT,
            company_id=company.id,
            is_active=True,
        )
        # Manager should NOT be returned
        user_factory.create(
            db_session,
            role=UserRole.MANAGER,
            company_id=company.id,
        )
        repo = UserRepository(db_session)

        results = repo.get_consultants_for_company(company.id)
        assert len(results) == 1
        assert results[0].id == consultant.id

    def test_get_consultants_for_company_excludes_inactive(self, db_session, company_factory, user_factory):
        company = company_factory.create(db_session)
        user_factory.create(
            db_session,
            role=UserRole.CONSULTANT,
            company_id=company.id,
            is_active=False,
        )
        repo = UserRepository(db_session)

        results = repo.get_consultants_for_company(company.id)
        assert len(results) == 0

    def test_get_managers_with_company(self, db_session, company_factory, user_factory):
        company = company_factory.create(db_session)
        manager = user_factory.create(
            db_session,
            role=UserRole.MANAGER,
            company_id=company.id,
        )
        repo = UserRepository(db_session)

        results = repo.get_managers_with_company()
        assert len(results) >= 1
        assert any(r.id == manager.id for r in results)

    def test_get_all_by_company(self, db_session, company_factory, user_factory):
        company = company_factory.create(db_session)
        u1 = user_factory.create(db_session, company_id=company.id, role=UserRole.CONSULTANT)
        u2 = user_factory.create(db_session, company_id=company.id, role=UserRole.MANAGER)
        repo = UserRepository(db_session)

        results = repo.get_all_by_company(company.id)
        ids = [r.id for r in results]
        assert u1.id in ids
        assert u2.id in ids

    def test_add(self, db_session):
        repo = UserRepository(db_session)
        user = User(
            id=uuid.uuid4(),
            email=f'new-{uuid.uuid4().hex[:6]}@test.com',
            password_hash=generate_password_hash('pass'),
            name='New User',
            role=UserRole.CONSULTANT,
            is_active=True,
        )
        result = repo.add(user)
        db_session.flush()

        assert repo.get_by_id(user.id) is not None

    def test_delete(self, db_session, user_factory):
        user = user_factory.create(db_session)
        repo = UserRepository(db_session)

        repo.delete(user)
        db_session.flush()

        assert repo.get_by_id(user.id) is None
