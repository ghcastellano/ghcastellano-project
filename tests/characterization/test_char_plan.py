"""
Characterization tests for plan management flow.

Captures current behavior of plan editing, saving, and approval by managers.
"""
import pytest
import uuid
from unittest.mock import patch, MagicMock


@pytest.fixture
def plan_data(client, db_session):
    """Create inspection with full action plan for manager testing."""
    from src.models_db import (
        Company, Establishment, User, UserRole, Inspection, InspectionStatus,
    )
    from werkzeug.security import generate_password_hash
    from tests.conftest import (
        CompanyFactory, EstablishmentFactory, UserFactory,
        InspectionFactory, ActionPlanFactory, ActionPlanItemFactory,
    )

    company = CompanyFactory.create(db_session, name='Plan Test Co')
    est = EstablishmentFactory.create(db_session, company=company, name='Restaurante Plan')

    manager = UserFactory.create(
        db_session,
        email='manager-plan@test.com',
        name='Gestor Plan',
        role=UserRole.MANAGER,
        company_id=company.id,
    )

    inspection = InspectionFactory.create(
        db_session,
        establishment=est,
        drive_file_id=f'plan-{uuid.uuid4().hex[:8]}',
        status=InspectionStatus.PENDING_MANAGER_REVIEW,
    )

    plan = ActionPlanFactory.create(db_session, inspection=inspection)

    items = []
    for i, (sector, problem) in enumerate([
        ('Cozinha', 'Problema na cozinha'),
        ('Estoque', 'Problema no estoque'),
    ]):
        item = ActionPlanItemFactory.create(
            db_session,
            action_plan=plan,
            problem_description=problem,
            corrective_action=f'Corrigir: {problem}',
            sector=sector,
            order_index=i,
        )
        items.append(item)

    with client.session_transaction() as sess:
        sess['_user_id'] = str(manager.id)
        sess['_fresh'] = True

    return {
        'client': client,
        'manager': manager,
        'company': company,
        'establishment': est,
        'inspection': inspection,
        'plan': plan,
        'items': items,
        'db_session': db_session,
    }


class TestPlanEditPage:
    """Tests for GET /manager/plan/<file_id>"""

    def test_plan_edit_requires_login(self, client):
        response = client.get('/manager/plan/some-file-id')
        assert response.status_code in [302, 401]

    @pytest.mark.requires_postgres
    def test_plan_edit_loads_for_valid_inspection(self, plan_data):
        client = plan_data['client']
        file_id = plan_data['inspection'].drive_file_id

        with patch('src.manager_routes.drive_service') as mock_drive:
            mock_drive.read_json.return_value = {
                'nome_estabelecimento': 'Restaurante Plan',
                'pontuacao_geral': 7,
                'pontuacao_maxima_geral': 10,
                'aproveitamento_geral': 70.0,
                'areas_inspecionadas': [],
            }
            mock_drive.service = MagicMock()

            response = client.get(f'/manager/plan/{file_id}')
            assert response.status_code == 200

    @pytest.mark.requires_postgres
    def test_plan_edit_nonexistent_file(self, plan_data):
        client = plan_data['client']
        response = client.get('/manager/plan/nonexistent-id')
        # Should redirect or show error
        assert response.status_code in [200, 302, 404]


class TestPlanSave:
    """Tests for POST /manager/plan/<file_id>/save"""

    def test_plan_save_requires_login(self, client):
        response = client.post('/manager/plan/some-id/save',
            json={}, headers={'Content-Type': 'application/json'})
        assert response.status_code in [302, 401]

    @pytest.mark.requires_postgres
    def test_plan_save_updates_items(self, plan_data):
        client = plan_data['client']
        file_id = plan_data['inspection'].drive_file_id
        item = plan_data['items'][0]

        with patch('src.manager_routes.drive_service') as mock_drive, \
             patch('src.manager_routes.pdf_service') as mock_pdf, \
             patch('src.manager_routes.storage_service') as mock_storage:

            mock_drive.read_json.return_value = {'areas_inspecionadas': []}
            mock_pdf.generate_pdf_bytes.return_value = b'%PDF-mock'
            mock_storage.upload_file.return_value = 'https://mock-url/plan.pdf'

            response = client.post(f'/manager/plan/{file_id}/save',
                json={
                    'items': [{
                        'id': str(item.id),
                        'problem_description': 'Problema editado',
                        'corrective_action': 'Ação editada',
                    }],
                    'summary': 'Resumo editado',
                },
                headers={'Content-Type': 'application/json'})
            assert response.status_code in [200, 302]


class TestPlanApproval:
    """Tests for POST /manager/plan/<file_id>/approve"""

    def test_approve_requires_login(self, client):
        response = client.post('/manager/plan/some-id/approve',
            json={}, headers={'Content-Type': 'application/json'})
        assert response.status_code in [302, 401]

    @pytest.mark.requires_postgres
    def test_approve_plan(self, plan_data):
        client = plan_data['client']
        file_id = plan_data['inspection'].drive_file_id

        with patch('src.manager_routes.drive_service') as mock_drive, \
             patch('src.manager_routes.pdf_service') as mock_pdf, \
             patch('src.manager_routes.storage_service') as mock_storage:

            mock_drive.read_json.return_value = {'areas_inspecionadas': []}
            mock_pdf.generate_pdf_bytes.return_value = b'%PDF-mock'
            mock_storage.upload_file.return_value = 'https://mock-url/plan.pdf'

            response = client.post(f'/manager/plan/{file_id}/approve',
                json={},
                headers={'Content-Type': 'application/json'})
            assert response.status_code in [200, 302]


class TestManagerDashboard:
    """Tests for GET /dashboard/manager"""

    def test_dashboard_requires_login(self, client):
        response = client.get('/dashboard/manager')
        assert response.status_code in [302, 401]

    @pytest.mark.requires_postgres
    def test_dashboard_loads_for_manager(self, plan_data):
        client = plan_data['client']
        response = client.get('/dashboard/manager')
        assert response.status_code == 200
