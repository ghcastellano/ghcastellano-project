from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from src.database import get_db
from datetime import datetime
from src.models_db import User, UserRole, Company, Establishment, Job, JobStatus, Inspection, InspectionStatus
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
            db.delete(company)
            db.commit()
            if request.accept_mimetypes.accept_json:
                 return jsonify({'success': True, 'message': 'Empresa removida.'}), 200
            flash('Empresa removida.', 'success')
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
        if user and user.role == UserRole.MANAGER:
            db.delete(user)
            db.commit()
            if request.accept_mimetypes.accept_json:
                 return jsonify({'success': True, 'message': 'Gestor removido.'}), 200
            flash('Gestor removido.', 'success')
        else:
            if request.accept_mimetypes.accept_json:
                 return jsonify({'error': 'Gestor não encontrado.'}), 404
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
    """
    db = next(get_db())
    try:
        from src.models_db import Inspection
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
                # Log format: "Started processing filename.pdf"
                if first_log.get('stage') == 'INIT':
                    msg = first_log.get('message', '')
                    if "Started processing " in msg:
                        filename = msg.replace("Started processing ", "")
            
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

            monitor_list.append({
                'id': str(insp.id),
                'filename': filename,
                'establishment': insp.establishment.name if insp.establishment else "Detectando...",
                'status': insp.status.value,
                'stage': last_stage,
                'message': last_msg,
                'duration': duration,
                'created_at': insp.created_at.isoformat() if insp.created_at else None,
                'logs': logs # Full logs for detail view
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

@admin_bp.route('/api/cron/sync_drive', methods=['GET', 'POST'])
def cron_sync_drive():
    """
    WORKERLESS SYNC: Scheduled by Cloud Scheduler (e.g., every 15 min).
    Lists input folder, checks if file is already processed (in DB),
    and triggers synchronous processing for up to 2 pending files per run (to avoid timeout).
    """
    # 1. Security Check: Validate App Engine Custom Header or Secret Token
    # Cloud Scheduler adds 'X-Appengine-Cron: true'
    is_cron = request.headers.get('X-Appengine-Cron') == 'true'
    secret = request.args.get('secret')
    valid_secret = os.getenv('WEBHOOK_SECRET_TOKEN')
    
    if not is_cron and (not secret or secret != valid_secret):
        return jsonify({'error': 'Unauthorized', 'message': 'Missing Cron Header or Secret'}), 403

    logger = logging.getLogger('cron_sync')
    drive = current_app.drive_service
    if not drive:
        return jsonify({'error': 'Drive Unavailable'}), 503

    db = next(get_db())
    processed_count = 0
    errors = []

    try:
        from src.config import config
        FOLDER_IN = config.FOLDER_ID_01_ENTRADA_RELATORIOS
        
        # 1. Fetch pending PDF files from Drive Input Folder
        files = drive.list_files(FOLDER_IN, extension='.pdf')
        logger.info(f"🔄 [CRON] Found {len(files)} files in input folder.")

        # 2. Check which ones are NEW (Not in DB)
        processed_file_ids = [r[0] for r in db.query(Inspection.drive_file_id).all()]
        
        # Limit processing batch to avoid Timeout (e.g. 2 files max per run)
        files_to_process = []
        for f in files:
            if f['id'] not in processed_file_ids:
                files_to_process.append(f)
                if len(files_to_process) >= 2: 
                    break
        
        if not files_to_process:
            return jsonify({'status': 'ok', 'message': 'No new files to sync.'})

        # 3. Process Batch
        from src.models_db import Job, JobStatus
        from src.services.processor import processor_service
        
        for file in files_to_process:
            logger.info(f"⏳ [CRON] Processing NEW file: {file['name']} ({file['id']})")
            
            try:
                # Create Job & Inspection Record
                job = Job(
                    type="CRON_SYNC_PROCESS",
                    status=JobStatus.PENDING,
                    input_payload={'file_id': file['id'], 'filename': file['name'], 'source': 'drive_cron'}
                )
                db.add(job)
                
                # Create Pre-Inspection record
                new_insp = Inspection(
                    drive_file_id=file['id'],
                    drive_web_link=file.get('webViewLink'),
                    status=InspectionStatus.PROCESSING
                )
                db.add(new_insp)
                db.commit()

                # Synchronous Processing
                result = processor_service.process_single_file(
                    {'id': file['id'], 'name': file['name']}, 
                    company_id=None, # Will be detected by processor
                    establishment_id=None, # Will be detected
                    job=job
                )
                
                job.status = JobStatus.COMPLETED
                job.finished_at = datetime.utcnow()
                db.commit()
                processed_count += 1
                
            except Exception as e:
                logger.error(f"❌ [CRON] Error processing {file['name']}: {e}")
                errors.append(f"{file['name']}: {str(e)}")
                if 'job' in locals():
                    job.status = JobStatus.FAILED
                    job.error_log = str(e)
                    db.commit()

        return jsonify({
            'status': 'success', 
            'processed': processed_count, 
            'errors': errors
        })

    except Exception as e:
        logger.error(f"❌ [CRON] Fatal Error: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()
