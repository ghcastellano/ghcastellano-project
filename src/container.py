"""
Simple Dependency Injection container using Flask's g object.

No external DI framework needed - just factory functions that create
services with their dependencies, cached per-request in Flask g.
"""
from flask import g, current_app

from src.database import get_db
from src.repositories.unit_of_work import UnitOfWork


def get_uow() -> UnitOfWork:
    """Get or create UnitOfWork for the current request."""
    if 'uow' not in g:
        db = next(get_db())
        g.uow = UnitOfWork(db)
    return g.uow


def get_inspection_data_service():
    """Get InspectionDataService for the current request."""
    from src.application.inspection_data_service import InspectionDataService
    return InspectionDataService(get_uow())


def get_dashboard_service():
    """Get DashboardService for the current request."""
    from src.application.dashboard_service import DashboardService
    return DashboardService(get_uow())


def get_upload_service():
    """Get UploadService with processor and validator."""
    from src.application.upload_service import UploadService
    from src.services.processor import processor_service
    from src.domain.validators import FileValidator

    return UploadService(
        get_uow(),
        processor=processor_service,
        file_validator=FileValidator.create_pdf_validator(),
    )


def get_plan_service():
    """Get PlanService with PDF and storage services."""
    from src.application.plan_service import PlanService

    pdf_svc = getattr(current_app, 'pdf_service', None)
    storage_svc = None
    try:
        from src.services.storage_service import storage_service
        storage_svc = storage_service
    except Exception:
        pass

    return PlanService(
        get_uow(),
        pdf_service=pdf_svc,
        storage_service=storage_svc,
    )


def get_admin_service():
    """Get AdminService with Drive and email services."""
    from src.application.admin_service import AdminService

    drive_svc = getattr(current_app, 'drive_service', None)
    email_svc = getattr(current_app, 'email_service', None)

    return AdminService(
        get_uow(),
        drive_service=drive_svc,
        email_service=email_svc,
    )


def get_tracker_service():
    """Get TrackerService (stateless, no dependencies)."""
    from src.application.tracker_service import TrackerService
    return TrackerService()


def teardown_uow(exception=None):
    """
    Teardown handler for Flask app context.

    Register with: app.teardown_appcontext(teardown_uow)
    """
    uow = g.pop('uow', None)
    if uow:
        if exception:
            uow.rollback()
        uow.close()
