from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from src.database import get_db
from src.tasks import task_manager
from src.models_db import User, UserRole, Company, Establishment, Job, JobStatus
from sqlalchemy.orm import joinedload
from functools import wraps
import uuid
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
            flash('Empresa removida.', 'success')
        else:
            flash('Empresa não encontrada.', 'error')
    except Exception as e:
        db.rollback()
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
        flash(f'Estabelecimento {name} criado!', 'success')
    except Exception as e:
        db.rollback()
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
            flash('Gestor removido.', 'success')
    except Exception as e:
        db.rollback()
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
        success = task_manager.enqueue_job(job.id, payload={"type": "TEST_JOB"})
        
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

@admin_bp.route('/api/jobs')
@login_required
@admin_required
def api_jobs_stats():
    """
    API JSON para alimentar o Monitoramento de Jobs em Tempo Real.
    """
    db = next(get_db())
    try:
        # Fetch Top 50 recent jobs
        jobs = db.query(Job).options(joinedload(Job.company)).order_by(Job.created_at.desc()).limit(50).all()
        
        job_list = []
        for j in jobs:
            # Calc Duration
            duration = None
            if j.created_at and j.finished_at:
                duration = round((j.finished_at - j.created_at).total_seconds(), 2)
            elif j.created_at:
                duration = round((datetime.utcnow() - j.created_at).total_seconds(), 2)
                
            # Maps status to color badge
            status_colors = {
                JobStatus.PENDING: "warning",
                JobStatus.QUEUED: "info",
                JobStatus.PROCESSING: "primary",
                JobStatus.COMPLETED: "success",
                JobStatus.FAILED: "danger"
            }
            
            job_list.append({
                'id': str(j.id),
                'type': j.type,
                'company_name': j.company.name if j.company else "Sistema",
                'status': j.status.value,
                'status_label': j.status.value,
                'status_color': status_colors.get(j.status, "secondary"),
                'cost_input': j.cost_input_brl or 0.0,
                'cost_output': j.cost_output_brl or 0.0,
                'tokens_input': j.cost_tokens_input or 0,
                'tokens_output': j.cost_tokens_output or 0,
                'duration': duration,
                'created_at': j.created_at.isoformat() if j.created_at else None
            })
            
        return jsonify({'jobs': job_list})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()

