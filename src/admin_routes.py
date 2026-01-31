from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from src.database import get_db
from datetime import datetime
from src.models_db import User, UserRole, Company, Establishment, Job, JobStatus, Inspection, InspectionStatus, ActionPlan, ActionPlanItem
from sqlalchemy.orm import joinedload
from functools import wraps
import uuid
import os
import logging
from datetime import datetime
from src.services.drive_service import drive_service

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != UserRole.ADMIN:
            flash('Acesso restrito a administradores.', 'error')
            return redirect(url_for('manager.dashboard_manager')) # Fallback seguro
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/')
@login_required
@admin_required
def index():
    db = next(get_db())
    try:
        companies = db.query(Company).all()
        # Eager load company to prevent DetachedInstanceError in template
        managers = db.query(User).filter(User.role == UserRole.MANAGER).options(joinedload(User.company)).all()
        # Sort safe: Handle None company
        managers.sort(key=lambda m: m.company.name if m.company else "ZZZ_SemEmpresa")
        
        return render_template('admin_dashboard.html', companies=companies, managers=managers)
    except Exception as e:
        import traceback
        current_app.logger.error(f"Erro Crítico em Admin Index: {traceback.format_exc()}")
        return f"Erro Interno no Servidor (500). Detalhes: {e}", 500
    finally:
        db.close()

@admin_bp.route('/company/new', methods=['POST'])
@login_required
@admin_required
def create_company():
    name = request.form.get('name')
    cnpj = request.form.get('cnpj')
    
    if not name:
        if request.accept_mimetypes.accept_json:
             return jsonify({'error': 'Nome da empresa é obrigatório.'}), 400
        flash('Nome da empresa é obrigatório.', 'error')
        return redirect(url_for('admin.index'))
        
    db = next(get_db())
    try:
        company = Company(name=name, cnpj=cnpj)
        
        # [NEW] Drive Folder - Level 1: Company
        drive_folder_created = False
        try:
             # Use Root Folder from Env or None (Root)
             from src.app import drive_service # Import instance
             if drive_service.service:
                 root_id = os.getenv('GDRIVE_ROOT_FOLDER_ID')
                 f_id, f_link = drive_service.create_folder(folder_name=name, parent_id=root_id)
                 if f_id:
                     company.drive_folder_id = f_id
                     drive_folder_created = True
        except Exception as drive_err:
             current_app.logger.error(f"Failed to create Drive folder for Company: {drive_err}")
             
        db.add(company)
        db.commit()
        
        if request.accept_mimetypes.accept_json:
            return jsonify({
                'success': True, 
                'company': {
                    'id': str(company.id),
                    'name': company.name,
                    'cnpj': company.cnpj
                },
                'message': f'Empresa {name} criada com sucesso!'
            }), 201
            
        # [IMPROVEMENT] Notificar usuário se pasta do Drive não foi criada
        success_msg = f'Empresa {name} criada com sucesso!'
        if not drive_folder_created:
            success_msg += ' ⚠️ Pasta no Drive não pôde ser criada.'
            
        flash(success_msg, 'success' if drive_folder_created else 'warning')
    except Exception as e:
        db.rollback()
        if request.accept_mimetypes.accept_json:
             return jsonify({'error': f'Erro ao criar empresa: {e}'}), 500
        flash(f'Erro ao criar empresa: {e}', 'error')
    finally:
        db.close()
        
    return redirect(url_for('admin.index'))

@admin_bp.route('/company/<uuid:company_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_company(company_id):
    db = next(get_db())
    try:
        company = db.query(Company).get(company_id)
        if company:
            # 1. Delete Jobs
            db.query(Job).filter(Job.company_id == company_id).delete()
            
            # 2. Delete Users (Managers/Consultants) and their relations
            users = db.query(User).filter(User.company_id == company_id).all()
            for user in users:
                # Nullify approved plans (keep history but remove link or just nullify)
                db.query(ActionPlan).filter(ActionPlan.approved_by_id == user.id).update({ActionPlan.approved_by_id: None})
                # Delete visits - REMOVED
                # Delete user
                db.delete(user)
            
            # 3. Delete Establishments and their relations (Inspections -> ActionPlans)
            establishments = db.query(Establishment).filter(Establishment.company_id == company_id).all()
            for est in establishments:
                # Get Inspections
                inspections = db.query(Inspection).filter(Inspection.establishment_id == est.id).all()
                for insp in inspections:
                    # Delete ActionPlan Items
                    if insp.action_plan:
                         db.query(ActionPlanItem).filter(ActionPlanItem.action_plan_id == insp.action_plan.id).delete()
                         db.delete(insp.action_plan)
                    db.delete(insp)

                # Delete Establishment's Drive folder
                if est.drive_folder_id:
                    drive_service.delete_folder(est.drive_folder_id)

                db.delete(est)

            # 4. Delete Company's Drive folder
            if company.drive_folder_id:
                drive_service.delete_folder(company.drive_folder_id)

            # 5. Finally Delete Company
            db.delete(company)
            db.commit()
            
            if request.accept_mimetypes.accept_json:
                 return jsonify({'success': True, 'message': 'Empresa e todos os dados vinculados removidos.'}), 200
            flash('Empresa e todos os dados vinculados removidos.', 'success')
        else:
            if request.accept_mimetypes.accept_json:
                 return jsonify({'error': 'Empresa não encontrada.'}), 404
            flash('Empresa não encontrada.', 'error')
    except Exception as e:
        db.rollback()
        if request.accept_mimetypes.accept_json:
             return jsonify({'error': str(e)}), 500
        flash(f'Erro ao remover empresa: {e}', 'error')
    finally:
        db.close()
    return redirect(url_for('admin.index'))

@admin_bp.route('/establishment/new', methods=['POST'])
@login_required
@admin_required
def create_establishment():
    company_id = request.form.get('company_id')
    name = request.form.get('name')
    drive_id = request.form.get('drive_folder_id')
    
    if not company_id or not name:
        flash('Empresa e Nome são obrigatórios.', 'error')
        return redirect(url_for('admin.index'))
        
    db = next(get_db())
    try:
        est = Establishment(company_id=uuid.UUID(company_id), name=name, drive_folder_id=drive_id)
        db.add(est)
        db.commit()
        
        if request.accept_mimetypes.accept_json:
             return jsonify({
                 'success': True,
                 'message': f'Estabelecimento {name} criado!',
                 'establishment': {'id': str(est.id), 'name': est.name}
             }), 201
             
        flash(f'Estabelecimento {name} criado!', 'success')
    except Exception as e:
        db.rollback()
        if request.accept_mimetypes.accept_json:
             return jsonify({'error': str(e)}), 500
        flash(f'Erro ao criar estabelecimento: {e}', 'error')
    finally:
        db.close()
    return redirect(url_for('admin.index'))

@admin_bp.route('/manager/new', methods=['POST'])
@login_required
@admin_required
def create_manager():
    name = request.form.get('name')
    email = request.form.get('email')
    company_id = request.form.get('company_id')
    initial_password = request.form.get('password', '123456') # Default ou gerado
    
    if not email or not company_id:
        if request.accept_mimetypes.accept_json:
             return jsonify({'error': 'Email e Empresa são obrigatórios.'}), 400
        flash('Email e Empresa são obrigatórios.', 'error')
        return redirect(url_for('admin.index'))
        
    db = next(get_db())
    try:
        # Check exists
        if db.query(User).filter_by(email=email).first():
            if request.accept_mimetypes.accept_json:
                return jsonify({'error': 'Email já cadastrado.'}), 400
            flash('Email já cadastrado.', 'error')
            return redirect(url_for('admin.index'))
            
        if not initial_password or initial_password == '123456':
            import secrets
            import string
            alphabet = string.ascii_letters + string.digits + "!@#$%&"
            initial_password = ''.join(secrets.choice(alphabet) for i in range(12)) # 12 chars strong
            
        hashed = generate_password_hash(initial_password)
        user = User(
            name=name, 
            email=email, 
            password_hash=hashed, 
            role=UserRole.MANAGER,
            company_id=uuid.UUID(company_id),
            must_change_password=True
        )
        db.add(user)
        db.commit()
        db.refresh(user) # Recarrega para garantir relacionamentos
        
        # Helper for response
        company_name = user.company.name if user.company else 'Sem Empresa'
        company_id_str = str(user.company.id) if user.company else ''
        
        # Send Email
        from flask import current_app
        email_sent = False
        if hasattr(current_app, 'email_service'):
            email_sent = current_app.email_service.send_welcome_email(email, name, initial_password)
        
        if request.accept_mimetypes.accept_json:
            return jsonify({
                'success': True,
                'manager': {
                    'id': str(user.id),
                    'name': user.name,
                    'email': user.email,
                    'company_name': company_name,
                    'company_id': company_id_str
                },
                'message': f'Gestor criado com sucesso! Email enviado: {email_sent}'
            }), 201
        
        if email_sent:
            flash(f'Gestor criado! Email de boas-vindas enviado para {email}.', 'success')
        else:
            flash(f'Gestor criado, mas falha no envio de email. Senha temporária: {initial_password}', 'warning')
        
    except Exception as e:
        db.rollback()
        if request.accept_mimetypes.accept_json:
             return jsonify({'error': f'Erro ao criar gestor: {e}'}), 500
        flash(f'Erro ao criar gestor: {e}', 'error')
    finally:
        db.close()
    return redirect(url_for('admin.index'))

@admin_bp.route('/manager/<uuid:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_manager(user_id):
    db = next(get_db())
    try:
        user = db.query(User).get(user_id)
        if user and user.role == UserRole.MANAGER: # Allow deleting CONSULTANT too if passed? The route says manager.
            # Handle dependencies
            # 1. Nullify ActionPlans approved by this user
            db.query(ActionPlan).filter(ActionPlan.approved_by_id == user.id).update({ActionPlan.approved_by_id: None})
            
            # 2. Delete Visits linked to this user (if any, usually consultants have visits)
            # db.query(Visit).filter(Visit.consultant_id == user.id).delete() # REMOVED
            
            db.delete(user)
            db.commit()
            if request.accept_mimetypes.accept_json:
                 return jsonify({'success': True, 'message': 'Gestor removido.'}), 200
            flash('Gestor removido.', 'success')
        else:
            if request.accept_mimetypes.accept_json:
                 return jsonify({'error': 'Gestor não encontrado.'}), 404
            flash('Gestor não encontrado.', 'error')
    except Exception as e:
        db.rollback()
        if request.accept_mimetypes.accept_json:
             return jsonify({'error': str(e)}), 500
        flash(f'Erro: {e}', 'error')
    finally:
        db.close()
    return redirect(url_for('admin.index'))

@admin_bp.route('/test-job', methods=['POST'])
@login_required
@admin_required
def trigger_test_job():
    """
    Dispara manualmente um job de teste para verificar o pipeline assíncrono.
    """
    db = next(get_db())
    try:
        # Tenta pegar ID da empresa do usuário, ou fallback seguro
        company_id = current_user.company_id
        if not company_id:
             # Fallback para admin sem empresa: pega a primeira ou define dummy se permitido
             first_company = db.query(Company).first()
             if first_company:
                 company_id = first_company.id
             else:
                 # Se não tem nenhuma empresa, cria uma dummy ou falha
                 flash("Nenhuma empresa encontrada para associar o Job.", "error")
                 return redirect(url_for('admin.index'))

        # Criar Job
        job = Job(
            company_id=company_id,
            type="TEST_JOB",
            status=JobStatus.PENDING,
            input_payload={"delay": 5, "triggered_by": current_user.email}
        )
        
        db.add(job)
        db.commit()
        
        # Enfileirar (Enqueue)
        # [SYNC-MVP] Worker removed. Test job disabled or could run sync.
        success = True # task_manager.enqueue_job(job.id, payload={"type": "TEST_JOB"})
        
        job.status = JobStatus.COMPLETED
        db.commit()
        
        if success:
            job.status = JobStatus.QUEUED
            db.commit()
            flash(f"Job {job.id} enfileirado com sucesso!", "success")
        else:
            flash(f"Job {job.id} criado, mas falha ao enfileirar (Modo Mock ou Erro).", "warning")
            
    except Exception as e:
        db.rollback()
        flash(f"Erro ao criar job: {e}", "error")
    finally:
        db.close()
        
    return redirect(url_for('admin.index'))

@admin_bp.route('/company/<uuid:company_id>/update', methods=['POST'])
@login_required
@admin_required
def update_company(company_id):
    name = request.form.get('name')
    cnpj = request.form.get('cnpj')
    
    if not name:
        if request.accept_mimetypes.accept_json:
             return jsonify({'error': 'Nome da empresa é obrigatório.'}), 400
        flash('Nome da empresa é obrigatório.', 'error')
        return redirect(url_for('admin.index'))
        
    db = next(get_db())
    try:
        company = db.query(Company).get(company_id)
        if not company:
            if request.accept_mimetypes.accept_json:
                return jsonify({'error': 'Empresa não encontrada.'}), 404
            flash('Empresa não encontrada.', 'error')
            return redirect(url_for('admin.index'))
            
        company.name = name
        company.cnpj = cnpj
        db.commit()
        
        if request.accept_mimetypes.accept_json:
            return jsonify({'success': True, 'message': 'Empresa atualizada!'}), 200
        flash(f'Empresa {name} atualizada!', 'success')
    except Exception as e:
        db.rollback()
        if request.accept_mimetypes.accept_json:
             return jsonify({'error': str(e)}), 500
        flash(f'Erro ao atualizar: {e}', 'error')
    finally:
        db.close()
    return redirect(url_for('admin.index'))

@admin_bp.route('/manager/<uuid:user_id>/update', methods=['POST'])
@login_required
@admin_required
def update_manager(user_id):
    name = request.form.get('name')
    email = request.form.get('email')
    company_id = request.form.get('company_id')
    password = request.form.get('password') # Optional
    
    if not name or not email:
        return jsonify({'error': 'Nome e Email são obrigatórios.'}), 400

    db = next(get_db())
    try:
        user = db.query(User).get(user_id)
        if not user or user.role != UserRole.MANAGER:
            return jsonify({'error': 'Gestor não encontrado.'}), 404
            
        user.name = name
        user.email = email
        if company_id and company_id.strip():
            user.company_id = uuid.UUID(company_id)
        else:
            user.company_id = None # Permite desvincular empresa (Super Admin)
            
        if password and len(password.strip()) > 0:
            user.password_hash = generate_password_hash(password)
            
        db.commit()
        return jsonify({'success': True, 'message': 'Gestor atualizado!'}), 200
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()

@admin_bp.route('/api/monitor')
@login_required
@admin_required
def api_monitor_stats():
    """
    API JSON para alimentar o Monitoramento de Inspeções (Traceability Logs).
    Substitui o antigo Job Monitor.
    Agora enriquecido com dados de Custo, Tokens, Logs e Estágios.
    """
    db = next(get_db())
    try:
        from src.models_db import Job, JobStatus, Company, Inspection

        # Fetch Top 50 recent jobs with related inspection data
        jobs = db.query(Job).options(
            joinedload(Job.company)
        ).order_by(Job.created_at.desc()).limit(50).all()

        monitor_list = []
        for job in jobs:
            # Extract basic info
            payload = job.input_payload or {}
            filename = payload.get('filename', 'N/A')
            est_name = payload.get('establishment_name') or payload.get('establishment', 'N/A')
            file_id = payload.get('file_id')

            # Duration calculation
            duration = None
            if job.finished_at and job.created_at:
                delta = job.finished_at - job.created_at
                duration = round(delta.total_seconds(), 2)

            # Cost & Tokens
            cost_usd = (job.cost_input_usd or 0) + (job.cost_output_usd or 0)
            cost_brl = (job.cost_input_brl or 0) + (job.cost_output_brl or 0)
            tokens_in = job.cost_tokens_input or 0
            tokens_out = job.cost_tokens_output or 0

            # Get inspection data for detailed status
            current_stage = "Upload"
            inspection_status = None
            last_log_message = None

            if file_id:
                inspection = db.query(Inspection).filter_by(drive_file_id=file_id).first()
                if inspection:
                    inspection_status = inspection.status.value if inspection.status else None

                    # Determine current stage from status
                    if inspection_status == "PROCESSING":
                        current_stage = "Processando IA"
                    elif inspection_status == "PENDING_MANAGER_REVIEW":
                        current_stage = "Aguardando Gestor"
                    elif inspection_status == "PENDING_CONSULTANT_VERIFICATION":
                        current_stage = "Aguardando Visita"
                    elif inspection_status == "COMPLETED":
                        current_stage = "Concluído"
                    elif inspection_status == "REJECTED":
                        current_stage = "Rejeitado"

                    # Get last log message
                    if inspection.processing_logs and len(inspection.processing_logs) > 0:
                        last_log = inspection.processing_logs[-1]
                        last_log_message = last_log.get('message', '')

            # Parse error details
            error_details = None
            error_code = None
            if job.error_log:
                try:
                    import json
                    error_data = json.loads(job.error_log) if isinstance(job.error_log, str) else job.error_log

                    # Handle array format (new) or single object (legacy)
                    if isinstance(error_data, list) and len(error_data) > 0:
                        # Get the most recent error (last in array)
                        latest_error = error_data[-1]
                        error_code = latest_error.get('code', 'ERRO')
                        error_details = latest_error.get('admin_msg') or latest_error.get('user_msg') or latest_error.get('message', 'Erro desconhecido')

                        # If multiple errors, add count
                        if len(error_data) > 1:
                            error_details = f"[{len(error_data)} erros] {error_details}"
                    elif isinstance(error_data, dict):
                        # Legacy single error object
                        error_code = error_data.get('code', 'ERRO')
                        error_details = error_data.get('admin_msg') or error_data.get('user_msg') or error_data.get('message', 'Erro desconhecido')
                    else:
                        error_details = str(error_data)[:100]
                except Exception as parse_err:
                    # If JSON parsing fails, show raw string
                    error_details = str(job.error_log)[:100]  # Limit to 100 chars
                    error_code = 'PARSE_ERROR'

            # Infer type if not set (for legacy jobs)
            job_type = job.type
            if not job_type:
                # Try to infer from payload or context
                if 'file_id' in payload or 'filename' in payload:
                    job_type = 'PROCESS_REPORT'
                elif 'sync' in str(payload).lower():
                    job_type = 'SYNC_PROCESS'
                else:
                    job_type = 'PROCESS_REPORT'  # Default

            monitor_list.append({
                'id': str(job.id),
                'type': job_type,
                'company_name': job.company.name if job.company else "Sem Empresa",
                'filename': filename,
                'establishment': est_name,
                'status': job.status.value,
                'inspection_status': inspection_status,
                'current_stage': current_stage,
                'created_at': job.created_at.isoformat() if job.created_at else None,
                'finished_at': job.finished_at.isoformat() if job.finished_at else None,
                'duration': duration,
                'tokens_input': tokens_in,
                'tokens_output': tokens_out,
                'tokens_total': tokens_in + tokens_out,
                'cost_usd': round(cost_usd, 4),
                'cost_brl': round(cost_brl, 4),
                'error_log': error_details,
                'error_code': error_code,
                'last_log_message': last_log_message,
                'attempts': job.attempts or 0
            })

        return jsonify({'items': monitor_list})
    except Exception as e:
        import traceback
        current_app.logger.error(f"❌ Erro em api_monitor_stats: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@admin_bp.route('/api/tracker/<uuid:inspection_id>')
@login_required
@admin_required
def tracker_details(inspection_id):
    db = next(get_db())
    try:
        insp = db.query(Inspection).options(joinedload(Inspection.processing_logs)).get(inspection_id)
        if not insp:
            return jsonify({'error': 'Not found'}), 404
            
        # Analyze Logs / Status
        logs = insp.processing_logs or []
        status = insp.status.value
        
        steps = {
            'upload': {'status': 'completed', 'label': 'Upload Recebido'},
            'ai_process': {'status': 'pending', 'label': 'Processamento IA'},
            'db_save': {'status': 'pending', 'label': 'Estruturação de Dados'},
            'plan_gen': {'status': 'pending', 'label': 'Geração do Plano'},
            'analysis': {'status': 'pending', 'label': 'Análise do Gestor'}
        }
        
        has_logs = len(logs) > 0
        
        # Logic mirroring Manager view
        if has_logs or status != 'PROCESSING':
             steps['ai_process']['status'] = 'completed'
        if insp.action_plan or (has_logs and any('saved' in l.get('message', '').lower() for l in logs)):
             steps['ai_process']['status'] = 'completed'
             steps['db_save']['status'] = 'completed'
        if insp.action_plan:
             steps['db_save']['status'] = 'completed'
             steps['plan_gen']['status'] = 'completed'
        if status in ['PENDING', 'APPROVED', 'REJECTED']:
             steps['plan_gen']['status'] = 'completed'
             steps['analysis']['status'] = 'current' if status == 'PENDING' else 'completed'
             if status == 'APPROVED': steps['analysis']['label'] = 'Aprovado'
             
        if 'ERROR' in status or 'FAILED' in status:
            failed_step = 'ai_process'
            if steps['db_save']['status'] == 'completed': failed_step = 'plan_gen'
            steps[failed_step]['status'] = 'error'
            
        return jsonify({
            'id': str(insp.id),
            'filename': "Relatório de Inspeção", # [FIX] Model does not have processed_filename
            'status': status,
            'steps': steps,
            'logs': [l.get('message') for l in logs[-5:]]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()
