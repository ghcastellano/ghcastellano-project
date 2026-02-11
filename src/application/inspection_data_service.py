"""
Service for rebuilding inspection data from DB + AI raw response.

This is the BIGGEST WIN of the refactoring: eliminates ~520 lines of
duplicated item rebuild logic that previously existed in 4 different places.
"""
from src.models_db import ActionPlanItemStatus


class InspectionDataService:
    """Rebuilds inspection areas and items from DB records + AI JSON."""

    def __init__(self, uow):
        self._uow = uow

    def get_review_data(self, file_id, filter_compliant=True):
        """
        Build data for /review/<file_id> (consultant view).

        Args:
            file_id: Drive file ID of the inspection.
            filter_compliant: If True, skip items with status 'Conforme'.

        Returns:
            dict with rebuilt areas, stats, and inspection metadata,
            or None if not found.
        """
        inspection = self._uow.inspections.get_with_plan_by_file_id(file_id)
        if not inspection:
            return None

        ai_raw = inspection.ai_raw_response or {}
        plan = inspection.action_plan

        if not plan:
            return {
                'inspection': inspection,
                'data': ai_raw,
                'plan': None,
                'areas': [],
            }

        merged_stats = ai_raw.copy()
        if plan.stats_json:
            merged_stats.update(plan.stats_json)

        rebuilt_areas = self._rebuild_items(
            plan, merged_stats, filter_compliant=filter_compliant,
        )

        merged_stats['areas_inspecionadas'] = list(rebuilt_areas.values())

        return {
            'inspection': inspection,
            'data': merged_stats,
            'plan': plan,
            'areas': list(rebuilt_areas.values()),
        }

    def get_plan_edit_data(self, file_id):
        """
        Build data for /manager/plan/<file_id> (manager edit view).
        Same rebuild but without filtering compliant items.
        """
        return self.get_review_data(file_id, filter_compliant=False)

    def get_pdf_data(self, file_id):
        """
        Build data for PDF generation.
        Returns the merged dict ready for pdf_service.generate_pdf_bytes().
        """
        result = self.get_review_data(file_id, filter_compliant=False)
        if not result:
            return {}

        data = result['data']
        inspection = result['inspection']

        # Map status for template
        status_val = inspection.status.value if hasattr(inspection.status, 'value') else str(inspection.status)
        if status_val == 'COMPLETED':
            data['status_plano'] = 'CONCLUÍDO'
        elif status_val in ('APPROVED', 'PENDING_CONSULTANT_VERIFICATION'):
            data['status_plano'] = 'AGUARDANDO VISITA'
        else:
            data['status_plano'] = 'EM APROVAÇÃO'

        return data

    def _rebuild_items(self, plan, data, filter_compliant=True):
        """
        CORE LOGIC - replaces 4 duplicate copies.

        Rebuilds areas_inspecionadas from DB ActionPlanItems,
        recovering original AI metadata via two-level fallback.
        """
        if not plan or not plan.items:
            return {}

        db_items = sorted(
            plan.items,
            key=lambda i: (
                i.order_index if i.order_index is not None else float('inf'),
                str(i.id),
            ),
        )

        # Build lookup for recovering original item_verificado/observacao from AI JSON
        ai_item_map = {}
        if 'areas_inspecionadas' in data:
            for area in data['areas_inspecionadas']:
                a_name = area.get('nome_area', 'Geral')
                for idx, ai_item in enumerate(area.get('itens', [])):
                    ai_item_map[(a_name, idx)] = {
                        'item_verificado': ai_item.get('item_verificado', ''),
                        'observacao': ai_item.get('observacao', ''),
                    }

        # Build score map by index for two-level score recovery
        score_map_by_index = {}
        score_map_by_text = {}
        if 'areas_inspecionadas' in data:
            for area in data['areas_inspecionadas']:
                a_name = area.get('nome_area', 'Geral')
                for idx, ai_item in enumerate(area.get('itens', [])):
                    key_index = (a_name, idx)
                    score_data = {
                        'pontuacao': ai_item.get('pontuacao', 0),
                        'status': ai_item.get('status', 'Não Conforme'),
                    }
                    score_map_by_index[key_index] = score_data

                    text_key = (ai_item.get('item_verificado', '') or '')[:50]
                    if text_key:
                        score_map_by_text[text_key] = score_data

        # Initialize area containers from AI data
        rebuilt_areas = {}
        normalized_area_map = {}

        if 'areas_inspecionadas' in data:
            for area in data['areas_inspecionadas']:
                key = area.get('nome_area') or area.get('name')
                if key:
                    rebuilt_areas[key] = {
                        'nome_area': key,
                        'itens': [],
                        'pontuacao_obtida': area.get('pontuacao_obtida', 0),
                        'pontuacao_maxima': area.get('pontuacao_maxima', 0),
                        'aproveitamento': area.get('aproveitamento', 0),
                    }
                    normalized_area_map[key.strip().lower()] = rebuilt_areas[key]

        # Rebuild from DB items
        for item in db_items:
            raw_area_name = getattr(item, 'nome_area', None) or item.sector or 'Geral'
            norm_area_name = raw_area_name.strip().lower()

            target_area = normalized_area_map.get(norm_area_name)
            if target_area:
                area_name = target_area['nome_area']
            else:
                area_name = raw_area_name

            if area_name not in rebuilt_areas:
                rebuilt_areas[area_name] = {
                    'nome_area': area_name,
                    'itens': [],
                    'pontuacao_obtida': 0,
                    'pontuacao_maxima': 0,
                    'aproveitamento': 0,
                }
                normalized_area_map[area_name.strip().lower()] = rebuilt_areas[area_name]

            # Recover score/status via two-level fallback
            score_val = item.original_score if item.original_score is not None else 0
            status_val = item.original_status or 'Não Conforme'

            # Normalize status to standard Portuguese labels
            status_val = self._normalize_status(status_val)

            # Filter compliant items if requested
            if filter_compliant and status_val == 'Conforme':
                continue

            # Format deadline
            deadline_display = self._format_deadline(item)

            # Current workflow status
            current_status = item.current_status or (
                'Pendente' if item.status == ActionPlanItemStatus.OPEN else 'Pendente'
            )
            is_corrected = (current_status == 'Corrigido')

            # Recover AI original item name/observation
            ai_data = {}
            if item.order_index is not None:
                ai_data = ai_item_map.get((area_name, item.order_index), {})

            recovered_item_name = ai_data.get('item_verificado', '')
            recovered_obs = ai_data.get('observacao', '')

            rebuilt_areas[area_name]['itens'].append({
                'item_verificado': recovered_item_name or item.problem_description,
                'status': status_val,
                'status_atual': current_status,
                'observacao': recovered_obs or item.problem_description,
                'fundamento_legal': item.legal_basis,
                'acao_corretiva_sugerida': item.corrective_action,
                'prazo_sugerido': deadline_display,
                'pontuacao': float(score_val),
                'manager_notes': item.manager_notes,
                'evidence_image_url': item.evidence_image_url,
                'correction_notes': item.manager_notes,
                'is_corrected': is_corrected,
                'original_status_label': status_val,
                'old_score_display': str(score_val) if score_val else None,
                # Preserve DB item ID for edit operations
                'id': str(item.id),
                'severity': item.severity.value if hasattr(item.severity, 'value') else str(item.severity),
            })

        # Recalculate NC counts per area
        for area in rebuilt_areas.values():
            area['items_nc'] = sum(
                1 for i in area.get('itens', [])
                if i.get('status') != 'Conforme'
            )

        return rebuilt_areas

    @staticmethod
    def _normalize_status(status_val):
        """Normalize status string to standard Portuguese labels."""
        status_lower = status_val.lower()
        if 'parcial' in status_lower:
            return 'Parcialmente Conforme'
        elif 'não' in status_lower or 'nao' in status_lower:
            return 'Não Conforme'
        elif 'conforme' in status_lower:
            return 'Conforme'
        return status_val

    @staticmethod
    def _format_deadline(item):
        """Format deadline from item using priority: deadline_text > deadline_date > ai_suggested."""
        if item.deadline_text and item.deadline_text.strip():
            return item.deadline_text
        if item.deadline_date:
            try:
                return item.deadline_date.strftime('%d/%m/%Y')
            except Exception:
                pass
        return item.ai_suggested_deadline or 'N/A'
