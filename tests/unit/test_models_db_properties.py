"""Unit tests for SQLAlchemy model properties and legacy adapters in models_db.py.

Covers:
- Inspection template adapter properties (resumo_geral, aproveitamento_geral,
  score_geral_obtido, score_geral_maximo, area_results, action_items, has_been_updated)
- ActionPlanItem legacy property adapters (item_verificado, fundamento_legal,
  acao_corretiva_sugerida, prazo_sugerido) - both getters and setters
"""

import pytest
import uuid
from datetime import date

from tests.conftest import (
    CompanyFactory,
    EstablishmentFactory,
    InspectionFactory,
    ActionPlanFactory,
    ActionPlanItemFactory,
)


# ---------------------------------------------------------------------------
# Inspection model template adapter properties
# ---------------------------------------------------------------------------

class TestResumoGeral:
    """Tests for Inspection.resumo_geral property."""

    def test_resumo_geral_returns_summary_text_when_plan_exists(self, db_session):
        plan = ActionPlanFactory.create(db_session, summary_text='Resumo de teste')
        inspection = plan.inspection
        db_session.refresh(inspection)
        assert inspection.resumo_geral == 'Resumo de teste'

    def test_resumo_geral_returns_na_when_no_plan(self, db_session):
        inspection = InspectionFactory.create(db_session)
        assert inspection.resumo_geral == "N/A"

    def test_resumo_geral_returns_none_summary_when_plan_has_no_text(self, db_session):
        plan = ActionPlanFactory.create(db_session, summary_text=None)
        inspection = plan.inspection
        db_session.refresh(inspection)
        # Property returns action_plan.summary_text which is None
        assert inspection.resumo_geral is None


class TestAproveitamentoGeral:
    """Tests for Inspection.aproveitamento_geral property."""

    def test_returns_percentage_from_stats(self, db_session):
        plan = ActionPlanFactory.create(db_session, stats_json={
            'percentage': 85.0, 'score': 17, 'max_score': 20,
        })
        inspection = plan.inspection
        db_session.refresh(inspection)
        assert inspection.aproveitamento_geral == 85.0

    def test_returns_none_when_no_plan(self, db_session):
        inspection = InspectionFactory.create(db_session)
        assert inspection.aproveitamento_geral is None

    def test_returns_none_when_stats_json_is_none(self, db_session):
        plan = ActionPlanFactory.create(db_session, stats_json=None)
        inspection = plan.inspection
        db_session.refresh(inspection)
        assert inspection.aproveitamento_geral is None

    def test_returns_none_when_percentage_key_missing(self, db_session):
        plan = ActionPlanFactory.create(db_session, stats_json={'score': 5})
        inspection = plan.inspection
        db_session.refresh(inspection)
        assert inspection.aproveitamento_geral is None


class TestScoreGeralObtido:
    """Tests for Inspection.score_geral_obtido property."""

    def test_returns_score_from_stats(self, db_session):
        plan = ActionPlanFactory.create(db_session, stats_json={
            'score': 12, 'max_score': 15, 'percentage': 80.0,
        })
        inspection = plan.inspection
        db_session.refresh(inspection)
        assert inspection.score_geral_obtido == 12

    def test_returns_none_when_no_plan(self, db_session):
        inspection = InspectionFactory.create(db_session)
        assert inspection.score_geral_obtido is None

    def test_returns_none_when_stats_json_is_none(self, db_session):
        plan = ActionPlanFactory.create(db_session, stats_json=None)
        inspection = plan.inspection
        db_session.refresh(inspection)
        assert inspection.score_geral_obtido is None

    def test_returns_none_when_score_key_missing(self, db_session):
        plan = ActionPlanFactory.create(db_session, stats_json={'max_score': 10})
        inspection = plan.inspection
        db_session.refresh(inspection)
        assert inspection.score_geral_obtido is None


class TestScoreGeralMaximo:
    """Tests for Inspection.score_geral_maximo property."""

    def test_returns_max_score_from_stats(self, db_session):
        plan = ActionPlanFactory.create(db_session, stats_json={
            'score': 8, 'max_score': 10, 'percentage': 80.0,
        })
        inspection = plan.inspection
        db_session.refresh(inspection)
        assert inspection.score_geral_maximo == 10

    def test_returns_none_when_no_plan(self, db_session):
        inspection = InspectionFactory.create(db_session)
        assert inspection.score_geral_maximo is None

    def test_returns_none_when_stats_json_is_none(self, db_session):
        plan = ActionPlanFactory.create(db_session, stats_json=None)
        inspection = plan.inspection
        db_session.refresh(inspection)
        assert inspection.score_geral_maximo is None

    def test_returns_none_when_max_score_key_missing(self, db_session):
        plan = ActionPlanFactory.create(db_session, stats_json={'score': 5})
        inspection = plan.inspection
        db_session.refresh(inspection)
        assert inspection.score_geral_maximo is None


class TestAreaResults:
    """Tests for Inspection.area_results property."""

    def test_returns_empty_list_when_no_plan(self, db_session):
        inspection = InspectionFactory.create(db_session)
        assert inspection.area_results == []

    def test_returns_empty_list_when_plan_has_no_items(self, db_session):
        plan = ActionPlanFactory.create(db_session)
        inspection = plan.inspection
        db_session.refresh(inspection)
        # Plan has no items, so area_results should be empty
        assert inspection.area_results == []

    def test_groups_items_by_sector(self, db_session):
        plan = ActionPlanFactory.create(db_session, stats_json=None)
        ActionPlanItemFactory.create(db_session, action_plan=plan, sector='Cozinha')
        ActionPlanItemFactory.create(db_session, action_plan=plan, sector='Estoque')
        ActionPlanItemFactory.create(db_session, action_plan=plan, sector='Cozinha')

        inspection = plan.inspection
        db_session.refresh(inspection)
        results = inspection.area_results

        sector_names = [r['nome_area'] for r in results]
        assert 'Cozinha' in sector_names
        assert 'Estoque' in sector_names
        assert len(results) == 2

    def test_item_with_none_sector_defaults_to_geral(self, db_session):
        plan = ActionPlanFactory.create(db_session, stats_json=None)
        ActionPlanItemFactory.create(db_session, action_plan=plan, sector=None)

        inspection = plan.inspection
        db_session.refresh(inspection)
        results = inspection.area_results

        assert len(results) == 1
        assert results[0]['nome_area'] == 'Geral'

    def test_area_results_contain_expected_keys(self, db_session):
        plan = ActionPlanFactory.create(db_session, stats_json=None)
        ActionPlanItemFactory.create(db_session, action_plan=plan, sector='Cozinha')

        inspection = plan.inspection
        db_session.refresh(inspection)
        result = inspection.area_results[0]

        assert 'id' in result
        assert 'nome_area' in result
        assert 'score_obtido' in result
        assert 'score_maximo' in result
        assert 'aproveitamento' in result
        assert 'order' in result

    def test_area_results_enriched_by_stats_json_by_sector(self, db_session):
        stats = {
            'score': 7, 'max_score': 10, 'percentage': 70.0,
            'by_sector': {
                'Cozinha': {'score': 3, 'max_score': 5, 'percentage': 60.0},
                'Estoque': {'score': 4, 'max_score': 5, 'percentage': 80.0},
            }
        }
        plan = ActionPlanFactory.create(db_session, stats_json=stats)
        ActionPlanItemFactory.create(db_session, action_plan=plan, sector='Cozinha')
        ActionPlanItemFactory.create(db_session, action_plan=plan, sector='Estoque')

        inspection = plan.inspection
        db_session.refresh(inspection)
        results = inspection.area_results
        by_name = {r['nome_area']: r for r in results}

        assert by_name['Cozinha']['score_obtido'] == 3
        assert by_name['Cozinha']['score_maximo'] == 5
        assert by_name['Cozinha']['aproveitamento'] == 60.0
        assert by_name['Estoque']['score_obtido'] == 4
        assert by_name['Estoque']['score_maximo'] == 5
        assert by_name['Estoque']['aproveitamento'] == 80.0

    def test_by_sector_adds_new_sector_not_in_items(self, db_session):
        """stats_json by_sector may reference a sector that has no items."""
        stats = {
            'by_sector': {
                'Banheiro': {'score': 5, 'max_score': 5, 'percentage': 100.0},
            }
        }
        plan = ActionPlanFactory.create(db_session, stats_json=stats)
        ActionPlanItemFactory.create(db_session, action_plan=plan, sector='Cozinha')

        inspection = plan.inspection
        db_session.refresh(inspection)
        results = inspection.area_results

        sector_names = [r['nome_area'] for r in results]
        assert 'Cozinha' in sector_names
        assert 'Banheiro' in sector_names
        assert len(results) == 2


class TestActionItems:
    """Tests for Inspection.action_items property."""

    def test_returns_empty_list_when_no_plan(self, db_session):
        inspection = InspectionFactory.create(db_session)
        assert inspection.action_items == []

    def test_returns_enriched_items(self, db_session):
        plan = ActionPlanFactory.create(db_session)
        ActionPlanItemFactory.create(
            db_session,
            action_plan=plan,
            problem_description='Problema A',
            corrective_action='Corrigir A',
            legal_basis='Lei 123',
            sector='Cozinha',
            original_status='Nao Conforme',
            ai_suggested_deadline='7 dias',
            manager_notes='Nota do gestor',
        )

        inspection = plan.inspection
        db_session.refresh(inspection)
        items = inspection.action_items

        assert len(items) == 1
        item = items[0]
        assert item.item_verificado == 'Problema A'
        assert item.acao_corretiva == 'Corrigir A'
        assert item.fundamento_legal == 'Lei 123'
        assert item.nome_area == 'Cozinha'
        assert item.status_inicial == 'Nao Conforme'
        assert item.prazo_sugerido == '7 dias'
        assert item.correction_notes == 'Nota do gestor'

    def test_status_atual_is_pendente_for_open_item(self, db_session):
        from src.models_db import ActionPlanItemStatus

        plan = ActionPlanFactory.create(db_session)
        ActionPlanItemFactory.create(
            db_session, action_plan=plan, status=ActionPlanItemStatus.OPEN,
        )

        inspection = plan.inspection
        db_session.refresh(inspection)
        items = inspection.action_items

        assert items[0].status_atual == 'Pendente'

    def test_status_atual_is_corrigido_for_resolved_item(self, db_session):
        from src.models_db import ActionPlanItemStatus

        plan = ActionPlanFactory.create(db_session)
        ActionPlanItemFactory.create(
            db_session, action_plan=plan, status=ActionPlanItemStatus.RESOLVED,
        )

        inspection = plan.inspection
        db_session.refresh(inspection)
        items = inspection.action_items

        assert items[0].status_atual == 'Corrigido'

    def test_prazo_sugerido_formats_deadline_date(self, db_session):
        plan = ActionPlanFactory.create(db_session)
        ActionPlanItemFactory.create(
            db_session,
            action_plan=plan,
            deadline_date=date(2026, 3, 15),
            ai_suggested_deadline='30 dias',
        )

        inspection = plan.inspection
        db_session.refresh(inspection)
        items = inspection.action_items

        # deadline_date takes priority and is formatted dd/mm/YYYY
        assert items[0].prazo_sugerido == '15/03/2026'

    def test_prazo_sugerido_falls_back_to_ai_deadline(self, db_session):
        plan = ActionPlanFactory.create(db_session)
        ActionPlanItemFactory.create(
            db_session,
            action_plan=plan,
            deadline_date=None,
            ai_suggested_deadline='14 dias',
        )

        inspection = plan.inspection
        db_session.refresh(inspection)
        items = inspection.action_items

        assert items[0].prazo_sugerido == '14 dias'

    def test_prazo_sugerido_na_when_no_dates(self, db_session):
        plan = ActionPlanFactory.create(db_session)
        ActionPlanItemFactory.create(
            db_session,
            action_plan=plan,
            deadline_date=None,
            ai_suggested_deadline=None,
        )

        inspection = plan.inspection
        db_session.refresh(inspection)
        items = inspection.action_items

        assert items[0].prazo_sugerido == 'N/A'

    def test_fundamento_legal_na_when_none(self, db_session):
        plan = ActionPlanFactory.create(db_session)
        ActionPlanItemFactory.create(
            db_session, action_plan=plan, legal_basis=None,
        )

        inspection = plan.inspection
        db_session.refresh(inspection)
        items = inspection.action_items

        assert items[0].fundamento_legal == 'N/A'

    def test_nome_area_defaults_to_geral(self, db_session):
        plan = ActionPlanFactory.create(db_session)
        ActionPlanItemFactory.create(
            db_session, action_plan=plan, sector=None,
        )

        inspection = plan.inspection
        db_session.refresh(inspection)
        items = inspection.action_items

        assert items[0].nome_area == 'Geral'

    def test_status_inicial_defaults_to_nao_conforme_when_none(self, db_session):
        plan = ActionPlanFactory.create(db_session)
        ActionPlanItemFactory.create(
            db_session, action_plan=plan, original_status=None,
        )

        inspection = plan.inspection
        db_session.refresh(inspection)
        items = inspection.action_items

        assert items[0].status_inicial == 'N\u00e3o Conforme'  # fallback


class TestHasBeenUpdated:
    """Tests for Inspection.has_been_updated property."""

    def test_always_returns_false(self, db_session):
        inspection = InspectionFactory.create(db_session)
        assert inspection.has_been_updated is False

    def test_returns_false_even_with_resolved_items(self, db_session):
        from src.models_db import ActionPlanItemStatus

        plan = ActionPlanFactory.create(db_session)
        ActionPlanItemFactory.create(
            db_session, action_plan=plan, status=ActionPlanItemStatus.RESOLVED,
        )
        inspection = plan.inspection
        db_session.refresh(inspection)
        assert inspection.has_been_updated is False


# ---------------------------------------------------------------------------
# ActionPlanItem legacy property adapters
# ---------------------------------------------------------------------------

class TestItemVerificadoAdapter:
    """Tests for ActionPlanItem.item_verificado getter and setter."""

    def test_getter_returns_problem_description(self, db_session):
        item = ActionPlanItemFactory.create(
            db_session, problem_description='Piso escorregadio',
        )
        assert item.item_verificado == 'Piso escorregadio'

    def test_setter_updates_problem_description(self, db_session):
        item = ActionPlanItemFactory.create(db_session)
        item.item_verificado = 'Novo problema detectado'
        assert item.problem_description == 'Novo problema detectado'


class TestFundamentoLegalAdapter:
    """Tests for ActionPlanItem.fundamento_legal getter and setter."""

    def test_getter_returns_legal_basis(self, db_session):
        item = ActionPlanItemFactory.create(
            db_session, legal_basis='RDC 216/2004 Art. 10',
        )
        assert item.fundamento_legal == 'RDC 216/2004 Art. 10'

    def test_setter_updates_legal_basis(self, db_session):
        item = ActionPlanItemFactory.create(db_session)
        item.fundamento_legal = 'Portaria 1428/93'
        assert item.legal_basis == 'Portaria 1428/93'


class TestAcaoCorretivaSugeridaAdapter:
    """Tests for ActionPlanItem.acao_corretiva_sugerida getter and setter."""

    def test_getter_returns_corrective_action(self, db_session):
        item = ActionPlanItemFactory.create(
            db_session, corrective_action='Realizar limpeza diaria',
        )
        assert item.acao_corretiva_sugerida == 'Realizar limpeza diaria'

    def test_setter_updates_corrective_action(self, db_session):
        item = ActionPlanItemFactory.create(db_session)
        item.acao_corretiva_sugerida = 'Instalar exaustor'
        assert item.corrective_action == 'Instalar exaustor'


class TestPrazoSugeridoAdapter:
    """Tests for ActionPlanItem.prazo_sugerido getter and setter."""

    def test_getter_returns_ai_suggested_deadline(self, db_session):
        item = ActionPlanItemFactory.create(
            db_session, ai_suggested_deadline='15 dias',
        )
        assert item.prazo_sugerido == '15 dias'

    def test_setter_updates_ai_suggested_deadline(self, db_session):
        item = ActionPlanItemFactory.create(db_session)
        item.prazo_sugerido = '30 dias'
        assert item.ai_suggested_deadline == '30 dias'

    def test_getter_returns_none_when_no_deadline(self, db_session):
        item = ActionPlanItemFactory.create(
            db_session, ai_suggested_deadline=None,
        )
        assert item.prazo_sugerido is None
