"""Service for building dashboard data."""
import json
from datetime import datetime, timedelta

from src.models_db import InspectionStatus, JobStatus


class DashboardService:
    """Extracts dashboard business logic from route handlers."""

    def __init__(self, uow):
        self._uow = uow

    def get_consultant_dashboard(self, user):
        """
        Build all data needed for the consultant dashboard template.

        Returns dict with keys: inspections, stats, user_hierarchy,
        pending_establishments, failed_jobs.
        """
        my_est_ids = [est.id for est in user.establishments] if user.establishments else []

        # 1. Fetch processed inspections
        inspections = self._get_formatted_inspections(user.company_id, my_est_ids)

        # 2. Fetch and merge pending jobs
        existing_file_ids = {insp.get('id') for insp in inspections}
        pending_jobs = self._get_pending_jobs_as_dicts(user.company_id, my_est_ids)
        self._merge_jobs_into_inspections(inspections, pending_jobs, existing_file_ids)

        # 3. Calculate stats
        stats = self._calculate_stats(inspections, my_est_ids)

        # 4. Get pending establishments
        pending_establishments = self._get_pending_establishments(my_est_ids)

        # 5. Get failed jobs alerts
        failed_jobs = self._get_failed_job_alerts(user.company_id)

        # 6. Build user hierarchy
        user_hierarchy = self._build_user_hierarchy(user)

        return {
            'inspections': inspections,
            'stats': stats,
            'user_hierarchy': user_hierarchy,
            'pending_establishments': pending_establishments,
            'failed_jobs': failed_jobs,
        }

    def get_status_data(self, user, establishment_id=None):
        """Build data for /api/status polling endpoint."""
        my_est_ids = [est.id for est in user.establishments] if user.establishments else []

        pending = self._uow.inspections.get_pending(
            company_id=user.company_id,
            establishment_ids=my_est_ids,
        )
        processed = self._uow.inspections.get_for_manager(
            company_id=user.company_id,
            establishment_id=establishment_id,
        )

        return {
            'pending': [{'name': p.establishment.name if p.establishment else 'N/A'} for p in pending],
            'processed_raw': [
                {
                    'establishment': p.establishment.name if p.establishment else 'N/A',
                    'date': p.created_at.strftime('%d/%m/%Y %H:%M') if p.created_at else '',
                    'status': p.status.value if hasattr(p.status, 'value') else str(p.status),
                    'review_link': f'/manager/plan/{p.drive_file_id}',
                }
                for p in processed
            ],
        }

    def _get_formatted_inspections(self, company_id, establishment_ids):
        """Fetch inspections and format as dicts for template."""
        raw = self._uow.inspections.get_for_consultant(
            company_id=company_id,
            establishment_ids=establishment_ids,
        )
        result = []
        for insp in raw:
            status_val = insp.status.value if hasattr(insp.status, 'value') else str(insp.status)
            result.append({
                'id': insp.drive_file_id,
                'name': getattr(insp, 'processed_filename', None) or insp.drive_file_id,
                'establishment': insp.establishment.name if insp.establishment else 'N/A',
                'date': insp.created_at.strftime('%d/%m/%Y %H:%M') if insp.created_at else '',
                'status': status_val,
                'pdf_link': f'/review/{insp.drive_file_id}',
                'review_link': f'/review/{insp.drive_file_id}',
            })
        return result

    def _get_pending_jobs_as_dicts(self, company_id, establishment_ids):
        """Fetch pending jobs formatted as dicts."""
        jobs = self._uow.jobs.get_pending_for_company(
            company_id=company_id,
            establishment_ids=establishment_ids,
        )
        result = []
        for job in jobs:
            payload = job.input_payload or {}
            status_val = job.status.value if hasattr(job.status, 'value') else str(job.status)
            result.append({
                'drive_file_id': payload.get('file_id'),
                'name': payload.get('filename', 'Arquivo'),
                'establishment': payload.get('establishment_name', 'Em processamento...'),
                'created_at': job.created_at.strftime('%d/%m/%Y %H:%M') if job.created_at else '',
                'status': 'Em Análise' if status_val in ('PENDING', 'PROCESSING') else status_val,
                'status_raw': status_val,
            })
        return result

    @staticmethod
    def _merge_jobs_into_inspections(inspections, jobs, existing_file_ids):
        """Merge active jobs into inspections list, avoiding duplicates."""
        for job in jobs:
            file_id = job.get('drive_file_id')
            if file_id and file_id in existing_file_ids:
                continue

            is_completed = (job.get('status_raw') == 'COMPLETED')
            if is_completed:
                msg = 'Processamento concluído. O relatório deve aparecer na lista em breve.'
            elif job.get('status_raw') == 'FAILED':
                msg = 'Houve uma falha no processamento deste arquivo. Tente enviar novamente.'
            else:
                msg = 'Arquivo ainda em processamento. Por favor aguarde.'

            inspections.insert(0, {
                'id': file_id or '#',
                'name': job['name'],
                'establishment': job.get('establishment', 'Em processamento...'),
                'date': job['created_at'],
                'status': job.get('status', 'Pendente'),
                'pdf_link': '#',
                'review_link': f"javascript:alert('{msg}')",
            })

    def _calculate_stats(self, inspections, establishment_ids):
        """Calculate dashboard summary statistics."""
        total_score = 0
        max_score = 0

        if establishment_ids:
            completed = self._uow.inspections.get_for_consultant(
                establishment_ids=establishment_ids,
                statuses=[
                    InspectionStatus.COMPLETED,
                    InspectionStatus.PENDING_CONSULTANT_VERIFICATION,
                    InspectionStatus.APPROVED,
                ],
            )
            for insp in completed:
                if insp.ai_raw_response and isinstance(insp.ai_raw_response, dict):
                    score = insp.ai_raw_response.get('pontuacao_geral', 0)
                    max_s = insp.ai_raw_response.get('pontuacao_maxima_geral', 100)
                    if score and max_s:
                        total_score += float(score)
                        max_score += float(max_s)

        avg_score = round((total_score / max_score * 100), 2) if max_score > 0 else 0

        return {
            'total': len(inspections),
            'pending': sum(1 for i in inspections if i['status'] in ['PENDING_MANAGER_REVIEW', 'Pendente']),
            'approved': sum(1 for i in inspections if i['status'] in ['APPROVED', 'COMPLETED', 'Concluído']),
            'pontuacao_geral': total_score,
            'pontuacao_maxima': max_score,
            'aproveitamento_geral': avg_score,
        }

    def _get_pending_establishments(self, establishment_ids):
        """Get unique establishments with pending inspections."""
        if not establishment_ids:
            return []

        pending = self._uow.inspections.get_for_consultant(
            establishment_ids=establishment_ids,
            statuses=[InspectionStatus.PROCESSING, InspectionStatus.PENDING_MANAGER_REVIEW],
        )
        est_set = {insp.establishment for insp in pending if insp.establishment}
        return sorted(list(est_set), key=lambda e: e.name)

    def _get_failed_job_alerts(self, company_id):
        """Get recent failed job alerts, deduplicated by filename."""
        if not company_id:
            return []

        failed_records = self._uow.jobs.get_failed_recent(
            company_id=company_id,
            minutes=30,
            limit=10,
        )

        alerts = []
        seen_filenames = set()

        for job in failed_records:
            payload = job.input_payload or {}
            filename = payload.get('filename', 'Arquivo')

            if filename in seen_filenames:
                continue

            # Skip if file already processed successfully
            file_id = payload.get('file_id')
            if file_id:
                success = self._uow.inspections.get_by_drive_file_id(file_id)
                if success and success.status != InspectionStatus.PROCESSING:
                    continue

            seen_filenames.add(filename)

            error_obj = {'code': 'ERR_9001', 'user_msg': 'Erro desconhecido'}
            if job.error_log:
                try:
                    error_obj = json.loads(job.error_log.split('\n')[-1])
                except Exception:
                    error_obj = {'code': 'ERR_9001', 'user_msg': job.error_log[:200]}

            alerts.append({
                'filename': filename,
                'establishment': payload.get('establishment_name', 'N/A'),
                'establishment_id': payload.get('establishment_id'),
                'error_code': error_obj.get('code', 'ERR_UNKNOWN'),
                'error_message': error_obj.get('user_msg', 'Erro desconhecido. Contate o suporte.'),
                'created_at': job.created_at.strftime('%d/%m/%Y %H:%M') if job.created_at else 'N/A',
            })

        return alerts

    @staticmethod
    def _build_user_hierarchy(user):
        """Build establishment hierarchy dict for upload selectors."""
        hierarchy = {}
        if not user.establishments:
            return hierarchy

        sorted_ests = sorted(user.establishments, key=lambda x: x.name)
        for est in sorted_ests:
            comp_name = est.company.name if est.company else 'Outras'
            comp_id = str(est.company.id) if est.company else 'other'

            if comp_id not in hierarchy:
                hierarchy[comp_id] = {
                    'name': comp_name,
                    'establishments': [],
                }

            hierarchy[comp_id]['establishments'].append({
                'id': str(est.id),
                'name': est.name,
            })

        return hierarchy
