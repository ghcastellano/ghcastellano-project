"""
Unit tests for the dependency injection container (src/container.py).

Tests cover all factory functions:
- get_uow: creates/reuses UnitOfWork per request
- get_inspection_data_service: returns InspectionDataService
- get_dashboard_service: returns DashboardService
- get_upload_service: returns UploadService with processor and validator
- get_plan_service: returns PlanService with optional pdf/storage
- get_admin_service: returns AdminService with optional drive/email
- get_tracker_service: returns TrackerService (stateless)
- teardown_uow: closes UoW, rollback on exception
"""

from unittest.mock import MagicMock, patch, PropertyMock
import pytest


class TestGetUow:
    """Tests for get_uow() factory function."""

    @patch('src.container.UnitOfWork')
    @patch('src.container.get_db')
    def test_creates_uow_on_first_call(self, mock_get_db, mock_uow_cls, app):
        """Should create a new UnitOfWork on the first call within a request."""
        mock_session = MagicMock()
        mock_get_db.return_value = iter([mock_session])
        mock_uow_instance = MagicMock()
        mock_uow_cls.return_value = mock_uow_instance

        from src.container import get_uow

        with app.test_request_context():
            result = get_uow()

            assert result is mock_uow_instance
            mock_get_db.assert_called_once()
            mock_uow_cls.assert_called_once_with(mock_session)

    @patch('src.container.UnitOfWork')
    @patch('src.container.get_db')
    def test_reuses_uow_on_second_call(self, mock_get_db, mock_uow_cls, app):
        """Should reuse the same UnitOfWork on subsequent calls in the same request."""
        mock_session = MagicMock()
        mock_get_db.return_value = iter([mock_session])
        mock_uow_instance = MagicMock()
        mock_uow_cls.return_value = mock_uow_instance

        from src.container import get_uow

        with app.test_request_context():
            first = get_uow()
            second = get_uow()

            assert first is second
            # get_db should only be called once (cached in g)
            mock_get_db.assert_called_once()
            mock_uow_cls.assert_called_once()


class TestGetInspectionDataService:
    """Tests for get_inspection_data_service() factory function."""

    @patch('src.container.get_uow')
    def test_returns_inspection_data_service(self, mock_get_uow, app):
        """Should return an InspectionDataService with the UoW."""
        mock_uow = MagicMock()
        mock_get_uow.return_value = mock_uow

        from src.container import get_inspection_data_service
        from src.application.inspection_data_service import InspectionDataService

        with app.test_request_context():
            result = get_inspection_data_service()

            assert isinstance(result, InspectionDataService)
            assert result._uow is mock_uow


class TestGetDashboardService:
    """Tests for get_dashboard_service() factory function."""

    @patch('src.container.get_uow')
    def test_returns_dashboard_service(self, mock_get_uow, app):
        """Should return a DashboardService with the UoW."""
        mock_uow = MagicMock()
        mock_get_uow.return_value = mock_uow

        from src.container import get_dashboard_service
        from src.application.dashboard_service import DashboardService

        with app.test_request_context():
            result = get_dashboard_service()

            assert isinstance(result, DashboardService)
            assert result._uow is mock_uow


class TestGetUploadService:
    """Tests for get_upload_service() factory function."""

    @patch('src.container.get_uow')
    def test_returns_upload_service(self, mock_get_uow, app):
        """Should return an UploadService with UoW, processor, and file_validator."""
        import sys

        mock_uow = MagicMock()
        mock_get_uow.return_value = mock_uow

        mock_file_validator_cls = MagicMock()
        mock_validator_instance = MagicMock()
        mock_file_validator_cls.create_pdf_validator.return_value = mock_validator_instance

        mock_processor_mod = MagicMock()
        mock_validators_mod = MagicMock()
        mock_validators_mod.FileValidator = mock_file_validator_cls

        from src.container import get_upload_service
        from src.application.upload_service import UploadService

        with app.test_request_context():
            with patch.dict(sys.modules, {
                'src.domain.validators': mock_validators_mod,
                'src.domain': MagicMock(),
            }):
                result = get_upload_service()

                assert isinstance(result, UploadService)
                assert result._uow is mock_uow
                assert result._processor is not None

    @patch('src.container.get_uow')
    def test_upload_service_uses_pdf_validator(self, mock_get_uow, app):
        """Should use a PDF validator created via FileValidator.create_pdf_validator."""
        import sys

        mock_uow = MagicMock()
        mock_get_uow.return_value = mock_uow

        mock_file_validator_cls = MagicMock()
        mock_validator_instance = MagicMock()
        mock_file_validator_cls.create_pdf_validator.return_value = mock_validator_instance

        mock_validators_mod = MagicMock()
        mock_validators_mod.FileValidator = mock_file_validator_cls

        from src.container import get_upload_service

        with app.test_request_context():
            with patch.dict(sys.modules, {
                'src.domain.validators': mock_validators_mod,
                'src.domain': MagicMock(),
            }):
                result = get_upload_service()

                mock_file_validator_cls.create_pdf_validator.assert_called_once()
                assert result._validator is mock_validator_instance


class TestGetPlanService:
    """Tests for get_plan_service() factory function."""

    @patch('src.container.get_uow')
    def test_returns_plan_service(self, mock_get_uow, app):
        """Should return a PlanService with UoW."""
        mock_uow = MagicMock()
        mock_get_uow.return_value = mock_uow

        from src.container import get_plan_service
        from src.application.plan_service import PlanService

        with app.test_request_context():
            result = get_plan_service()

            assert isinstance(result, PlanService)
            assert result._uow is mock_uow

    @patch('src.container.get_uow')
    def test_plan_service_with_pdf_service(self, mock_get_uow, app):
        """Should pass pdf_service from current_app when available."""
        mock_uow = MagicMock()
        mock_get_uow.return_value = mock_uow
        mock_pdf_svc = MagicMock()

        from src.container import get_plan_service

        with app.test_request_context():
            app.pdf_service = mock_pdf_svc
            try:
                result = get_plan_service()
                assert result._pdf_service is mock_pdf_svc
            finally:
                # Clean up attribute so it doesn't leak to other tests
                if hasattr(app, 'pdf_service'):
                    delattr(app, 'pdf_service')

    @patch('src.container.get_uow')
    def test_plan_service_without_pdf_service(self, mock_get_uow, app):
        """Should set pdf_service to None when not available on current_app."""
        mock_uow = MagicMock()
        mock_get_uow.return_value = mock_uow

        from src.container import get_plan_service

        # Ensure pdf_service is not set on app
        if hasattr(app, 'pdf_service'):
            delattr(app, 'pdf_service')

        with app.test_request_context():
            result = get_plan_service()
            assert result._pdf_service is None


class TestGetAdminService:
    """Tests for get_admin_service() factory function."""

    @patch('src.container.get_uow')
    def test_returns_admin_service(self, mock_get_uow, app):
        """Should return an AdminService with UoW."""
        mock_uow = MagicMock()
        mock_get_uow.return_value = mock_uow

        from src.container import get_admin_service
        from src.application.admin_service import AdminService

        with app.test_request_context():
            result = get_admin_service()

            assert isinstance(result, AdminService)
            assert result._uow is mock_uow

    @patch('src.container.get_uow')
    def test_admin_service_with_drive_and_email(self, mock_get_uow, app):
        """Should pass drive_service and email_service from current_app."""
        mock_uow = MagicMock()
        mock_get_uow.return_value = mock_uow
        mock_drive = MagicMock()
        mock_email = MagicMock()

        from src.container import get_admin_service

        with app.test_request_context():
            app.drive_service = mock_drive
            app.email_service = mock_email
            try:
                result = get_admin_service()
                assert result._drive_service is mock_drive
                assert result._email_service is mock_email
            finally:
                if hasattr(app, 'drive_service'):
                    delattr(app, 'drive_service')
                if hasattr(app, 'email_service'):
                    delattr(app, 'email_service')

    @patch('src.container.get_uow')
    def test_admin_service_without_optional_services(self, mock_get_uow, app):
        """Should set drive_service and email_service to None when not available."""
        mock_uow = MagicMock()
        mock_get_uow.return_value = mock_uow

        from src.container import get_admin_service

        # Ensure optional services are not set on app
        for attr in ('drive_service', 'email_service'):
            if hasattr(app, attr):
                delattr(app, attr)

        with app.test_request_context():
            result = get_admin_service()
            assert result._drive_service is None
            assert result._email_service is None


class TestGetTrackerService:
    """Tests for get_tracker_service() factory function."""

    def test_returns_tracker_service(self, app):
        """Should return a TrackerService instance (stateless, no UoW)."""
        from src.container import get_tracker_service
        from src.application.tracker_service import TrackerService

        with app.test_request_context():
            result = get_tracker_service()
            assert isinstance(result, TrackerService)

    def test_returns_new_instance_each_call(self, app):
        """Should return a new TrackerService instance each time."""
        from src.container import get_tracker_service

        with app.test_request_context():
            first = get_tracker_service()
            second = get_tracker_service()
            # TrackerService is stateless so each call creates a new instance
            assert first is not second


class TestTeardownUow:
    """Tests for teardown_uow() teardown handler."""

    def test_closes_uow_without_exception(self, app):
        """Should close the UoW when no exception occurred."""
        mock_uow = MagicMock()

        from src.container import teardown_uow
        from flask import g

        with app.test_request_context():
            g.uow = mock_uow

            teardown_uow(exception=None)

            mock_uow.close.assert_called_once()
            mock_uow.rollback.assert_not_called()

    def test_rollback_and_close_on_exception(self, app):
        """Should rollback then close the UoW when an exception occurred."""
        mock_uow = MagicMock()

        from src.container import teardown_uow
        from flask import g

        with app.test_request_context():
            g.uow = mock_uow

            teardown_uow(exception=RuntimeError("test error"))

            mock_uow.rollback.assert_called_once()
            mock_uow.close.assert_called_once()

    def test_noop_when_no_uow_in_g(self, app):
        """Should do nothing when no UoW exists in Flask g."""
        from src.container import teardown_uow

        with app.test_request_context():
            # No g.uow set -- should not raise
            teardown_uow(exception=None)

    def test_removes_uow_from_g(self, app):
        """Should remove the UoW from Flask g after teardown."""
        mock_uow = MagicMock()

        from src.container import teardown_uow
        from flask import g

        with app.test_request_context():
            g.uow = mock_uow

            teardown_uow()

            assert 'uow' not in g.__dict__ if hasattr(g, '__dict__') else True
            # Accessing g.uow after pop should raise AttributeError
            with pytest.raises(AttributeError):
                _ = g.uow
