"""Tests for InspectionDataService - the CRITICAL unified rebuild logic."""
import pytest
import uuid
from unittest.mock import MagicMock

from src.application.inspection_data_service import InspectionDataService
from src.repositories.unit_of_work import UnitOfWork
from src.models_db import ActionPlanItemStatus, SeverityLevel


class TestInspectionDataService:

    @pytest.fixture
    def service_with_data(self, db_session, inspection_factory,
                          action_plan_factory, action_plan_item_factory):
        """Create service with a real DB inspection + plan + items."""
        inspection = inspection_factory.create(
            db_session,
            drive_file_id='test-rebuild-file',
            ai_raw_response={
                'nome_estabelecimento': 'Restaurante Teste',
                'pontuacao_geral': 7,
                'pontuacao_maxima_geral': 10,
                'aproveitamento_geral': 70.0,
                'areas_inspecionadas': [
                    {
                        'nome_area': 'Cozinha',
                        'pontuacao_obtida': 3,
                        'pontuacao_maxima': 5,
                        'aproveitamento': 60.0,
                        'itens': [
                            {
                                'item_verificado': 'Higienização de bancadas',
                                'status': 'Não Conforme',
                                'observacao': 'Bancadas sujas',
                                'pontuacao': 0,
                            },
                            {
                                'item_verificado': 'Organização de utensílios',
                                'status': 'Conforme',
                                'observacao': 'OK',
                                'pontuacao': 10,
                            },
                        ],
                    },
                    {
                        'nome_area': 'Estoque',
                        'pontuacao_obtida': 4,
                        'pontuacao_maxima': 5,
                        'aproveitamento': 80.0,
                        'itens': [
                            {
                                'item_verificado': 'Rotulagem de produtos',
                                'status': 'Parcialmente Conforme',
                                'observacao': 'Alguns sem rótulo',
                                'pontuacao': 5,
                            },
                        ],
                    },
                ],
            },
        )

        plan = action_plan_factory.create(db_session, inspection=inspection)

        items = []
        # Item 0: NC in Cozinha
        items.append(action_plan_item_factory.create(
            db_session, action_plan=plan,
            problem_description='Bancadas sem higienização adequada',
            corrective_action='Higienizar bancadas diariamente',
            sector='Cozinha',
            order_index=0,
            original_status='Não Conforme',
            original_score=0.0,
            severity=SeverityLevel.HIGH,
        ))
        # Item 1: Partial in Estoque
        items.append(action_plan_item_factory.create(
            db_session, action_plan=plan,
            problem_description='Produtos sem rotulagem',
            corrective_action='Rotular todos os produtos',
            sector='Estoque',
            order_index=0,
            original_status='Parcialmente Conforme',
            original_score=5.0,
            severity=SeverityLevel.MEDIUM,
        ))

        uow = UnitOfWork(db_session)
        svc = InspectionDataService(uow)

        return {
            'service': svc,
            'inspection': inspection,
            'plan': plan,
            'items': items,
        }

    def test_get_review_data_returns_data(self, service_with_data):
        svc = service_with_data['service']
        result = svc.get_review_data('test-rebuild-file')

        assert result is not None
        assert result['inspection'] is not None
        assert result['plan'] is not None
        assert len(result['areas']) > 0

    def test_get_review_data_not_found(self, db_session):
        uow = UnitOfWork(db_session)
        svc = InspectionDataService(uow)
        result = svc.get_review_data('nonexistent-file')
        assert result is None

    def test_rebuild_creates_correct_areas(self, service_with_data):
        svc = service_with_data['service']
        result = svc.get_review_data('test-rebuild-file', filter_compliant=False)

        areas = result['areas']
        area_names = [a['nome_area'] for a in areas]
        assert 'Cozinha' in area_names
        assert 'Estoque' in area_names

    def test_rebuild_items_have_required_fields(self, service_with_data):
        svc = service_with_data['service']
        result = svc.get_review_data('test-rebuild-file', filter_compliant=False)

        for area in result['areas']:
            for item in area['itens']:
                assert 'item_verificado' in item
                assert 'status' in item
                assert 'acao_corretiva_sugerida' in item
                assert 'pontuacao' in item
                assert 'id' in item

    def test_status_normalization(self, service_with_data):
        svc = service_with_data['service']
        result = svc.get_review_data('test-rebuild-file', filter_compliant=False)

        statuses = []
        for area in result['areas']:
            for item in area['itens']:
                statuses.append(item['status'])

        assert 'Não Conforme' in statuses
        assert 'Parcialmente Conforme' in statuses

    def test_filter_compliant_skips_conforme(self, service_with_data):
        svc = service_with_data['service']

        # Without filter - should have both NC and partial
        result_all = svc.get_review_data('test-rebuild-file', filter_compliant=False)
        all_items = sum(len(a['itens']) for a in result_all['areas'])

        # With filter - should exclude 'Conforme' items
        result_filtered = svc.get_review_data('test-rebuild-file', filter_compliant=True)
        filtered_items = sum(len(a['itens']) for a in result_filtered['areas'])

        # Both our DB items are NC/Partial, so count should be same
        # (Conforme items are in AI data but not in DB items)
        assert filtered_items == all_items

    def test_nc_count_per_area(self, service_with_data):
        svc = service_with_data['service']
        result = svc.get_review_data('test-rebuild-file', filter_compliant=False)

        for area in result['areas']:
            if area['nome_area'] == 'Cozinha':
                assert area['items_nc'] >= 1
            if area['nome_area'] == 'Estoque':
                assert area['items_nc'] >= 1

    def test_get_pdf_data_includes_status_plano(self, service_with_data):
        svc = service_with_data['service']
        result = svc.get_pdf_data('test-rebuild-file')

        assert 'status_plano' in result
        assert result['status_plano'] in ['EM APROVAÇÃO', 'AGUARDANDO VISITA', 'CONCLUÍDO']

    def test_get_plan_edit_data_no_filter(self, service_with_data):
        svc = service_with_data['service']
        result = svc.get_plan_edit_data('test-rebuild-file')

        assert result is not None
        # Plan edit should not filter any items
        total_items = sum(len(a['itens']) for a in result['areas'])
        assert total_items >= 2

    def test_normalize_status_nao_conforme(self):
        assert InspectionDataService._normalize_status('Não Conforme') == 'Não Conforme'
        assert InspectionDataService._normalize_status('nao conforme') == 'Não Conforme'

    def test_normalize_status_parcial(self):
        assert InspectionDataService._normalize_status('Parcialmente Conforme') == 'Parcialmente Conforme'
        assert InspectionDataService._normalize_status('parcial') == 'Parcialmente Conforme'

    def test_normalize_status_conforme(self):
        assert InspectionDataService._normalize_status('Conforme') == 'Conforme'
        assert InspectionDataService._normalize_status('conforme') == 'Conforme'
