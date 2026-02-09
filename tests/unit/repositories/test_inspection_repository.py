"""Tests for InspectionRepository."""
import pytest
import uuid

from src.repositories.inspection_repository import InspectionRepository
from src.models_db import Inspection, InspectionStatus


class TestInspectionRepository:

    def test_get_by_id(self, db_session, inspection_factory):
        inspection = inspection_factory.create(db_session)
        repo = InspectionRepository(db_session)

        result = repo.get_by_id(inspection.id)
        assert result is not None
        assert result.id == inspection.id

    def test_get_by_id_not_found(self, db_session):
        repo = InspectionRepository(db_session)
        result = repo.get_by_id(uuid.uuid4())
        assert result is None

    def test_get_by_drive_file_id(self, db_session, inspection_factory):
        inspection = inspection_factory.create(db_session, drive_file_id='test-drive-id-123')
        repo = InspectionRepository(db_session)

        result = repo.get_by_drive_file_id('test-drive-id-123')
        assert result is not None
        assert result.id == inspection.id

    def test_get_by_drive_file_id_not_found(self, db_session):
        repo = InspectionRepository(db_session)
        result = repo.get_by_drive_file_id('nonexistent')
        assert result is None

    def test_get_by_file_hash(self, db_session, inspection_factory):
        inspection = inspection_factory.create(db_session, file_hash='abc123hash')
        repo = InspectionRepository(db_session)

        result = repo.get_by_file_hash('abc123hash')
        assert result is not None
        assert result.id == inspection.id

    def test_get_by_file_hash_excludes_statuses(self, db_session, inspection_factory):
        inspection_factory.create(
            db_session,
            file_hash='hash-excluded',
            status=InspectionStatus.REJECTED,
        )
        repo = InspectionRepository(db_session)

        result = repo.get_by_file_hash(
            'hash-excluded',
            exclude_statuses=[InspectionStatus.REJECTED],
        )
        assert result is None

    def test_get_with_plan_by_file_id(self, db_session, inspection_factory, action_plan_factory):
        inspection = inspection_factory.create(db_session, drive_file_id='with-plan-id')
        action_plan_factory.create(db_session, inspection=inspection)
        repo = InspectionRepository(db_session)

        result = repo.get_with_plan_by_file_id('with-plan-id')
        assert result is not None
        assert result.action_plan is not None

    def test_get_for_consultant_by_establishment(self, db_session, establishment_factory, inspection_factory):
        est = establishment_factory.create(db_session)
        inspection = inspection_factory.create(
            db_session, establishment=est,
            status=InspectionStatus.PENDING_MANAGER_REVIEW,
        )
        repo = InspectionRepository(db_session)

        results = repo.get_for_consultant(establishment_ids=[est.id])
        assert len(results) >= 1
        assert any(r.id == inspection.id for r in results)

    def test_get_for_consultant_filters_by_status(self, db_session, establishment_factory, inspection_factory):
        est = establishment_factory.create(db_session)
        inspection_factory.create(
            db_session, establishment=est,
            status=InspectionStatus.PROCESSING,
        )
        repo = InspectionRepository(db_session)

        # PROCESSING is not in default statuses
        results = repo.get_for_consultant(establishment_ids=[est.id])
        assert len(results) == 0

    def test_get_for_manager_by_company(self, db_session, company_factory, establishment_factory, inspection_factory):
        company = company_factory.create(db_session)
        est = establishment_factory.create(db_session, company=company)
        inspection = inspection_factory.create(
            db_session, establishment=est,
            status=InspectionStatus.PENDING_MANAGER_REVIEW,
        )
        repo = InspectionRepository(db_session)

        results = repo.get_for_manager(company_id=company.id)
        assert len(results) >= 1
        assert any(r.id == inspection.id for r in results)

    def test_get_for_manager_by_establishment(self, db_session, establishment_factory, inspection_factory):
        est = establishment_factory.create(db_session)
        inspection = inspection_factory.create(
            db_session, establishment=est,
            status=InspectionStatus.APPROVED,
        )
        repo = InspectionRepository(db_session)

        results = repo.get_for_manager(establishment_id=est.id)
        assert len(results) >= 1
        assert any(r.id == inspection.id for r in results)

    def test_get_pending(self, db_session, establishment_factory, inspection_factory):
        est = establishment_factory.create(db_session)
        inspection = inspection_factory.create(
            db_session, establishment=est,
            status=InspectionStatus.PENDING_MANAGER_REVIEW,
        )
        repo = InspectionRepository(db_session)

        results = repo.get_pending(establishment_ids=[est.id])
        assert len(results) >= 1
        assert any(r.id == inspection.id for r in results)

    def test_get_processing(self, db_session, inspection_factory):
        inspection = inspection_factory.create(
            db_session,
            status=InspectionStatus.PROCESSING,
        )
        repo = InspectionRepository(db_session)

        results = repo.get_processing()
        assert len(results) >= 1
        assert any(r.id == inspection.id for r in results)

    def test_add(self, db_session, establishment_factory):
        est = establishment_factory.create(db_session)
        repo = InspectionRepository(db_session)

        inspection = Inspection(
            id=uuid.uuid4(),
            drive_file_id=f'new-{uuid.uuid4().hex[:8]}',
            status=InspectionStatus.PROCESSING,
            establishment_id=est.id,
        )
        result = repo.add(inspection)
        db_session.flush()

        assert result.id == inspection.id
        assert repo.get_by_id(inspection.id) is not None

    def test_delete(self, db_session, inspection_factory):
        inspection = inspection_factory.create(db_session)
        repo = InspectionRepository(db_session)

        repo.delete(inspection)
        db_session.flush()

        assert repo.get_by_id(inspection.id) is None
