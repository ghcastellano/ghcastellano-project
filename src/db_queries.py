"""
Funções auxiliares para consultas ao banco de dados na aplicação web.
Todas as queries usam SQLAlchemy para interagir com o PostgreSQL (Supabase).
"""
from sqlalchemy.orm import joinedload
from src.models_db import Inspection, ActionPlan, ActionPlanItem, InspectionStatus, Establishment, Company, Job, JobStatus
from src import database
import logging
import uuid
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def get_pending_inspections(establishment_id=None):
    """Busca inspeções com status PROCESSING do banco de dados."""
    try:
        session = database.db_session()
        from datetime import datetime, timedelta
        cutoff = datetime.utcnow() - timedelta(hours=2)

        query = session.query(Inspection).options(
            joinedload(Inspection.establishment)
        ).filter(
            Inspection.status == InspectionStatus.PROCESSING,
            Inspection.created_at >= cutoff
        )
        
        if establishment_id:
            query = query.filter(Inspection.establishment_id == establishment_id)
            
        inspections = query.order_by(Inspection.created_at.desc()).limit(10).all()
        
        result = []
        for insp in inspections:
            # Determine name
            est_name = 'Desconhecido'
            if insp.establishment: est_name = insp.establishment.name
            
            result.append({
                'id': str(insp.id),
                'name': f"Inspeção {est_name}",
                'drive_file_id': insp.drive_file_id
            })
        
        session.close()
        return result
    except Exception as e:
        if 'session' in locals():
            session.rollback()
            session.close()
        return []

def get_processed_inspections_raw(company_id=None, establishment_id=None):
    """Busca lista de inspeções para o GESTOR (Tudo que já foi processado ou está em aprovação)."""
    try:
        session = database.db_session()
        # Gestor vê: PENDING_MANAGER_REVIEW, WAITING_APPROVAL, APPROVED, PENDING_VERIFICATION, COMPLETED
        statuses = [
            InspectionStatus.PENDING_MANAGER_REVIEW,
            InspectionStatus.WAITING_APPROVAL,
            InspectionStatus.APPROVED,
            InspectionStatus.PENDING_VERIFICATION,
            InspectionStatus.COMPLETED
        ]
        
        # Otimização: Eager Load Action Plan para evitar N+1 ao acessar propriedades (score, resumo)
        query = session.query(Inspection).options(
            joinedload(Inspection.establishment),
            joinedload(Inspection.action_plan) # Eager load for stats access
        ).filter(
            Inspection.status.in_(statuses)
        )
        if establishment_id:
            query = query.filter(Inspection.establishment_id == establishment_id)
        elif company_id:
            from src.models_db import Visit, User
            query = query.outerjoin(Inspection.establishment).outerjoin(Inspection.visit).outerjoin(Visit.consultant)
            query = query.filter(
                (Establishment.company_id == company_id) | 
                (User.company_id == company_id)
            )
            
        inspections = query.order_by(Inspection.created_at.desc()).limit(50).all()
        
        result = []
        for insp in inspections:
            ai_data = insp.ai_raw_response or {}
            
            est_name = 'Desconhecido'
            if insp.establishment: est_name = insp.establishment.name
            
            result.append({
                'id': insp.drive_file_id,
                'name': ai_data.get('titulo', 'Relatório Processado'),
                'establishment': est_name,
                'date': ai_data.get('data_inspecao', ''),
                'status': insp.status.value, # Passa status para UI
                'pdf_link': f"/download_pdf/{insp.drive_file_id}" if insp.drive_file_id else "#",
                'review_link': f"/manager/plan/{insp.drive_file_id}" if insp.drive_file_id else "#"
            })
        
        session.close()
        return result
    except Exception as e:
        if 'session' in locals():
            session.rollback()
            session.close()
        return []

def get_consultant_inspections(company_id=None, establishment_id=None, allowed_establishment_ids=None):
    """Busca lista de inspeções para o CONSULTOR (Apenas aprovados/em verificação)."""
    try:
        session = database.db_session()
        # Consultor vê: PROCESSING, APPROVED, PENDING_VERIFICATION, COMPLETED, WAITING_APPROVAL, PENDING_MANAGER_REVIEW
        statuses = [
            InspectionStatus.PROCESSING,
            InspectionStatus.APPROVED,
            InspectionStatus.PENDING_VERIFICATION,
            InspectionStatus.COMPLETED,
            InspectionStatus.WAITING_APPROVAL,
            InspectionStatus.PENDING_MANAGER_REVIEW,
            InspectionStatus.REJECTED
        ]
        
        query = session.query(Inspection).options(
            joinedload(Inspection.establishment)
        ).filter(
            Inspection.status.in_(statuses)
        )
        
        if establishment_id:
            query = query.filter(Inspection.establishment_id == establishment_id)
        
        # [SECURITY] Filter by allowed establishments (Consultant Scope)
        # [FIX] Simplificar lógica - se temos establishment_ids, filtrar diretamente
        elif allowed_establishment_ids is not None and len(allowed_establishment_ids) > 0:
            # Consultor só vê inspeções dos estabelecimentos dele
            query = query.filter(Inspection.establishment_id.in_(allowed_establishment_ids))
        elif company_id:
            # Fallback: Se não tem establishment_ids mas tem company_id, filtrar por company
            from sqlalchemy import or_
            query = query.join(Inspection.establishment)
            query = query.filter(Establishment.company_id == company_id)
        
        inspections = query.order_by(Inspection.created_at.desc()).limit(50).all()
        
        result = []
        for insp in inspections:
            ai_data = insp.ai_raw_response or {}
            est_name = 'Desconhecido'
            if insp.establishment: est_name = insp.establishment.name
            
            result.append({
                'id': insp.drive_file_id,
                'name': ai_data.get('titulo', 'Relatório Processado'),
                'establishment': est_name,
                'date': ai_data.get('data_inspecao', ''),
                'status': insp.status.value,
                'pdf_link': f"/download_pdf/{insp.drive_file_id}" if insp.drive_file_id else "#",
                'review_link': f"/review/{insp.drive_file_id}" if insp.drive_file_id else "#"
            })
        
        # session.close()
        return result
    except Exception as e:
        logger.error(f"❌ ERRO em get_consultant_inspections: {e}")
        import traceback
        logger.error(traceback.format_exc())
        if 'session' in locals():
            session.rollback()
            # session.close()
        return []

def get_consultant_pending_inspections(establishment_id=None, company_id=None, establishment_ids=None):
    """Busca inspeções com status WAITING_APPROVAL ou PENDING_MANAGER_REVIEW."""
    try:
        session = database.db_session()
        statuses = [InspectionStatus.WAITING_APPROVAL, InspectionStatus.PENDING_MANAGER_REVIEW]
        
        query = session.query(Inspection).filter(
            Inspection.status.in_(statuses)
        )
        
        from sqlalchemy import or_
        from src.models_db import Establishment

        conditions = []
        
        # 1. Single ID (Legacy)
        if establishment_id:
            conditions.append(Inspection.establishment_id == establishment_id)
            
        # 2. List of IDs (Scope)
        if establishment_ids:
            conditions.append(Inspection.establishment_id.in_(establishment_ids))
            
        # 3. Company Fallback (New Stores / Company Wide)
        if company_id:
             query = query.outerjoin(Inspection.establishment)
             conditions.append(Establishment.company_id == company_id)
        
        if conditions:
            query = query.filter(or_(*conditions))
        
        inspections = query.order_by(Inspection.created_at.desc()).limit(10).all()
        
        result = []
        for insp in inspections:
            ai_data = insp.ai_raw_response or {}
            
            # Safe establishment name resolve
            est_name = 'Desconhecido'
            if insp.establishment: est_name = insp.establishment.name
            
            result.append({
                'id': insp.drive_file_id,
                'name': ai_data.get('titulo', 'Relatório em Análise'),
                'establishment': est_name,
                'date': ai_data.get('data_inspecao', insp.created_at.strftime('%d/%m/%Y')),
                'status': 'Aguardando Aprovação'
            })
        
        # session.close()
        return result
    except Exception as e:
        if 'session' in locals():
            # session.close()
            pass
        return []

def get_inspection_details(drive_file_id):
    """Obtém detalhes completos de uma inspeção pelo drive_file_id."""
    try:
        session = database.db_session()
        inspection = session.query(Inspection).options(
            joinedload(Inspection.action_plan).joinedload(ActionPlan.items)
        ).filter(Inspection.drive_file_id == drive_file_id).first()
        
        if not inspection:
            session.close()
            return None
        
        # Extrai dados do JSONB ai_raw_response
        ai_data = inspection.ai_raw_response or {}
        
        result = {
            'id': inspection.drive_file_id,
            'name': ai_data.get('titulo', 'Relatório Processado'),
            'establishment': inspection.establishment.name if inspection.establishment else 'Desconhecido',
            'date': ai_data.get('data_inspecao', ''),
            'pdf_name': f"{inspection.establishment.name if inspection.establishment else 'relatorio'}.pdf",
            'pdf_link': f"/download_pdf/{inspection.drive_file_id}",
            'review_link': f"/review/{inspection.drive_file_id}",
            'action_plan': {
                'final_pdf_link': inspection.action_plan.final_pdf_public_link if inspection.action_plan else None,
                'items': [{
                    'id': str(item.id),
                    'problem': item.problem_description,
                    'action': item.corrective_action,
                    'legal_basis': item.legal_basis,
                    'severity': item.severity.value if item.severity else 'MEDIUM',
                    'status': item.status.value if item.status else 'OPEN'
                } for item in inspection.action_plan.items] if inspection.action_plan else []
            } if inspection.action_plan else None
        }
        
        session.close()
        return result
    except Exception as e:
        if 'session' in locals():
            session.rollback()
            session.close()
        return None

def get_batch_inspection_details(drive_file_ids):
    """Obtém detalhes de múltiplas inspeções de uma vez."""
    try:
        session = database.db_session()
        inspections = session.query(Inspection).options(
            joinedload(Inspection.action_plan)
        ).filter(Inspection.drive_file_id.in_(drive_file_ids)).all()
        
        results = {}
        for inspection in inspections:
            ai_data = inspection.ai_raw_response or {}
            results[inspection.drive_file_id] = {
                'id': inspection.drive_file_id,
                'name': ai_data.get('titulo', 'Relatório Processado'),
                'establishment': inspection.establishment.name if inspection.establishment else 'Desconhecido',
                'date': ai_data.get('data_inspecao', ''),
                'pdf_name': f"{inspection.establishment.name if inspection.establishment else 'relatorio'}.pdf",
                'pdf_link': f"/download_pdf/{inspection.drive_file_id}",
                'review_link': f"/review/{inspection.drive_file_id}"
            }
        
        session.close()
        return results
    except Exception as e:
        if 'session' in locals():
            session.rollback()
            session.close()
        return {}
        return {}

def get_pending_jobs(company_id=None, establishment_id=None, allow_all=False, establishment_ids=None):
    """Busca JOBS (tarefas de background) que estão pendentes ou rodando."""
    try:
        session = database.db_session()
        from datetime import datetime, timedelta
        # Filter active jobs (Exclude COMPLETED to avoid "stuck" processing card)
        # Filter by recent time (last 30 minutes) to avoid ghosts
        cutoff_time = datetime.now() - timedelta(minutes=30)
        query = session.query(Job).filter(
            Job.status.in_([JobStatus.PENDING, JobStatus.PROCESSING, JobStatus.FAILED]),
            Job.created_at >= cutoff_time
        )
        
        # Security: If not allowing all, user MUST have either company scope or establishment scope
        if not allow_all and not company_id and not establishment_ids:
            # Fallback: If no scope provided, return empty (Safety)
            session.close()
            return []
            
        filters = []
        if company_id:
            filters.append(Job.company_id == company_id)
            
        if establishment_ids:
            # JSONB Query: input_payload->>'establishment_id' IN (list of ids)
            # Use astext for comparison
            from sqlalchemy import cast, String
            import json
            
            # Cast list to strings for robustness (Fix SQL UUID vs Text error)
            ids_str = [str(uid) for uid in establishment_ids if uid]
            
            # Note: We use OR logic? Usually users want to see jobs for their company OR their establishments.
            # But usually Consultant has no company_id. 
            # So if we have establishment_ids, we add it as an OR condition if filters exist, or main condition.
            # Let's use sqlalchemy OR if both present.
            
            if ids_str:
                est_filter = Job.input_payload['establishment_id'].astext.in_(ids_str)
                filters.append(est_filter)
            
        if filters:
            from sqlalchemy import or_
            query = query.filter(or_(*filters))

        jobs = query.order_by(Job.created_at.desc()).limit(20).all()
        
        result = []
        for job in jobs:
            payload = job.input_payload or {}
            filename = payload.get('filename', 'Processando arquivo...')
            
            # Additional logic for admin monitoring
            status_color = 'gray'
            status_label = job.status.value
            if job.status == JobStatus.COMPLETED:
                status_color = 'green'
                status_label = 'Concluído'
            elif job.status == JobStatus.FAILED:
                status_color = 'red'
                status_label = 'Falha'
            elif job.status == JobStatus.PROCESSING:
                status_color = 'blue'
                status_label = 'Processando'
            elif job.status == JobStatus.PENDING:
                status_color = 'orange'
                status_label = 'Pendente'

            # Calculate Costs (Fallback if not persisted)
            input_cost = job.cost_input_brl if job.cost_input_brl > 0 else (job.cost_tokens_input * 0.150 / 1000000.0 * 6.00 if job.cost_tokens_input else 0)
            output_cost = job.cost_output_brl if job.cost_output_brl > 0 else (job.cost_tokens_output * 0.600 / 1000000.0 * 6.00 if job.cost_tokens_output else 0)
            total_cost_brl = input_cost + output_cost
            
            # USD approximation (BRL / 6.0)
            total_cost_usd = total_cost_brl / 6.0

            result.append({
                'id': str(job.id),
                'drive_file_id': payload.get('file_id'),
                'type': job.type, 
                'filename': filename,
                'name': filename, # Compat
                'establishment': payload.get('company_name') or payload.get('establishment_name') or 'N/A',
                'company_name': job.company.name if job.company else 'N/A',
                'status': job.status.value, # Raw value for Frontend mapping
                'status_label': status_label, # Legacy/Extra
                'error_log': job.error_log,
                
                'tokens_input': job.cost_tokens_input or 0,
                'tokens_output': job.cost_tokens_output or 0,
                'tokens_total': (job.cost_tokens_input or 0) + (job.cost_tokens_output or 0),
                
                'cost_brl': total_cost_brl,
                'cost_usd': total_cost_usd,
                
                'duration': round(job.execution_time_seconds, 1) if job.execution_time_seconds else 0,
                'created_at': job.created_at.strftime('%d/%m/%Y %H:%M')
            })
            
        session.close()
        return result
    except Exception as e:
        logger.error(f"Error fetching pending jobs: {e}")
        if 'session' in locals():
             session.close()
        return []
