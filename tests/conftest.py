"""
Pytest configuration and fixtures for testing.

This module provides:
- Test client fixture with proper app configuration
- Database fixtures with SQLite in-memory for isolation
- Model factories for creating test data
- Authentication helpers
"""

import sys
from pathlib import Path

# Add project root to Python path so 'src' module can be imported
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest
import os
import uuid
from datetime import datetime
from werkzeug.security import generate_password_hash


# Set testing environment BEFORE importing app
os.environ['TESTING'] = 'true'
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'  # Use in-memory SQLite for tests
os.environ['SECRET_KEY'] = 'test-secret-key-for-testing-only'
os.environ['FLASK_DEBUG'] = 'false'


@pytest.fixture(scope='session')
def app():
    """Create application for testing."""
    from src.app import app as flask_app

    flask_app.config.update({
        'TESTING': True,
        'WTF_CSRF_ENABLED': False,  # Disable CSRF for API testing
        'LOGIN_DISABLED': False,
        'SERVER_NAME': 'localhost.localdomain',
    })

    yield flask_app


@pytest.fixture(scope='function')
def client(app):
    """Create test client for each test function."""
    # Reset rate limiter storage before each test
    try:
        from src.infrastructure.security import limiter
        limiter.reset()
    except Exception:
        pass  # Limiter might not be initialized

    with app.test_client() as test_client:
        with app.app_context():
            yield test_client


@pytest.fixture(scope='function')
def db_session(app):
    """
    Create a fresh database session for each test.

    Uses SQLite in-memory database for isolation.
    Tables are created fresh for each test.
    """
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker, scoped_session
    from sqlalchemy.dialects.postgresql import JSONB
    from sqlalchemy import JSON
    from src.models_db import Base

    # Create in-memory SQLite engine
    engine = create_engine('sqlite:///:memory:', echo=False)

    # Map JSONB -> JSON for SQLite compatibility
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        pass  # SQLite pragmas if needed

    # Replace JSONB with JSON for SQLite before creating tables
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, JSONB):
                column.type = JSON()

    # Create all tables
    Base.metadata.create_all(engine)

    # Create session
    Session = scoped_session(sessionmaker(bind=engine))
    session = Session()

    yield session

    # Cleanup
    session.rollback()
    session.close()
    Session.remove()


@pytest.fixture
def auth_client(client, db_session):
    """
    Create a test client with an authenticated user.

    Returns a tuple of (client, user) where user is a logged-in consultant.
    """
    from src.models_db import User, UserRole, Company, Establishment

    # Create test company
    company = Company(
        id=uuid.uuid4(),
        name='Test Company',
        cnpj='12345678000199',
        is_active=True
    )
    db_session.add(company)

    # Create test establishment
    establishment = Establishment(
        id=uuid.uuid4(),
        company_id=company.id,
        name='Test Establishment',
        code='TEST001',
        is_active=True
    )
    db_session.add(establishment)

    # Create test user
    user = User(
        id=uuid.uuid4(),
        email='test@example.com',
        password_hash=generate_password_hash('testpassword'),
        name='Test User',
        role=UserRole.CONSULTANT,
        company_id=company.id,
        is_active=True
    )
    user.establishments.append(establishment)
    db_session.add(user)
    db_session.commit()

    # Login the user
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True

    return client, user


@pytest.fixture
def manager_client(client, db_session):
    """
    Create a test client with an authenticated manager.
    """
    from src.models_db import User, UserRole, Company

    company = Company(
        id=uuid.uuid4(),
        name='Manager Company',
        cnpj='98765432000111',
        is_active=True
    )
    db_session.add(company)

    user = User(
        id=uuid.uuid4(),
        email='manager@example.com',
        password_hash=generate_password_hash('managerpass'),
        name='Test Manager',
        role=UserRole.MANAGER,
        company_id=company.id,
        is_active=True
    )
    db_session.add(user)
    db_session.commit()

    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True

    return client, user


@pytest.fixture
def admin_client(client, db_session):
    """
    Create a test client with an authenticated admin.
    """
    from src.models_db import User, UserRole

    user = User(
        id=uuid.uuid4(),
        email='admin@example.com',
        password_hash=generate_password_hash('adminpass'),
        name='Test Admin',
        role=UserRole.ADMIN,
        is_active=True
    )
    db_session.add(user)
    db_session.commit()

    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True

    return client, user


# ============ Test Data Factories ============

class UserFactory:
    """Factory for creating test users."""

    @staticmethod
    def create(db_session, **kwargs):
        from src.models_db import User, UserRole

        defaults = {
            'id': uuid.uuid4(),
            'email': f'user_{uuid.uuid4().hex[:8]}@example.com',
            'password_hash': generate_password_hash('password123'),
            'name': 'Test User',
            'role': UserRole.CONSULTANT,
            'is_active': True
        }
        defaults.update(kwargs)

        user = User(**defaults)
        db_session.add(user)
        db_session.commit()
        return user


class CompanyFactory:
    """Factory for creating test companies."""

    @staticmethod
    def create(db_session, **kwargs):
        from src.models_db import Company

        defaults = {
            'id': uuid.uuid4(),
            'name': f'Company {uuid.uuid4().hex[:8]}',
            'cnpj': f'{uuid.uuid4().int % 100000000000000:014d}',
            'is_active': True
        }
        defaults.update(kwargs)

        company = Company(**defaults)
        db_session.add(company)
        db_session.commit()
        return company


class EstablishmentFactory:
    """Factory for creating test establishments."""

    @staticmethod
    def create(db_session, company=None, **kwargs):
        from src.models_db import Establishment

        if company is None:
            company = CompanyFactory.create(db_session)

        defaults = {
            'id': uuid.uuid4(),
            'company_id': company.id,
            'name': f'Establishment {uuid.uuid4().hex[:8]}',
            'code': f'EST{uuid.uuid4().hex[:6].upper()}',
            'is_active': True
        }
        defaults.update(kwargs)

        establishment = Establishment(**defaults)
        db_session.add(establishment)
        db_session.commit()
        return establishment


class InspectionFactory:
    """Factory for creating test inspections."""

    @staticmethod
    def create(db_session, establishment=None, **kwargs):
        from src.models_db import Inspection, InspectionStatus

        if establishment is None:
            establishment = EstablishmentFactory.create(db_session)

        defaults = {
            'id': uuid.uuid4(),
            'drive_file_id': f'upload:{uuid.uuid4()}',
            'status': InspectionStatus.PENDING_MANAGER_REVIEW,
            'establishment_id': establishment.id
        }
        defaults.update(kwargs)

        inspection = Inspection(**defaults)
        db_session.add(inspection)
        db_session.commit()
        return inspection


class ActionPlanFactory:
    """Factory for creating test action plans."""

    @staticmethod
    def create(db_session, inspection=None, **kwargs):
        from src.models_db import ActionPlan

        if inspection is None:
            inspection = InspectionFactory.create(db_session)

        defaults = {
            'id': uuid.uuid4(),
            'inspection_id': inspection.id,
            'summary_text': 'Resumo do plano de ação de teste',
            'strengths_text': 'Pontos fortes identificados',
            'stats_json': {
                'total_items': 3,
                'total_nc': 2,
                'score': 7,
                'max_score': 10,
                'percentage': 70.0,
                'by_sector': {
                    'Cozinha': {'score': 3, 'max_score': 5, 'percentage': 60.0, 'nc_count': 1},
                    'Estoque': {'score': 4, 'max_score': 5, 'percentage': 80.0, 'nc_count': 1},
                }
            }
        }
        defaults.update(kwargs)

        plan = ActionPlan(**defaults)
        db_session.add(plan)
        db_session.commit()
        return plan


class ActionPlanItemFactory:
    """Factory for creating test action plan items."""

    @staticmethod
    def create(db_session, action_plan=None, **kwargs):
        from src.models_db import ActionPlanItem, ActionPlanItemStatus, SeverityLevel

        if action_plan is None:
            action_plan = ActionPlanFactory.create(db_session)

        defaults = {
            'id': uuid.uuid4(),
            'action_plan_id': action_plan.id,
            'problem_description': 'Problema de teste encontrado na inspeção',
            'corrective_action': 'Ação corretiva sugerida para o problema',
            'legal_basis': 'RDC 216/2004 Art. 5',
            'severity': SeverityLevel.MEDIUM,
            'status': ActionPlanItemStatus.OPEN,
            'sector': 'Cozinha',
            'order_index': 0,
            'original_status': 'Não Conforme',
            'original_score': 0.0,
            'ai_suggested_deadline': '7 dias',
        }
        defaults.update(kwargs)

        item = ActionPlanItem(**defaults)
        db_session.add(item)
        db_session.commit()
        return item


@pytest.fixture
def user_factory():
    """Fixture that returns the UserFactory class."""
    return UserFactory


@pytest.fixture
def company_factory():
    """Fixture that returns the CompanyFactory class."""
    return CompanyFactory


@pytest.fixture
def establishment_factory():
    """Fixture that returns the EstablishmentFactory class."""
    return EstablishmentFactory


@pytest.fixture
def inspection_factory():
    """Fixture that returns the InspectionFactory class."""
    return InspectionFactory


@pytest.fixture
def action_plan_factory():
    """Fixture that returns the ActionPlanFactory class."""
    return ActionPlanFactory


@pytest.fixture
def action_plan_item_factory():
    """Fixture that returns the ActionPlanItemFactory class."""
    return ActionPlanItemFactory


# ============ Mock Fixtures ============

@pytest.fixture
def mock_drive_service(app):
    """Mock drive_service to avoid real Google Drive calls."""
    from unittest.mock import MagicMock, patch

    mock_drive = MagicMock()
    mock_drive.service = MagicMock()
    mock_drive.read_json.return_value = {}
    mock_drive.create_folder.return_value = ('mock-folder-id', 'https://drive.google.com/mock')
    mock_drive.delete_folder.return_value = True
    mock_drive.upload_file.return_value = 'mock-file-id'

    with patch('src.admin_routes.drive_service', mock_drive), \
         patch('src.app.drive_service', mock_drive):
        yield mock_drive


@pytest.fixture
def mock_processor():
    """Mock processor_service to avoid real AI processing."""
    from unittest.mock import MagicMock, patch

    mock_proc = MagicMock()
    mock_proc.process_single_file.return_value = {
        'status': 'success',
        'file_id': 'mock-output-id',
        'title': 'Relatório de Inspeção - Teste',
        'summary': 'Resumo do teste',
    }

    with patch('src.app.processor_service', mock_proc):
        yield mock_proc


# ============ Full Data Fixtures ============

@pytest.fixture
def full_inspection_data(db_session):
    """Create a complete inspection with action plan and items for testing."""
    from src.models_db import (
        Company, Establishment, User, UserRole, Inspection, InspectionStatus,
        ActionPlan, ActionPlanItem, ActionPlanItemStatus, SeverityLevel
    )

    company = CompanyFactory.create(db_session, name='Test Corp')
    establishment = EstablishmentFactory.create(db_session, company=company, name='Restaurante Teste')

    consultant = UserFactory.create(
        db_session,
        email='consultant-full@test.com',
        name='Consultor Teste',
        role=UserRole.CONSULTANT,
        company_id=company.id,
    )
    # Link consultant to establishment
    consultant.establishments.append(establishment)
    db_session.commit()

    manager = UserFactory.create(
        db_session,
        email='manager-full@test.com',
        name='Gestor Teste',
        role=UserRole.MANAGER,
        company_id=company.id,
    )

    inspection = InspectionFactory.create(
        db_session,
        establishment=establishment,
        drive_file_id=f'test-file-{uuid.uuid4().hex[:8]}',
        status=InspectionStatus.PENDING_MANAGER_REVIEW,
    )

    plan = ActionPlanFactory.create(db_session, inspection=inspection)

    items = []
    for i, (sector, problem, status) in enumerate([
        ('Cozinha', 'Bancadas sem higienização adequada', 'Não Conforme'),
        ('Cozinha', 'Lixeiras sem tampa e pedal', 'Parcialmente Conforme'),
        ('Estoque', 'Produtos sem rotulagem', 'Não Conforme'),
    ]):
        item = ActionPlanItemFactory.create(
            db_session,
            action_plan=plan,
            problem_description=problem,
            corrective_action=f'Ação corretiva para: {problem}',
            sector=sector,
            order_index=i,
            original_status=status,
            original_score=0.0 if status == 'Não Conforme' else 5.0,
        )
        items.append(item)

    return {
        'company': company,
        'establishment': establishment,
        'consultant': consultant,
        'manager': manager,
        'inspection': inspection,
        'action_plan': plan,
        'items': items,
    }


# ============ Helper Functions ============

def create_test_pdf_content():
    """Create minimal valid PDF content for testing."""
    return b'%PDF-1.4\n1 0 obj\n<<>>\nendobj\nxref\n0 1\n0000000000 65535 f \ntrailer\n<<>>\nstartxref\n9\n%%EOF'


def create_test_png_content():
    """Create minimal valid PNG content for testing."""
    return b'\x89PNG\r\n\x1a\n' + b'\x00' * 100


def create_test_jpg_content():
    """Create minimal valid JPEG content for testing."""
    return b'\xff\xd8\xff\xe0' + b'\x00' * 100


@pytest.fixture
def test_pdf():
    """Fixture that returns test PDF content."""
    return create_test_pdf_content()


@pytest.fixture
def test_png():
    """Fixture that returns test PNG content."""
    return create_test_png_content()


@pytest.fixture
def test_jpg():
    """Fixture that returns test JPEG content."""
    return create_test_jpg_content()


# Alias for 'db_session' - some tests use 'session' name
@pytest.fixture
def session(db_session):
    """Alias for db_session fixture."""
    return db_session


def pytest_configure(config):
    """Configure custom markers."""
    config.addinivalue_line(
        "markers", "requires_postgres: mark test as requiring PostgreSQL (skip on SQLite)"
    )


@pytest.fixture(autouse=True)
def skip_if_sqlite_and_requires_postgres(request):
    """
    Skip tests marked with 'requires_postgres' when using SQLite.

    Integration tests using full database features (JSONB, etc.) need PostgreSQL.
    """
    marker = request.node.get_closest_marker('requires_postgres')
    if marker:
        # Check if we're using SQLite
        db_url = os.environ.get('DATABASE_URL', '')
        if db_url.startswith('sqlite'):
            pytest.skip("Test requires PostgreSQL (SQLite doesn't support JSONB)")
