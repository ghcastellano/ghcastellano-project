"""Tests for DashboardService."""
import pytest
import uuid
from unittest.mock import MagicMock

from src.application.dashboard_service import DashboardService
from src.repositories.unit_of_work import UnitOfWork
from src.models_db import InspectionStatus


class TestDashboardService:

    @pytest.fixture
    def dash_env(self, db_session, company_factory, establishment_factory,
                 user_factory, inspection_factory):
        company = company_factory.create(db_session)
        est = establishment_factory.create(db_session, company=company)

        # Create user with establishments linked
        from src.models_db import UserRole
        user = user_factory.create(
            db_session,
            company_id=company.id,
            role=UserRole.CONSULTANT,
        )
        user.establishments.append(est)
        db_session.commit()

        # Create some inspections
        insp_pending = inspection_factory.create(
            db_session, establishment=est,
            status=InspectionStatus.PENDING_MANAGER_REVIEW,
        )
        insp_completed = inspection_factory.create(
            db_session, establishment=est,
            status=InspectionStatus.COMPLETED,
            ai_raw_response={
                'pontuacao_geral': 8,
                'pontuacao_maxima_geral': 10,
            },
        )

        uow = UnitOfWork(db_session)
        svc = DashboardService(uow)

        return {
            'service': svc,
            'user': user,
            'company': company,
            'establishment': est,
            'inspection_pending': insp_pending,
            'inspection_completed': insp_completed,
        }

    def test_get_consultant_dashboard_returns_all_keys(self, dash_env):
        svc = dash_env['service']
        result = svc.get_consultant_dashboard(dash_env['user'])

        assert 'inspections' in result
        assert 'stats' in result
        assert 'user_hierarchy' in result
        assert 'pending_establishments' in result
        assert 'failed_jobs' in result

    def test_stats_calculation(self, dash_env):
        svc = dash_env['service']
        result = svc.get_consultant_dashboard(dash_env['user'])

        stats = result['stats']
        assert stats['total'] >= 2  # At least our 2 inspections
        assert 'pontuacao_geral' in stats
        assert 'aproveitamento_geral' in stats

    def test_user_hierarchy_built(self, dash_env):
        svc = dash_env['service']
        result = svc.get_consultant_dashboard(dash_env['user'])

        hierarchy = result['user_hierarchy']
        assert len(hierarchy) >= 1
        company_id = str(dash_env['company'].id)
        assert company_id in hierarchy
        assert len(hierarchy[company_id]['establishments']) >= 1

    def test_pending_establishments(self, dash_env):
        svc = dash_env['service']
        result = svc.get_consultant_dashboard(dash_env['user'])

        pending = result['pending_establishments']
        assert len(pending) >= 1

    def test_build_user_hierarchy_empty(self):
        user = MagicMock()
        user.establishments = []
        result = DashboardService._build_user_hierarchy(user)
        assert result == {}

    def test_build_user_hierarchy_groups_by_company(self):
        user = MagicMock()
        est1 = MagicMock()
        est1.name = 'Est A'
        est1.id = uuid.uuid4()
        est1.company = MagicMock()
        est1.company.name = 'Company 1'
        est1.company.id = uuid.uuid4()

        est2 = MagicMock()
        est2.name = 'Est B'
        est2.id = uuid.uuid4()
        est2.company = est1.company  # Same company

        user.establishments = [est1, est2]

        result = DashboardService._build_user_hierarchy(user)
        company_key = str(est1.company.id)
        assert company_key in result
        assert len(result[company_key]['establishments']) == 2

    def test_merge_jobs_deduplicates(self):
        inspections = [
            {'id': 'file-1', 'name': 'Test', 'status': 'COMPLETED',
             'establishment': 'E1', 'date': '', 'pdf_link': '#', 'review_link': '#'},
        ]
        jobs = [
            {'drive_file_id': 'file-1', 'name': 'Test', 'status': 'Processing',
             'establishment': 'E1', 'created_at': '', 'status_raw': 'PROCESSING'},
        ]
        existing_ids = {'file-1'}

        DashboardService._merge_jobs_into_inspections(inspections, jobs, existing_ids)
        # Should NOT add duplicate
        assert len(inspections) == 1

    def test_merge_jobs_adds_new(self):
        inspections = []
        jobs = [
            {'drive_file_id': 'file-new', 'name': 'New File', 'status': 'Em Análise',
             'establishment': 'E1', 'created_at': '01/01/2025', 'status_raw': 'PROCESSING'},
        ]
        existing_ids = set()

        DashboardService._merge_jobs_into_inspections(inspections, jobs, existing_ids)
        assert len(inspections) == 1
        assert inspections[0]['id'] == 'file-new'
