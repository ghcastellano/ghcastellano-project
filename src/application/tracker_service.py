"""Service for tracking inspection processing progress."""


class TrackerService:
    """Determines tracker step statuses based on inspection state."""

    def get_tracker_steps(self, inspection):
        """
        Build tracker steps dict based on inspection state.

        Returns dict with keys: upload, ai_process, db_save, plan_gen, analysis.
        Each has 'status' (pending/current/completed/error) and 'label'.
        """
        steps = {
            'upload': {'status': 'completed', 'label': 'Upload Recebido'},
            'ai_process': {'status': 'pending', 'label': 'Processamento IA'},
            'db_save': {'status': 'pending', 'label': 'Estruturação de Dados'},
            'plan_gen': {'status': 'pending', 'label': 'Geração do Plano'},
            'analysis': {'status': 'pending', 'label': 'Análise do Gestor'},
        }

        logs = inspection.processing_logs or []
        status = inspection.status.value if hasattr(inspection.status, 'value') else str(inspection.status)
        has_logs = len(logs) > 0

        # Step 2: AI Processing
        if has_logs or status != 'PROCESSING':
            steps['ai_process']['status'] = 'completed'

        # Step 3: DB Structure
        if inspection.action_plan or (has_logs and any(
            'saved' in l.get('message', '').lower() for l in logs
        )):
            steps['ai_process']['status'] = 'completed'
            steps['db_save']['status'] = 'completed'

        # Step 4: Plan Generation
        if inspection.action_plan:
            steps['db_save']['status'] = 'completed'
            steps['plan_gen']['status'] = 'completed'

        # Step 5: Analysis
        if status in ['PENDING_MANAGER_REVIEW', 'APPROVED', 'REJECTED',
                       'PENDING_CONSULTANT_VERIFICATION', 'COMPLETED']:
            steps['plan_gen']['status'] = 'completed'
            if status in ['APPROVED', 'COMPLETED', 'PENDING_CONSULTANT_VERIFICATION']:
                steps['analysis']['status'] = 'completed'
                if status == 'APPROVED':
                    steps['analysis']['label'] = 'Aprovado'
            else:
                steps['analysis']['status'] = 'current'

        # Error handling
        if 'ERROR' in status or 'FAILED' in status:
            failed_step = 'ai_process'
            if steps['db_save']['status'] == 'completed':
                failed_step = 'plan_gen'
            steps[failed_step]['status'] = 'error'

        return steps

    def get_tracker_data(self, inspection):
        """Return full tracker response data for an inspection."""
        logs = inspection.processing_logs or []
        status = inspection.status.value if hasattr(inspection.status, 'value') else str(inspection.status)

        return {
            'id': str(inspection.id),
            'filename': getattr(inspection, 'processed_filename', None) or 'Arquivo',
            'status': status,
            'steps': self.get_tracker_steps(inspection),
            'logs': [l.get('message') for l in logs[-5:]],
        }
