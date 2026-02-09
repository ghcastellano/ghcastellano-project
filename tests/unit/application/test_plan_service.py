"""Tests for PlanService."""
import pytest
import uuid
from unittest.mock import MagicMock
from datetime import datetime

from src.application.plan_service import PlanService
from src.repositories.unit_of_work import UnitOfWork
from src.models_db import InspectionStatus, ActionPlanItemStatus, SeverityLevel


class TestPlanService:

    @pytest.fixture
    def plan_env(self, db_session, inspection_factory,
                 action_plan_factory, action_plan_item_factory):
        """Create environment with inspection + plan + items."""
        inspection = inspection_factory.create(
            db_session,
            drive_file_id='test-plan-file',
            status=InspectionStatus.PENDING_MANAGER_REVIEW,
        )
        plan = action_plan_factory.create(db_session, inspection=inspection)
        item = action_plan_item_factory.create(
            db_session, action_plan=plan,
            problem_description='Problema original',
            corrective_action='Ação original',
            order_index=0,
        )

        uow = UnitOfWork(db_session)
        svc = PlanService(uow)

        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.role = MagicMock()
        mock_user.role.value = 'MANAGER'

        return {
            'service': svc,
            'uow': uow,
            'inspection': inspection,
            'plan': plan,
            'item': item,
            'user': mock_user,
        }

    def test_save_plan_updates_summary(self, plan_env):
        svc = plan_env['service']
        result = svc.save_plan('test-plan-file', {
            'summary_text': 'Novo resumo',
            'strengths_text': 'Novos pontos fortes',
        }, plan_env['user'])

        assert result.success is True
        assert plan_env['plan'].summary_text == 'Novo resumo'
        assert plan_env['plan'].strengths_text == 'Novos pontos fortes'

    def test_save_plan_updates_existing_item(self, plan_env):
        svc = plan_env['service']
        item_id = str(plan_env['item'].id)

        result = svc.save_plan('test-plan-file', {
            'items': [{
                'id': item_id,
                'problem': 'Problema editado',
                'action': 'Ação editada',
            }],
        }, plan_env['user'])

        assert result.success is True
        assert plan_env['item'].problem_description == 'Problema editado'
        assert plan_env['item'].corrective_action == 'Ação editada'

    def test_save_plan_creates_new_item(self, plan_env):
        svc = plan_env['service']

        result = svc.save_plan('test-plan-file', {
            'items': [{
                'problem': 'Novo problema',
                'action': 'Nova ação',
                'severity': 'HIGH',
            }],
        }, plan_env['user'])

        assert result.success is True
        items = plan_env['uow'].action_plans.get_items_by_plan_id(plan_env['plan'].id)
        assert len(items) >= 2

    def test_save_plan_not_found(self, db_session):
        uow = UnitOfWork(db_session)
        svc = PlanService(uow)
        user = MagicMock()

        result = svc.save_plan('nonexistent', {}, user)
        assert result.success is False
        assert result.error == 'NOT_FOUND'

    def test_save_plan_already_approved_forbidden(self, plan_env, db_session):
        plan_env['inspection'].status = InspectionStatus.APPROVED
        db_session.flush()

        svc = plan_env['service']
        result = svc.save_plan('test-plan-file', {}, plan_env['user'])
        assert result.success is False
        assert result.error == 'ALREADY_APPROVED'

    def test_approve_plan_changes_status(self, plan_env, db_session):
        svc = plan_env['service']
        result = svc.approve_plan('test-plan-file', plan_env['user'])

        assert result.success is True
        assert plan_env['inspection'].status == InspectionStatus.PENDING_CONSULTANT_VERIFICATION
        assert plan_env['plan'].approved_by_id == plan_env['user'].id
        assert plan_env['plan'].approved_at is not None

    def test_approve_plan_not_found(self, db_session):
        uow = UnitOfWork(db_session)
        svc = PlanService(uow)
        user = MagicMock()

        result = svc.approve_plan('nonexistent', user)
        assert result.success is False

    def test_finalize_verification(self, plan_env, db_session):
        plan_env['inspection'].status = InspectionStatus.PENDING_CONSULTANT_VERIFICATION
        db_session.flush()

        svc = plan_env['service']
        result = svc.finalize_verification('test-plan-file')

        assert result.success is True
        assert plan_env['inspection'].status == InspectionStatus.COMPLETED

    def test_save_review_updates_item_status(self, plan_env):
        svc = plan_env['service']
        item_id = str(plan_env['item'].id)

        result = svc.save_review('test-plan-file', {
            'items': [{
                'id': item_id,
                'current_status': 'Corrigido',
                'manager_notes': 'Verificado em campo',
            }],
        })

        assert result.success is True
        assert plan_env['item'].current_status == 'Corrigido'
        assert plan_env['item'].manager_notes == 'Verificado em campo'

    def test_parse_date_iso(self):
        result = PlanService._parse_date('2025-06-15')
        assert result is not None
        assert result.year == 2025
        assert result.month == 6

    def test_parse_date_br(self):
        result = PlanService._parse_date('15/06/2025')
        assert result is not None
        assert result.day == 15

    def test_parse_date_invalid(self):
        result = PlanService._parse_date('em 7 dias')
        assert result is None

    def test_parse_date_none(self):
        result = PlanService._parse_date(None)
        assert result is None
