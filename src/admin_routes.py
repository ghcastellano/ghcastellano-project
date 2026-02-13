from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from src.models_db import UserRole, AppConfig, JobStatus
from functools import wraps
import os
import logging

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != UserRole.ADMIN:
            flash('Acesso restrito a administradores.', 'error')
            return redirect(url_for('manager.dashboard_manager'))
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route('/')
@login_required
@admin_required
def index():
    from src.container import get_uow
    uow = get_uow()
    try:
        companies = uow.companies.get_all()
        managers = uow.users.get_managers_with_company()
        managers.sort(key=lambda m: m.company.name if m.company else "ZZZ_SemEmpresa")
        return render_template('admin_dashboard.html', companies=companies, managers=managers)
    except Exception as e:
        import traceback
        current_app.logger.error(f"Erro Crítico em Admin Index: {traceback.format_exc()}")
        return f"Erro Interno no Servidor (500). Detalhes: {e}", 500


@admin_bp.route('/company/new', methods=['POST'])
@login_required
@admin_required
def create_company():
    from src.container import get_admin_service
    name = request.form.get('name')
    cnpj = request.form.get('cnpj')

    result = get_admin_service().create_company(name, cnpj)

    if request.accept_mimetypes.accept_json:
        if result.success:
            return jsonify({'success': True, 'company': result.data, 'message': result.message}), 201
        return jsonify({'error': result.message}), 400

    flash(result.message, 'success' if result.success else 'error')
    return redirect(url_for('admin.index'))


@admin_bp.route('/company/<uuid:company_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_company(company_id):
    from src.container import get_admin_service
    result = get_admin_service().delete_company(company_id)

    if request.accept_mimetypes.accept_json:
        if result.success:
            return jsonify({'success': True, 'message': result.message}), 200
        return jsonify({'error': result.message}), 404 if result.error == 'NOT_FOUND' else 500

    flash(result.message, 'success' if result.success else 'error')
    return redirect(url_for('admin.index'))


@admin_bp.route('/establishment/new', methods=['POST'])
@login_required
@admin_required
def create_establishment():
    from src.container import get_uow
    from src.models_db import Establishment
    import uuid

    company_id = request.form.get('company_id')
    name = request.form.get('name')
    drive_id = request.form.get('drive_folder_id')

    if not company_id or not name:
        flash('Empresa e Nome são obrigatórios.', 'error')
        return redirect(url_for('admin.index'))

    uow = get_uow()
    try:
        est = Establishment(id=uuid.uuid4(), company_id=uuid.UUID(company_id), name=name, drive_folder_id=drive_id)
        uow.establishments.add(est)

        # Capture data before commit (SQLAlchemy expires attributes after commit)
        est_id = str(est.id)
        est_name = est.name
        uow.commit()

        if request.accept_mimetypes.accept_json:
            return jsonify({
                'success': True,
                'message': f'Estabelecimento {name} criado!',
                'establishment': {'id': est_id, 'name': est_name},
            }), 201

        flash(f'Estabelecimento {name} criado!', 'success')
    except Exception as e:
        uow.rollback()
        if request.accept_mimetypes.accept_json:
            return jsonify({'error': str(e)}), 500
        flash(f'Erro ao criar estabelecimento: {e}', 'error')
    return redirect(url_for('admin.index'))


@admin_bp.route('/manager/new', methods=['POST'])
@login_required
@admin_required
def create_manager():
    from src.container import get_admin_service

    name = request.form.get('name')
    email = request.form.get('email')
    company_id = request.form.get('company_id')
    password = request.form.get('password', '123456')

    result = get_admin_service().create_manager(name, email, company_id, password)

    if request.accept_mimetypes.accept_json:
        if result.success:
            return jsonify({
                'success': True,
                'manager': {
                    'id': result.data['id'],
                    'name': result.data['name'],
                    'email': result.data['email'],
                    'company_name': result.data.get('company_name', ''),
                    'company_id': result.data.get('company_id', ''),
                },
                'message': result.message,
            }), 201
        return jsonify({'error': result.message}), 400

    flash(result.message, 'success' if result.success else 'error')
    return redirect(url_for('admin.index'))


@admin_bp.route('/manager/<uuid:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_manager(user_id):
    from src.container import get_admin_service
    result = get_admin_service().delete_manager(user_id)

    if request.accept_mimetypes.accept_json:
        if result.success:
            return jsonify({'success': True, 'message': result.message}), 200
        return jsonify({'error': result.message}), 404

    flash(result.message, 'success' if result.success else 'error')
    return redirect(url_for('admin.index'))


@admin_bp.route('/test-job', methods=['POST'])
@login_required
@admin_required
def trigger_test_job():
    from src.container import get_uow
    from src.models_db import Job, JobStatus
    uow = get_uow()
    try:
        company_id = current_user.company_id
        if not company_id:
            first_company = uow.companies.get_all()
            if first_company:
                company_id = first_company[0].id
            else:
                flash("Nenhuma empresa encontrada para associar o Job.", "error")
                return redirect(url_for('admin.index'))

        job = Job(
            id=uuid.uuid4(),
            company_id=company_id,
            type="TEST_JOB",
            status=JobStatus.PENDING,
            input_payload={"delay": 5, "triggered_by": current_user.email},
        )
        uow.jobs.add(job)
        job_id = str(job.id)
        uow.commit()

        flash(f"Job {job_id} criado com sucesso!", "success")
    except Exception as e:
        uow.rollback()
        flash(f"Erro ao criar job: {e}", "error")
    return redirect(url_for('admin.index'))


@admin_bp.route('/company/<uuid:company_id>/update', methods=['POST'])
@login_required
@admin_required
def update_company(company_id):
    from src.container import get_uow
    name = request.form.get('name')
    cnpj = request.form.get('cnpj')

    if not name:
        if request.accept_mimetypes.accept_json:
            return jsonify({'error': 'Nome da empresa é obrigatório.'}), 400
        flash('Nome da empresa é obrigatório.', 'error')
        return redirect(url_for('admin.index'))

    uow = get_uow()
    try:
        company = uow.companies.get_by_id(company_id)
        if not company:
            if request.accept_mimetypes.accept_json:
                return jsonify({'error': 'Empresa não encontrada.'}), 404
            flash('Empresa não encontrada.', 'error')
            return redirect(url_for('admin.index'))

        # Check CNPJ uniqueness (if changed)
        if cnpj and cnpj != company.cnpj:
            existing = uow.companies.get_by_cnpj(cnpj)
            if existing and existing.id != company.id:
                if request.accept_mimetypes.accept_json:
                    return jsonify({'error': f'Já existe uma empresa com o CNPJ {cnpj}.'}), 400
                flash(f'Já existe uma empresa com o CNPJ {cnpj}.', 'error')
                return redirect(url_for('admin.index'))

        company.name = name
        company.cnpj = cnpj
        uow.commit()

        if request.accept_mimetypes.accept_json:
            return jsonify({'success': True, 'message': 'Empresa atualizada!'}), 200
        flash(f'Empresa {name} atualizada!', 'success')
    except Exception as e:
        uow.rollback()
        if request.accept_mimetypes.accept_json:
            return jsonify({'error': str(e)}), 500
        flash(f'Erro ao atualizar: {e}', 'error')
    return redirect(url_for('admin.index'))


@admin_bp.route('/manager/<uuid:user_id>/update', methods=['POST'])
@login_required
@admin_required
def update_manager(user_id):
    from src.container import get_admin_service
    name = request.form.get('name')
    email = request.form.get('email')
    company_id = request.form.get('company_id')
    password = request.form.get('password')

    if not name or not email:
        return jsonify({'error': 'Nome e Email são obrigatórios.'}), 400

    result = get_admin_service().update_manager(user_id, name, email, company_id, password)

    if result.success:
        return jsonify({'success': True, 'message': result.message}), 200
    return jsonify({'error': result.message}), 404 if result.error == 'NOT_FOUND' else 500


@admin_bp.route('/api/monitor')
@login_required
@admin_required
def api_monitor_stats():
    """API for inspection monitoring with cost/token data."""
    from src.container import get_uow
    from src.models_db import Job, Inspection
    import json

    uow = get_uow()
    try:
        jobs = uow.jobs.get_for_monitor(limit=50)
        monitor_list = []

        for job in jobs:
            payload = job.input_payload or {}
            filename = payload.get('filename', 'N/A')
            est_name = payload.get('establishment_name') or payload.get('establishment', 'N/A')
            file_id = payload.get('file_id')

            duration = None
            if job.finished_at and job.created_at:
                duration = round((job.finished_at - job.created_at).total_seconds(), 2)

            cost_usd = (job.cost_input_usd or 0) + (job.cost_output_usd or 0)
            cost_brl = (job.cost_input_brl or 0) + (job.cost_output_brl or 0)
            tokens_in = job.cost_tokens_input or 0
            tokens_out = job.cost_tokens_output or 0

            current_stage = "Upload"
            inspection_status = None
            last_log_message = None

            if file_id:
                inspection = uow.inspections.get_by_drive_file_id(file_id)
                if inspection:
                    inspection_status = inspection.status.value if inspection.status else None
                    stage_map = {
                        'PROCESSING': 'Processando IA',
                        'PENDING_MANAGER_REVIEW': 'Aguardando Gestor',
                        'PENDING_CONSULTANT_VERIFICATION': 'Aguardando Visita',
                        'COMPLETED': 'Concluído',
                        'REJECTED': 'Rejeitado',
                    }
                    current_stage = stage_map.get(inspection_status, current_stage)

                    if inspection.processing_logs and len(inspection.processing_logs) > 0:
                        last_log_message = inspection.processing_logs[-1].get('message', '')

            error_details, error_code = _parse_error_log(job.error_log)

            # Override stage for SKIPPED jobs
            if job.status == JobStatus.SKIPPED:
                current_stage = 'Duplicata Detectada'
                error_code = error_code or 'DUPLICATE'
                if not error_details or error_details == 'Erro desconhecido':
                    # Build message from raw error_log (handles old format without admin_msg)
                    try:
                        raw = json.loads(job.error_log) if isinstance(job.error_log, str) else job.error_log
                        if isinstance(raw, list) and raw:
                            entry = raw[-1]
                        elif isinstance(raw, dict):
                            entry = raw
                        else:
                            entry = {}
                        existing_id = entry.get('existing_id', '')
                        error_details = f'Arquivo duplicado (hash identico a {existing_id})' if existing_id else 'Arquivo ja foi enviado e processado anteriormente.'
                    except Exception:
                        error_details = 'Arquivo ja foi enviado e processado anteriormente.'

            job_type = job.type or 'PROCESS_REPORT'

            monitor_list.append({
                'id': str(job.id),
                'type': job_type,
                'company_id': str(job.company_id) if job.company_id else '',
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
                'attempts': job.attempts or 0,
            })

        return jsonify({'items': monitor_list})
    except Exception as e:
        import traceback
        current_app.logger.error(f"Erro em api_monitor_stats: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/tracker/<uuid:inspection_id>')
@login_required
@admin_required
def tracker_details(inspection_id):
    from src.container import get_uow, get_tracker_service
    uow = get_uow()
    try:
        insp = uow.inspections.get_by_id(inspection_id)
        if not insp:
            return jsonify({'error': 'Not found'}), 404

        data = get_tracker_service().get_tracker_data(insp)
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/recent-errors')
@login_required
@admin_required
def api_recent_errors():
    """API for recent job errors (last 20 FAILED jobs)."""
    from src.container import get_uow
    from src.models_db import Job, JobStatus
    import json

    uow = get_uow()
    try:
        failed_jobs = uow.session.query(Job).filter(
            Job.status.in_([JobStatus.FAILED, JobStatus.SKIPPED])
        ).order_by(Job.created_at.desc()).limit(20).all()

        errors = []
        for job in failed_jobs:
            payload = job.input_payload or {}
            error_msg = ''
            if job.error_log:
                try:
                    raw = json.loads(job.error_log) if isinstance(job.error_log, str) else job.error_log
                    if isinstance(raw, list) and raw:
                        entry = raw[-1]
                        error_msg = entry.get('admin_msg') or entry.get('message') or str(entry)
                    elif isinstance(raw, dict):
                        error_msg = raw.get('admin_msg') or raw.get('message') or raw.get('error') or str(raw)
                    else:
                        error_msg = str(raw)
                except Exception:
                    error_msg = str(job.error_log)[:200]
            elif job.result_details:
                error_msg = job.result_details.get('error', '') if isinstance(job.result_details, dict) else str(job.result_details)

            errors.append({
                'id': str(job.id),
                'status': job.status.value,
                'filename': payload.get('filename', 'N/A'),
                'source': payload.get('source', 'N/A'),
                'company': job.company.name if job.company else 'N/A',
                'error': error_msg[:300],
                'created_at': job.created_at.isoformat() if job.created_at else None,
            })

        return jsonify({'errors': errors})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# --- Settings / Configuracoes ---

SENSITIVE_KEYS = {
    'GCP_OAUTH_TOKEN', 'WHATSAPP_TOKEN', 'SMTP_PASSWORD',
    'OPENAI_API_KEY', 'WEBHOOK_SECRET_TOKEN',
}

CONFIG_GROUPS = {
    'google_drive': {
        'label': 'Google Drive',
        'icon': 'fa-google-drive',
        'keys': [
            {'key': 'GCP_SA_KEY', 'label': 'Service Account JSON (completo)', 'type': 'textarea'},
            {'key': 'GCP_OAUTH_TOKEN', 'label': 'OAuth Token (alternativo ao SA)', 'type': 'textarea'},
            {'key': 'GDRIVE_ROOT_FOLDER_ID', 'label': 'ID da Pasta Raiz', 'type': 'text'},
            {'key': 'FOLDER_ID_01_ENTRADA_RELATORIOS', 'label': 'Pasta Entrada Relatorios', 'type': 'text'},
            {'key': 'FOLDER_ID_02_PLANOS_GERADOS', 'label': 'Pasta Planos Gerados', 'type': 'text'},
            {'key': 'FOLDER_ID_03_PROCESSADOS_BACKUP', 'label': 'Pasta Backup Processados', 'type': 'text'},
            {'key': 'FOLDER_ID_99_ERROS', 'label': 'Pasta Erros', 'type': 'text'},
        ],
    },
    'whatsapp': {
        'label': 'WhatsApp Business API',
        'icon': 'fa-whatsapp',
        'keys': [
            {'key': 'WHATSAPP_TOKEN', 'label': 'Bearer Token (Meta)', 'type': 'password'},
            {'key': 'WHATSAPP_PHONE_ID', 'label': 'Phone ID', 'type': 'text'},
            {'key': 'WHATSAPP_DESTINATION_PHONE', 'label': 'Telefone Padrao', 'type': 'text'},
        ],
    },
    'email_smtp': {
        'label': 'Email (Gmail SMTP)',
        'icon': 'fa-envelope',
        'keys': [
            {'key': 'SMTP_EMAIL', 'label': 'Email Gmail', 'type': 'text'},
            {'key': 'SMTP_PASSWORD', 'label': 'Senha de App (App Password)', 'type': 'password'},
            {'key': 'SMTP_HOST', 'label': 'Servidor SMTP (padrao: smtp.gmail.com)', 'type': 'text'},
            {'key': 'SMTP_PORT', 'label': 'Porta SMTP (padrao: 587)', 'type': 'text'},
        ],
    },
    'openai': {
        'label': 'OpenAI',
        'icon': 'fa-brain',
        'keys': [
            {'key': 'OPENAI_API_KEY', 'label': 'API Key', 'type': 'password'},
        ],
    },
    'security': {
        'label': 'Seguranca',
        'icon': 'fa-shield-alt',
        'keys': [
            {'key': 'WEBHOOK_SECRET_TOKEN', 'label': 'Webhook Secret Token', 'type': 'password'},
        ],
    },
}


def _mask_value(key, value):
    if not value:
        return None
    if key in SENSITIVE_KEYS:
        return '****' if len(value) <= 8 else '****' + value[-4:]
    return value


def _parse_error_log(error_log):
    """Parse error log JSON and return (details, code) tuple."""
    if not error_log:
        return None, None
    try:
        import json
        error_data = json.loads(error_log) if isinstance(error_log, str) else error_log

        if isinstance(error_data, list) and len(error_data) > 0:
            latest = error_data[-1]
            code = latest.get('code', 'ERRO')
            details = latest.get('admin_msg') or latest.get('user_msg') or latest.get('message', 'Erro desconhecido')
            if len(error_data) > 1:
                details = f"[{len(error_data)} erros] {details}"
            return details, code
        elif isinstance(error_data, dict):
            code = error_data.get('code', 'ERRO')
            details = error_data.get('admin_msg') or error_data.get('user_msg') or error_data.get('message', 'Erro desconhecido')
            return details, code
        else:
            return str(error_data)[:100], None
    except Exception:
        return str(error_log)[:100], 'PARSE_ERROR'


@admin_bp.route('/api/settings')
@login_required
@admin_required
def get_settings():
    from src.container import get_uow
    uow = get_uow()
    try:
        configs = uow.config.get_all()
        db_configs = {c.key: c.value for c in configs}

        result = {}
        for group_id, group_def in CONFIG_GROUPS.items():
            group_data = {'label': group_def['label'], 'icon': group_def['icon'], 'fields': []}
            for field in group_def['keys']:
                key = field['key']
                db_val = db_configs.get(key)
                env_val = os.getenv(key)
                effective = db_val if (db_val is not None and str(db_val).strip()) else env_val

                group_data['fields'].append({
                    'key': key,
                    'label': field['label'],
                    'type': field['type'],
                    'value_masked': _mask_value(key, effective),
                    'is_configured': bool(effective),
                    'source': 'db' if (db_val and str(db_val).strip()) else ('env' if env_val else None),
                })
            result[group_id] = group_data
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/settings', methods=['POST'])
@login_required
@admin_required
def save_settings():
    from src.container import get_uow
    uow = get_uow()
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Dados invalidos.'}), 400

        all_valid_keys = set()
        for group in CONFIG_GROUPS.values():
            for field in group['keys']:
                all_valid_keys.add(field['key'])

        saved_count = 0
        for key, value in data.items():
            if key not in all_valid_keys:
                continue
            if value and str(value).startswith('****'):
                continue
            uow.config.set_value(key, value if value else None)
            saved_count += 1

        uow.commit()
        return jsonify({'success': True, 'message': f'{saved_count} configuracao(oes) salva(s).'})
    except Exception as e:
        uow.rollback()
        return jsonify({'error': str(e)}), 500
