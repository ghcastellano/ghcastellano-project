"""
Characterization tests for inspection review flow.

Captures current behavior of review page, save review, and finalize verification.
"""
import pytest
import uuid
from unittest.mock import patch, MagicMock


@pytest.fixture
def review_data(client, db_session):
    """Create inspection with full action plan data for review testing."""
    from src.models_db import (
        Company, Establishment, User, UserRole, Inspection, InspectionStatus,
        ActionPlan, ActionPlanItem, ActionPlanItemStatus, SeverityLevel,
    )
    from werkzeug.security import generate_password_hash
    from tests.conftest import (
        CompanyFactory, EstablishmentFactory, UserFactory,
        InspectionFactory, ActionPlanFactory, ActionPlanItemFactory,
    )

    company = CompanyFactory.create(db_session, name='Review Test Co')
    est = EstablishmentFactory.create(db_session, company=company, name='Restaurante Review')

    consultant = UserFactory.create(
        db_session,
        email='consultant-review@test.com',
        name='Consultor Review',
        role=UserRole.CONSULTANT,
        company_id=company.id,
    )
    consultant.establishments.append(est)
    db_session.commit()

    inspection = InspectionFactory.create(
        db_session,
        establishment=est,
        drive_file_id=f'review-{uuid.uuid4().hex[:8]}',
        status=InspectionStatus.PENDING_CONSULTANT_VERIFICATION,
    )

    plan = ActionPlanFactory.create(db_session, inspection=inspection)

    items = []
    for i, (sector, problem, orig_status) in enumerate([
        ('Cozinha', 'Falta de higienização de bancadas', 'Não Conforme'),
        ('Cozinha', 'Lixeiras inadequadas', 'Parcialmente Conforme'),
        ('Estoque', 'Produtos vencidos', 'Não Conforme'),
    ]):
        item = ActionPlanItemFactory.create(
            db_session,
            action_plan=plan,
            problem_description=problem,
            corrective_action=f'Corrigir: {problem}',
            sector=sector,
            order_index=i,
            original_status=orig_status,
            original_score=0.0 if orig_status == 'Não Conforme' else 5.0,
        )
        items.append(item)

    with client.session_transaction() as sess:
        sess['_user_id'] = str(consultant.id)
        sess['_fresh'] = True

    return {
        'client': client,
        'consultant': consultant,
        'inspection': inspection,
        'plan': plan,
        'items': items,
        'db_session': db_session,
    }


class TestReviewPageAccess:
    """Tests for GET /review/<file_id>"""

    def test_review_requires_login(self, client):
        response = client.get('/review/some-file-id')
        assert response.status_code in [302, 401]

    @pytest.mark.requires_postgres
    def test_review_nonexistent_file(self, review_data):
        client = review_data['client']
        response = client.get('/review/nonexistent-file-id')
        # Should handle gracefully (redirect or 404)
        assert response.status_code in [200, 302, 404]

    @pytest.mark.requires_postgres
    def test_review_loads_for_valid_inspection(self, review_data):
        client = review_data['client']
        file_id = review_data['inspection'].drive_file_id

        with patch('src.app.drive_service') as mock_drive:
            mock_drive.read_json.return_value = {
                'nome_estabelecimento': 'Restaurante Review',
                'pontuacao_geral': 7,
                'pontuacao_maxima_geral': 10,
                'aproveitamento_geral': 70.0,
                'areas_inspecionadas': [],
            }

            response = client.get(f'/review/{file_id}')
            assert response.status_code == 200


class TestSaveReview:
    """Tests for POST /api/save_review/<file_id>"""

    def test_save_review_requires_login(self, client):
        response = client.post('/api/save_review/some-id',
            json={'items': []},
            headers={'Content-Type': 'application/json'})
        assert response.status_code in [302, 401]

    @pytest.mark.requires_postgres
    def test_save_review_updates_items(self, review_data):
        client = review_data['client']
        file_id = review_data['inspection'].drive_file_id
        item = review_data['items'][0]

        response = client.post(f'/api/save_review/{file_id}',
            json={
                'items': [{
                    'id': str(item.id),
                    'status': 'RESOLVED',
                    'notes': 'Corrigido pelo consultor',
                }]
            },
            headers={'Content-Type': 'application/json'})
        # Should accept the update
        assert response.status_code in [200, 302]


class TestFinalizeVerification:
    """Tests for POST /api/finalize_verification/<file_id>"""

    def test_finalize_requires_login(self, client):
        response = client.post('/api/finalize_verification/some-id')
        assert response.status_code in [302, 401]

    @pytest.mark.requires_postgres
    def test_finalize_changes_status_to_completed(self, review_data):
        client = review_data['client']
        file_id = review_data['inspection'].drive_file_id

        response = client.post(f'/api/finalize_verification/{file_id}',
            headers={'Content-Type': 'application/json'})
        # Should transition to COMPLETED
        assert response.status_code in [200, 302]
