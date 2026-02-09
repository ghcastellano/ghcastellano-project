"""Tests for CompanyRepository and EstablishmentRepository."""
import pytest
import uuid

from src.repositories.company_repository import CompanyRepository
from src.repositories.establishment_repository import EstablishmentRepository
from src.models_db import Company, Establishment


class TestCompanyRepository:

    def test_get_by_id(self, db_session, company_factory):
        company = company_factory.create(db_session)
        repo = CompanyRepository(db_session)

        result = repo.get_by_id(company.id)
        assert result is not None
        assert result.id == company.id

    def test_get_by_id_not_found(self, db_session):
        repo = CompanyRepository(db_session)
        assert repo.get_by_id(uuid.uuid4()) is None

    def test_get_all(self, db_session, company_factory):
        company_factory.create(db_session, name='Company A')
        company_factory.create(db_session, name='Company B')
        repo = CompanyRepository(db_session)

        results = repo.get_all()
        names = [c.name for c in results]
        assert 'Company A' in names
        assert 'Company B' in names

    def test_add(self, db_session):
        repo = CompanyRepository(db_session)
        company = Company(id=uuid.uuid4(), name='New Co', cnpj='11111111111111')
        repo.add(company)
        db_session.flush()

        assert repo.get_by_id(company.id) is not None

    def test_delete(self, db_session, company_factory):
        company = company_factory.create(db_session)
        repo = CompanyRepository(db_session)

        repo.delete(company)
        db_session.flush()
        assert repo.get_by_id(company.id) is None


class TestEstablishmentRepository:

    def test_get_by_id(self, db_session, establishment_factory):
        est = establishment_factory.create(db_session)
        repo = EstablishmentRepository(db_session)

        result = repo.get_by_id(est.id)
        assert result is not None
        assert result.id == est.id

    def test_get_by_id_not_found(self, db_session):
        repo = EstablishmentRepository(db_session)
        assert repo.get_by_id(uuid.uuid4()) is None

    def test_get_by_company(self, db_session, company_factory, establishment_factory):
        company = company_factory.create(db_session)
        est1 = establishment_factory.create(db_session, company=company, name='Est A')
        est2 = establishment_factory.create(db_session, company=company, name='Est B')
        repo = EstablishmentRepository(db_session)

        results = repo.get_by_company(company.id)
        ids = [r.id for r in results]
        assert est1.id in ids
        assert est2.id in ids

    def test_get_by_name_and_company(self, db_session, company_factory, establishment_factory):
        company = company_factory.create(db_session)
        est = establishment_factory.create(db_session, company=company, name='Unique Name')
        repo = EstablishmentRepository(db_session)

        result = repo.get_by_name_and_company('Unique Name', company.id)
        assert result is not None
        assert result.id == est.id

    def test_get_by_name_and_company_not_found(self, db_session, company_factory):
        company = company_factory.create(db_session)
        repo = EstablishmentRepository(db_session)

        result = repo.get_by_name_and_company('Nonexistent', company.id)
        assert result is None

    def test_add(self, db_session, company_factory):
        company = company_factory.create(db_session)
        repo = EstablishmentRepository(db_session)

        est = Establishment(
            id=uuid.uuid4(),
            company_id=company.id,
            name='New Establishment',
            code='NEW001',
        )
        repo.add(est)
        db_session.flush()

        assert repo.get_by_id(est.id) is not None

    def test_delete(self, db_session, establishment_factory):
        est = establishment_factory.create(db_session)
        repo = EstablishmentRepository(db_session)

        repo.delete(est)
        db_session.flush()
        assert repo.get_by_id(est.id) is None
