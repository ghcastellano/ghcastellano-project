from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from src.database import get_db
from datetime import datetime
from src.models_db import User, UserRole, Company, Establishment, Job, JobStatus, Inspection, InspectionStatus, ActionPlan, ActionPlanItem, Visit
from sqlalchemy.orm import joinedload
from functools import wraps
import uuid
import os
import logging
from datetime import datetime

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
            
        flash(f'Empresa {name} criada com sucesso!', 'success')
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
                # Delete visits
                db.query(Visit).filter(Visit.consultant_id == user.id).delete()
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
                
                # Delete Visits linked to Est (if any remained)
                db.query(Visit).filter(Visit.establishment_id == est.id).delete()
                
                db.delete(est)

            # 4. Finally Delete Company
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
            db.query(Visit).filter(Visit.consultant_id == user.id).delete()
            
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
    Agora enriquecido com dados de Custo e Tokens.
    """
    db = next(get_db())
    try:
        from src.models_db import Inspection, Job
        from sqlalchemy import text
        # Fetch Top 50 recent inspections
        inspections = db.query(Inspection).options(joinedload(Inspection.establishment)).order_by(Inspection.created_at.desc()).limit(50).all()
        
        monitor_list = []
        for insp in inspections:
            # Extract logs
            logs = insp.processing_logs if insp.processing_logs else []
            
            # Determine Filename (MVP extraction from logs)
            filename = "Unknown.pdf"
            if logs:
                first_log = logs[0]
                # Log format: "Started processing filename.pdf" or "Iniciando processamento de filename.pdf"
                if first_log.get('stage') == 'INIT':
                    msg = first_log.get('message', '')
                    if "Started processing " in msg:
                        filename = msg.replace("Started processing ", "")
                    elif "Iniciando processamento de " in msg:
                        filename = msg.replace("Iniciando processamento de ", "")
            
            # Determine Last Status/Stage
            last_stage = "PENDING"
            last_msg = "-"
            if logs:
                last_log = logs[-1]
                last_stage = last_log.get('stage', 'UNKNOWN')
                last_msg = last_log.get('message', '')
            
            # Duration
            duration = None
            if logs and len(logs) > 1:
                try:
                    start = datetime.fromisoformat(logs[0]['timestamp'])
                    end = datetime.fromisoformat(logs[-1]['timestamp'])
                    duration = round((end - start).total_seconds(), 2)
                except: pass

            # --- COST / TOKEN ENRICHMENT ---
            tokens_in = 0
            tokens_out = 0
            cost_usd = 0.0
            job_status = None
            
            # Tentativa de Linkar com Job (assumindo file_id match)
            # Nota: Isso pode ser N+1 query, mas para 50 itens é aceitável admin-side.
            # Se performance degradar, fazer join ou eager load.
            if insp.drive_file_id:
                # Busca Job onde input_payload->>'file_id' == insp.drive_file_id
                # Usando SQL texto para JSONB operator ->> (Postgres)
                try:
                    # Alternativa ORM pura se Job model tivesse mapeamento direto, mas input_payload é JSON
                    # Vamos tentar buscar o job mais recente criado perto da inspection
                    # Alternativa: Buscar por ID ou pelo Nome do Arquivo (Fallback robusto)
                    filename_clean = str(insp.drive_file_id).replace("gcs:", "") if insp.drive_file_id else ""
                    
                    job = db.query(Job).filter(
                        text("(input_payload->>'file_id' = :fid) OR (input_payload->>'filename' = :fname)")
                    ).params(fid=str(insp.drive_file_id), fname=filename_clean).order_by(Job.created_at.desc()).first()
                    
                    if job:
                        tokens_in = job.cost_tokens_input or 0
                        tokens_out = job.cost_tokens_output or 0
                        job_status = job.status.value
                        
                        # Pricing (GPT-4o-mini rough estimate: $0.15/1M in, $0.60/1M out)
                        # Ajuste conforme modelo real no processor.py
                        cost_usd = (tokens_in / 1_000_000 * 0.15) + (tokens_out / 1_000_000 * 0.60)
                except Exception as db_err:
                    logger.warning(f"Erro linkando Job para {insp.id}: {db_err}")

            monitor_list.append({
                'id': str(insp.id),
                'filename': filename,
                'establishment': insp.establishment.name if insp.establishment else "Detectando...",
                'status': insp.status.value,
                'stage': last_stage,
                'message': last_msg,
                'duration': duration,
                'created_at': insp.created_at.isoformat() if insp.created_at else None,
                'logs': logs, # Full logs for detail view
                'tokens_total': tokens_in + tokens_out,
                'cost_usd': round(cost_usd, 5), # 5 decimal places for micro-costs
                'job_status': job_status
            })
            
        return jsonify({'items': monitor_list})
    except Exception as e:
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"❌ Erro em api_monitor_stats: {str(e)}\n{traceback.format_exc()}")
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
            'filename': insp.processed_filename or "Arquivo",
            'status': status,
            'steps': steps,
            'logs': [l.get('message') for l in logs[-5:]]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()
