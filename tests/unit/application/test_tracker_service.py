"""Tests for TrackerService."""
import pytest
from unittest.mock import MagicMock
from src.application.tracker_service import TrackerService


def _make_inspection(status_value, has_plan=False, logs=None):
    """Create a mock inspection for tracker tests."""
    insp = MagicMock()
    insp.id = 'test-id'
    insp.status = MagicMock()
    insp.status.value = status_value
    insp.processing_logs = logs or []
    insp.processed_filename = 'test.pdf'
    insp.action_plan = MagicMock() if has_plan else None
    return insp


class TestTrackerService:

    def test_processing_state(self):
        insp = _make_inspection('PROCESSING', has_plan=False)
        svc = TrackerService()
        steps = svc.get_tracker_steps(insp)

        assert steps['upload']['status'] == 'completed'
        assert steps['ai_process']['status'] == 'pending'
        assert steps['db_save']['status'] == 'pending'

    def test_with_logs_marks_ai_completed(self):
        insp = _make_inspection('PROCESSING', logs=[{'message': 'Processing started'}])
        svc = TrackerService()
        steps = svc.get_tracker_steps(insp)

        assert steps['ai_process']['status'] == 'completed'

    def test_with_plan_marks_through_plan_gen(self):
        insp = _make_inspection('PROCESSING', has_plan=True)
        svc = TrackerService()
        steps = svc.get_tracker_steps(insp)

        assert steps['ai_process']['status'] == 'completed'
        assert steps['db_save']['status'] == 'completed'
        assert steps['plan_gen']['status'] == 'completed'

    def test_pending_review_marks_analysis_current(self):
        insp = _make_inspection('PENDING_MANAGER_REVIEW', has_plan=True)
        svc = TrackerService()
        steps = svc.get_tracker_steps(insp)

        assert steps['plan_gen']['status'] == 'completed'
        assert steps['analysis']['status'] == 'current'

    def test_approved_marks_analysis_completed(self):
        insp = _make_inspection('APPROVED', has_plan=True)
        svc = TrackerService()
        steps = svc.get_tracker_steps(insp)

        assert steps['analysis']['status'] == 'completed'
        assert steps['analysis']['label'] == 'Aprovado'

    def test_completed_marks_all_done(self):
        insp = _make_inspection('COMPLETED', has_plan=True)
        svc = TrackerService()
        steps = svc.get_tracker_steps(insp)

        assert all(s['status'] == 'completed' for s in steps.values())

    def test_error_marks_failed_step(self):
        insp = _make_inspection('FAILED', has_plan=False)
        svc = TrackerService()
        steps = svc.get_tracker_steps(insp)

        assert steps['ai_process']['status'] == 'error'

    def test_error_after_db_save(self):
        insp = _make_inspection('FAILED', has_plan=True)
        svc = TrackerService()
        steps = svc.get_tracker_steps(insp)

        # db_save completed (has plan), so error should be on plan_gen
        assert steps['db_save']['status'] == 'completed'
        assert steps['plan_gen']['status'] == 'error'

    def test_get_tracker_data_returns_full_dict(self):
        insp = _make_inspection('PENDING_MANAGER_REVIEW', has_plan=True,
                                logs=[{'message': 'step1'}, {'message': 'step2'}])
        svc = TrackerService()
        data = svc.get_tracker_data(insp)

        assert data['id'] == 'test-id'
        assert data['status'] == 'PENDING_MANAGER_REVIEW'
        assert 'steps' in data
        assert data['logs'] == ['step1', 'step2']
