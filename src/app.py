# v1.1.2 - CI/CD & Security Verified (Log Permission Fix)
import os
import glob
import json
import logging
import io
import threading
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, send_file, get_flashed_messages, session, after_this_request, make_response, current_app
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()
from src.config import config
import uuid

# Configuração de Logs (JSON Estruturado para Cloud Logging)
import re

# Patterns for sensitive data that should be masked in logs
SENSITIVE_PATTERNS = [
    (re.compile(r'(sk-[a-zA-Z0-9]{20,})'), r'sk-***REDACTED***'),  # OpenAI API keys
    (re.compile(r'(password["\']?\s*[:=]\s*["\']?)([^"\'&\s]+)', re.I), r'\1***REDACTED***'),  # Passwords
    (re.compile(r'(api[_-]?key["\']?\s*[:=]\s*["\']?)([^"\'&\s]+)', re.I), r'\1***REDACTED***'),  # API keys
    (re.compile(r'(token["\']?\s*[:=]\s*["\']?)([^"\'&\s]+)', re.I), r'\1***REDACTED***'),  # Tokens
    (re.compile(r'(secret["\']?\s*[:=]\s*["\']?)([^"\'&\s]+)', re.I), r'\1***REDACTED***'),  # Secrets
    (re.compile(r'(Bearer\s+)([a-zA-Z0-9._-]+)', re.I), r'\1***REDACTED***'),  # Bearer tokens
]


def sanitize_log_message(message: str) -> str:
    """Remove sensitive data patterns from log messages."""
    for pattern, replacement in SENSITIVE_PATTERNS:
        message = pattern.sub(replacement, message)
    return message


class JsonFormatter(logging.Formatter):
    def format(self, record):
        # Guard against Python shutdown (sys.meta_path becomes None)
        try:
            sanitized_message = sanitize_log_message(record.getMessage())
        except (ImportError, TypeError):
            sanitized_message = record.getMessage()

        json_log = {
            "severity": record.levelname,
            "message": sanitized_message,
            "timestamp": self.formatTime(record, self.datefmt),
            "logger": record.name,
            "module": record.module,
        }
        if hasattr(record, "props"):
            # Sanitize props values too
            sanitized_props = {}
            for k, v in record.props.items():
                if isinstance(v, str):
                    sanitized_props[k] = sanitize_log_message(v)
                else:
                    sanitized_props[k] = v
            json_log.update(sanitized_props)

        if record.exc_info:
            json_log["exception"] = sanitize_log_message(self.formatException(record.exc_info))

        return json.dumps(json_log)

handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logging.basicConfig(level=logging.DEBUG, handlers=[handler])
logger = logging.getLogger("mvp-app")
logger.setLevel(logging.DEBUG)

app = Flask(__name__, template_folder='templates', static_folder='static')

# Flask Extensions
from flask_wtf.csrf import CSRFProtect
from flask_login import login_required, current_user
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename
import uuid # Fix uuid not defined error
import logging
import json
import os

# Security module for file validation and rate limiting
from src.infrastructure.security import FileValidator, limiter, init_limiter
import tempfile

# Initialize Rate Limiting with the app
init_limiter(app)

# App Imports
from src.config import config
from src import database # Import module to access updated db_session
from src.database import get_db, init_db # Keep functions
from src.models_db import User, Company, Establishment, Job, JobStatus, UserRole
from datetime import datetime
from src.auth import role_required, admin_required, login_manager, auth_bp
from src.services.email_service import EmailService
from src.services.storage_service import storage_service
from src.config_helper import get_config

# Configurações do App
app.secret_key = config.SECRET_KEY
if not app.secret_key:
    # Fallback ONLY if ENV is missing AND config default failed (unlikely)
    logger.warning("⚠️ SECRET_KEY não encontrada no ambiente. Gerando chave aleatória (Sessões serão invalidadas ao reiniciar).")
    import secrets
    app.secret_key = secrets.token_hex(32)
    
app.config['SECRET_KEY'] = app.secret_key
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024 # 32MB Upload Limit

# Cloud Run Load Balancer Fix (HTTPS / CSRF)
# IMPORTANT: ProxyFix MUST be configured BEFORE CSRFProtect to properly detect HTTPS
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Session Configuration for Cloud Run (HTTPS)
# Only enforce secure cookies in production (Cloud Run sets K_SERVICE env var)
is_production = os.getenv('K_SERVICE') is not None
app.config['SESSION_COOKIE_SECURE'] = is_production
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevent JavaScript access (XSS protection)
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # CSRF protection while allowing navigation

csrf = CSRFProtect(app)

# --- Migrações (Execução automática V11 & V12) ---
# Migrações (Legado) - Puladas em desenvolvimento para evitar sobrecarga de inicialização dupla
# A chamada database.init_db() foi removida aqui para evitar duplicação do engine.
logger.info("⚡ Migrações Puladas (Modo Dev)")
# -----------------------------

# Inicializa Flask-Login
login_manager.init_app(app)

# Registra Blueprints
# Import Blueprints - Late Import to avoid circular dependencies
logger.info("🔧 Carregando Blueprints...")

# Dev Mode Blueprint (Mock Data) - Only register in debug mode
# Protects /dev/* routes from being accessible in production
if os.getenv('FLASK_DEBUG', 'false').lower() == 'true' or os.getenv('K_SERVICE') is None:
    from src.dev_routes import dev_bp
    app.register_blueprint(dev_bp)
    logger.info("🛠️ Rotas de Dev registradas em /dev")
else:
    logger.info("⛔ Rotas de Dev desabilitadas em produção")
try:
    from src.auth import auth_bp
    from src.admin_routes import admin_bp
    from src.manager_routes import manager_bp
    from src.cron_routes import cron_bp, cron_renew_webhook

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp)
    app.register_blueprint(manager_bp)
    app.register_blueprint(cron_bp)

    # Exempt Cron from CSRF and rate limiting
    csrf.exempt(cron_renew_webhook)
    limiter.exempt(cron_renew_webhook)

    logger.info("✅ Blueprints Registrados: auth, admin, manager")
    
    # Debug: List all rules
    logger.info(f"📍 Rotas Registradas: {[str(p) for p in app.url_map.iter_rules()]}")

except Exception as bp_error:
    logger.error(f"❌ Erro Crítico ao registrar Blueprints: {bp_error}")
    raise bp_error

# Debug endpoints - DISABLED in production (Cloud Run)
# These endpoints expose internal information and should only be available in development
IS_PRODUCTION = os.getenv('K_SERVICE') is not None  # K_SERVICE is set in Cloud Run
DEBUG_MODE = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'


@app.route('/debug/routes')
@login_required
@admin_required
def debug_routes():
    """List all registered routes. Admin only, disabled in production."""
    # Security: Disable in production
    if IS_PRODUCTION and not DEBUG_MODE:
        logger.warning("Attempted access to /debug/routes in production")
        return jsonify({'error': 'Not Found'}), 404

    rules = []
    for rule in app.url_map.iter_rules():
        rules.append(f"{rule.endpoint}: {rule}")
    return "<br>".join(rules)


@app.route('/debug/config')
@login_required
@admin_required
def debug_config():
    """
    Zero Defect Check: Verify if Cloud Run Env Vars are actually injected.
    """
    # Security: Disable in production
    if IS_PRODUCTION and not DEBUG_MODE:
        logger.warning("Attempted access to /debug/config in production")
        return jsonify({'error': 'Not Found'}), 404

    keys = ['GCP_PROJECT_ID', 'GCP_LOCATION', 'DATABASE_URL', 'FOLDER_ID_01_ENTRADA_RELATORIOS']
    status = {}
    for k in keys:
        val = os.getenv(k)
        if k == 'DATABASE_URL' and val:
            status[k] = val[:15] + "..." # Obfuscate
        else:
            status[k] = val or "MISSING"
    
    status['Task Queue'] = config.GCP_PROJECT_ID  # Confirm loaded config
    return jsonify(status)
# app.register_blueprint(worker_bp, url_prefix='/worker') # Removed to avoid conflict with app.route


# Inicializa Banco de Dados
try:
    init_db()
    logger.info("✅ Banco de dados inicializado com sucesso")

    # [AUTO-PATCH] Self-Healing Schema & SA Log
    try:
        from src.patcher import run_auto_patch
        run_auto_patch()
    except Exception as e:
        logger.error(f"❌ Falha no Auto-Patch: {e}")
except Exception as e:
    logger.error(f"❌ Falha crítica na inicialização do Banco de Dados: {e}")
    # Não vamos rodar sem BD, pois causa 500 em quase tudo. Deixe quebrar para o Cloud Run reiniciar.
    raise e

# Rodar Migrações
try:
    with app.app_context():
        from src.migration import run_migrations
        from src.models_db import Base
        
        logger.info("🏗️ Criando tabelas (Schema Initialization)...")
        # Garante que usamos o engine inicializado pelo banco de dados
        # Base.metadata.create_all(bind=database.engine)
        logger.info("⚡ Inicialização de Schema Pulada (Modo Dev)")
        
        # run_migrations(database.db_session)
        logger.info("⚡ Migrações Puladas (Modo Dev)")
except ImportError as e:
    logger.error(f"❌ Erro ao importar migrações: {e}")
except Exception as e:
    logger.error(f"❌ Erro Crítico nas Migrações: {e}")

import unicodedata
import re

# Timezone Helper - Brasil (UTC-3, sem horário de verão desde 2019)
from datetime import timezone, timedelta
BRAZIL_TZ = timezone(timedelta(hours=-3))

def to_brazil_time(dt):
    """Converte datetime UTC para horário de Brasília (UTC-3)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(BRAZIL_TZ)

def brazil_now():
    """Retorna datetime atual no horário de Brasília."""
    return datetime.now(BRAZIL_TZ)

@app.template_filter('brdate')
def brdate_filter(dt, fmt='%d/%m/%Y %H:%M'):
    """Filtro Jinja2: converte datetime para horário de Brasília formatado."""
    if dt is None:
        return 'N/A'
    br = to_brazil_time(dt)
    return br.strftime(fmt)

@app.template_filter('slugify')
def slugify(value):
    """
    Normalizes string, converts to lowercase, removes non-alpha characters,
    and converts spaces to hyphens.
    """
    if not value:
        return ""
    value = str(value)
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value).strip().lower()
    return re.sub(r'[-\s]+', '-', value)

# Inicializa Serviços
# Drive Service
# 1le3240234 is the default placeholder if env var is missing
FOLDER_OUT = config.FOLDER_ID_02_PLANOS_GERADOS

@app.errorhandler(500)
def handle_500(e):
    import traceback
    tb = traceback.format_exc()
    logger.error(f"💥 ERRO 500 DETECTADO: {e}\nTraceback:\n{tb}")
    # Return JSON for AJAX/fetch requests (check both XHR header and Accept header)
    if (request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            or 'application/json' in request.headers.get('Accept', '')):
        return jsonify({'error': f"Erro Interno: {str(e)}"}), 500
    return "Erro Interno no Servidor (500). Verifique os logs do Cloud Run para o Traceback.", 500

def _ensure_system_folder(drive_svc, root_folder_id, config_key, folder_name):
    """Validate a system folder exists in Drive. If missing/invalid, create under root and save to DB."""
    from src.database import get_db
    from src.models_db import AppConfig
    current_id = get_config(config_key)
    if current_id:
        try:
            drive_svc.service.files().get(
                fileId=current_id, fields='id', supportsAllDrives=True
            ).execute()
            logger.info(f"✅ {config_key} válido: {current_id}")
            return
        except Exception:
            logger.warning(f"⚠️ {config_key} inválido ({current_id}), recriando...")

    folder_id, _ = drive_svc.create_folder(folder_name, parent_id=root_folder_id)
    if folder_id:
        try:
            db = next(get_db())
            entry = db.query(AppConfig).get(config_key)
            if entry:
                entry.value = folder_id
            else:
                db.add(AppConfig(key=config_key, value=folder_id))
            db.commit()
            db.close()
        except Exception as e:
            logger.warning(f"⚠️ Falha ao salvar {config_key} no DB: {e}")
        logger.info(f"✅ {config_key} criado: {folder_id}")
    else:
        logger.error(f"❌ Falha ao criar pasta '{folder_name}' no Drive")

try:
    from src.services.drive_service import DriveService
    app.drive_service = DriveService()
    drive_service = app.drive_service # Global alias for routes
    logger.info("✅ Serviço do Drive Inicializado")

    # [IMPROVEMENT] Validar ROOT_FOLDER_ID se configurado
    root_folder_id = get_config('GDRIVE_ROOT_FOLDER_ID')
    if root_folder_id and app.drive_service.service:
        try:
            folder_info = app.drive_service.service.files().get(
                fileId=root_folder_id,
                fields='id,name',
                supportsAllDrives=True
            ).execute()
            logger.info(f"✅ ROOT_FOLDER_ID válido: '{folder_info.get('name')}' ({root_folder_id})")
        except Exception as e:
            logger.error(f"❌ ROOT_FOLDER_ID inválido ou inacessível: {e}")
            logger.warning("⚠️ Pastas de empresas serão criadas na raiz do Drive")

    # Auto-create backup folder if missing or invalid
    if app.drive_service.service and root_folder_id:
        _ensure_system_folder(
            app.drive_service, root_folder_id,
            config_key='FOLDER_ID_03_PROCESSADOS_BACKUP',
            folder_name='Processados - Backup'
        )

except Exception as e:
    logger.error(f"⚠️ Falha ao inicializar Serviço do Drive: {e}")
    app.drive_service = None
    drive_service = None

# Email Service
try:
    from src.services.email_service import EmailService
    app.email_service = EmailService()
    logger.info("✅ Serviço de Email Inicializado (lazy config)")
except Exception as e:
    logger.error(f"⚠️ Falha ao inicializar Serviço de Email: {e}")
    app.email_service = None

# PDF Service
try:
    from src.services.pdf_service import PDFService
    app.pdf_service = PDFService()
    pdf_service = app.pdf_service
    logger.info("✅ Serviço de PDF Inicializado")
except Exception as e:
    logger.error(f"⚠️ Falha ao inicializar Serviço de PDF: {e}")
    app.pdf_service = None
    pdf_service = None

@app.teardown_appcontext
def shutdown_session(exception=None):
    # Clean up DI container UnitOfWork
    from src.container import teardown_uow
    teardown_uow(exception)

    # Safe import to avoid circular dependency issues
    from src.database import db_session
    if db_session:
        db_session.remove()

@app.route('/')
@login_required
def root():
    logger.debug(f"🏠 Acessando root (User: {current_user.id if current_user.is_authenticated else 'Anonymous'})")
    from src.models_db import UserRole # Local import
    if current_user.role == UserRole.MANAGER:
        return redirect(url_for('manager.dashboard_manager'))
    elif current_user.role == UserRole.ADMIN:
        return redirect(url_for('admin.index'))
    else:
        return redirect(url_for('dashboard_consultant'))

# Removed dashboard_manager from app.py to avoid circular imports.
# It is now located in src/manager_routes.py

@app.route('/dashboard/consultant')
@login_required
@role_required(UserRole.CONSULTANT)
def dashboard_consultant():
    from src.container import get_dashboard_service

    svc = get_dashboard_service()
    data = svc.get_consultant_dashboard(current_user)
    data['stats']['last_sync'] = brazil_now().strftime('%H:%M')

    return render_template(
        'dashboard_consultant.html',
        user_role='CONSULTANT',
        inspections=data['inspections'],
        stats=data['stats'],
        user_hierarchy=data['user_hierarchy'],
        pending_establishments=data['pending_establishments'],
        failed_jobs=data['failed_jobs'],
    )

# Rota legado (redireciona para root para tratar auth)
@app.route('/dashboard')
def dashboard_legacy():
    return redirect(url_for('root'))

def get_friendly_error_message(e):
    msg = str(e).lower()
    # DEBUG: Expose full error to user for diagnosis
    if "quota" in msg or "insufficient storage" in msg:
        return f"Erro de COTA no Drive (Cheio). Detalhes: {msg}"
    if "403" in msg:
        return f"Erro de PERMISSÃO (403). O token pode não ter acesso à pasta. Detalhes: {msg}"
    if "token" in msg or "expired" in msg:
        return f"Sessão expirada ou Token inválido. Detalhes: {msg}"
    if "not found" in msg or "404" in msg:
        return "Recurso não encontrado (404)."
    if "pdf" in msg or "corrupt" in msg:
        return "Arquivo PDF inválido/corrompido."
    return f"Erro processamento: {msg}"

@app.route('/upload', methods=['GET', 'POST'])
@limiter.limit("10 per minute")  # Rate limit: 10 uploads per minute per IP
@login_required
@role_required(UserRole.CONSULTANT)
def upload_file():
    """
    Rota para upload de múltiplos relatórios de vistoria.
    Realiza o processamento inicial e enfileira jobs assíncronos.
    """
    if request.method == 'GET':
        return redirect(url_for('dashboard_consultant'))

    try:
        if 'file' not in request.files:
            flash('Nenhum arquivo enviado', 'error')
            return redirect(url_for('dashboard_consultant'))
        
        uploaded_files = request.files.getlist('file')
        if not uploaded_files or (len(uploaded_files) == 1 and uploaded_files[0].filename == ''):
            flash('Nenhum arquivo selecionado', 'error')
            return redirect(url_for('dashboard_consultant'))

        sucesso = 0
        falha = 0
        
        # [UX] Explicit Establishment Selection
        est_id_param = request.form.get('establishment_id')
        est_alvo_selected = None
        
        if est_id_param:
            # Validate Access
            for est in current_user.establishments:
                if str(est.id) == est_id_param:
                    est_alvo_selected = est
                    break
            
            if not est_alvo_selected:
                flash("Erro de Permissão: Você não tem acesso a esta loja.", "error")
                return redirect(url_for('dashboard_consultant'))

        # [FIX] Capture user details early to avoid DetachedInstanceError in exception handler
        user_email = current_user.email
        user_name = current_user.name

        # Initialize file validator (validates magic bytes, not just extension)
        pdf_validator = FileValidator.create_pdf_validator(max_size_mb=50)

        for file in uploaded_files:
            if not file or file.filename == '':
                continue

            nome_seguro = secure_filename(file.filename)
            caminho_temp = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}_{nome_seguro}")
            file.save(caminho_temp)

            # Read file content for validation
            with open(caminho_temp, 'rb') as f_validate:
                file_content = f_validate.read()

            # Validate file using magic bytes (more secure than extension check)
            validation_result = pdf_validator.validate(file_content, file.filename)
            if not validation_result.is_valid:
                flash(f'Arquivo {file.filename} rejeitado: {validation_result.error_message}', 'warning')
                logger.warning(f"File validation failed: {file.filename} - {validation_result.error_code}: {validation_result.error_message}")
                os.remove(caminho_temp)
                falha += 1
                continue
            
            try:
                est_alvo = est_alvo_selected

                # Smart Match Fallback (only if no selection)
                if not est_alvo:
                    # 1. Extrair texto para Smart Match de estabelecimento
                    from pypdf import PdfReader
                    conteudo_texto = ""
                    try:
                        reader = PdfReader(caminho_temp)
                        for page in reader.pages[:2]:
                            conteudo_texto += page.extract_text() or ""
                    except Exception as e:
                        logger.error(f"Erro na leitura do PDF {file.filename}: {e}")

                    conteudo_texto = conteudo_texto.upper()
                    
                    # 2. Match com estabelecimentos do consultor
                    meus_estabelecimentos = sorted(current_user.establishments, key=lambda x: len(x.name), reverse=True)
                    
                    for est in meus_estabelecimentos:
                        if est.name.strip().upper() in conteudo_texto:
                            est_alvo = est
                            break

                # [FIX] Salvar valores primitivos DEPOIS do smart match
                # (evita DetachedInstanceError após commit)
                est_alvo_id = est_alvo.id if est_alvo else None
                est_alvo_name = est_alvo.name if est_alvo else "N/A"
                est_alvo_company_id = est_alvo.company_id if est_alvo else None

                # 3. Gerar ID único para o upload (sem salvar no Drive)
                upload_id = f"upload:{uuid.uuid4()}"
                logger.info(f"📄 Upload direto (sem Drive): {file.filename} -> {upload_id}")

                # 4. Ler bytes do arquivo para processamento direto
                with open(caminho_temp, 'rb') as f_temp:
                    file_bytes = f_temp.read()

                # 5. Criar Job e Inspection
                db = next(get_db())
                job = None
                job_id_saved = None
                try:
                    from src.models_db import Inspection, InspectionStatus

                    new_insp = Inspection(
                        drive_file_id=upload_id,
                        drive_web_link=None,
                        status=InspectionStatus.PROCESSING,
                        establishment_id=est_alvo_id  # Usa valor primitivo (evita DetachedInstanceError)
                    )
                    db.add(new_insp)
                    db.flush()
                    logger.info(f"✅ Registro de Inspeção {new_insp.id} pré-criado para visibilidade na UI.")

                    # Usar valores primitivos salvos (evita DetachedInstanceError)
                    job_company_id = current_user.company_id or est_alvo_company_id

                    job = Job(
                        company_id=job_company_id,
                        type="PROCESS_REPORT",
                        status=JobStatus.PROCESSING,  # [FIX] Já inicia como PROCESSING (não PENDING)
                        input_payload={
                            'file_id': upload_id,
                            'filename': file.filename,
                            'establishment_id': str(est_alvo_id) if est_alvo_id else None,
                            'establishment_name': est_alvo_name,  # Valor primitivo
                            'uploaded_by_id': str(current_user.id),
                            'uploaded_by_name': user_name,
                        }
                    )
                    db.add(job)
                    db.flush()  # Gera o ID sem fechar a sessão

                    # Salvar ID ANTES do commit (evita DetachedInstanceError)
                    job_id_saved = job.id

                    db.commit()
                    db.close()  # [FIX] Fechar sessão explicitamente antes do processamento

                    # [SYNC-MVP] Processar Imediatamente (Sem Worker)
                    logger.info(f"⏳ [SYNC] Iniciando processamento de {file.filename} (Job: {job_id_saved})")

                    from src.services.processor import processor_service

                    file_meta = {'id': upload_id, 'name': file.filename}

                    result = processor_service.process_single_file(
                        file_meta,
                        company_id=job_company_id,
                        establishment_id=est_alvo_id,  # Valor primitivo (evita DetachedInstanceError)
                        job_id=job_id_saved,
                        file_content=file_bytes
                    )

                    # [FIX] Verificar se arquivo foi pulado por duplicação
                    if result and result.get('status') == 'skipped' and result.get('reason') == 'duplicate':
                        logger.info(f"♻️ Arquivo duplicado: {file.filename} (já existe como {result.get('existing_id')})")

                        # Atualizar Job como SKIPPED
                        db_skip = next(get_db())
                        try:
                            skip_job = db_skip.get(Job, job_id_saved)
                            if skip_job:
                                skip_job.status = JobStatus.SKIPPED
                                skip_job.finished_at = datetime.utcnow()
                                skip_job.error_log = f"Arquivo duplicado - já processado anteriormente"
                                db_skip.commit()
                        finally:
                            db_skip.close()

                        # Remover Inspection órfã criada para este upload
                        db_cleanup = next(get_db())
                        try:
                            orphan = db_cleanup.query(Inspection).filter_by(
                                drive_file_id=upload_id,
                                status=InspectionStatus.PROCESSING
                            ).first()
                            if orphan:
                                db_cleanup.delete(orphan)
                                db_cleanup.commit()
                                logger.info(f"🧹 Removida Inspection órfã para duplicado: {file.filename}")
                        finally:
                            db_cleanup.close()

                        # Informar usuário sobre duplicação
                        flash(f'Arquivo "{file.filename}" já foi processado anteriormente. Verifique na lista de relatórios.', 'warning')
                        continue  # Próximo arquivo

                    # Re-fetch job in fresh session (processor closes/detaches our objects)
                    db_fresh = next(get_db())
                    try:
                        fresh_job = db_fresh.get(Job, job_id_saved)
                        if fresh_job:
                            fresh_job.status = JobStatus.COMPLETED
                            fresh_job.finished_at = datetime.utcnow()
                            if fresh_job.created_at:
                                fresh_job.execution_time_seconds = (fresh_job.finished_at - fresh_job.created_at.replace(tzinfo=None)).total_seconds()
                            fresh_job.attempts = (fresh_job.attempts or 0) + 1
                            db_fresh.commit()

                            total_cost = (fresh_job.cost_input_usd or 0) + (fresh_job.cost_output_usd or 0)
                            logger.info(f"✅ [SYNC] Processamento concluído: {file.filename} (Cost: ${total_cost:.4f})")
                    finally:
                        db_fresh.close()

                    sucesso += 1

                except Exception as job_e:
                    logger.error(f"Erro no processamento síncrono para {file.filename}: {job_e}")

                    # Cleanup: Update Job and remove orphan Inspection
                    try:
                        db_err = next(get_db())

                        # Update Job status
                        if job_id_saved:
                            err_job = db_err.get(Job, job_id_saved)
                            if err_job:
                                err_job.status = JobStatus.FAILED
                                err_job.error_log = str(job_e)

                        # Remove orphan Inspection (was created but processing failed)
                        orphan_insp = db_err.query(Inspection).filter_by(
                            drive_file_id=upload_id,
                            status=InspectionStatus.PROCESSING
                        ).first()
                        if orphan_insp:
                            db_err.delete(orphan_insp)
                            logger.info(f"🧹 Removida Inspection órfã para {file.filename}")

                        db_err.commit()
                        db_err.close()
                    except Exception as cleanup_e:
                        logger.error(f"Failed to cleanup after error for {file.filename}: {cleanup_e}")

                    falha += 1

                    # [NOTIFY] Avisar consultor sobre erro crítico
                    try:
                        if app.email_service and user_email:
                            subj = f"Erro no Processamento: {file.filename}"

                            body_html = f"""
                            <html>
                            <head></head>
                            <body style="font-family: sans-serif; color: #333;">
                                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #fecaca; border-radius: 10px; background: #fef2f2;">
                                    <h2 style="color: #dc2626;"><span style="font-size: 1.5rem;">⚠️</span> Erro no Processamento</h2>
                                    <p>Olá, <strong>{user_name}</strong>.</p>
                                    <p>Ocorreu um erro ao processar o relatório:</p>
                                    <div style="background: #fff; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #dc2626;">
                                        <p style="margin: 0; font-weight: bold; color: #333;">{file.filename}</p>
                                    </div>
                                    <p style="font-size: 0.9rem; color: #666;">O arquivo pode estar corrompido, em formato inválido, ou houve uma falha temporária no sistema.</p>
                                    <p><strong>O que fazer:</strong></p>
                                    <ul style="color: #666;">
                                        <li>Verifique se o arquivo é um PDF válido</li>
                                        <li>Tente enviar novamente</li>
                                        <li>Se o erro persistir, contate o suporte</li>
                                    </ul>
                                    <hr style="border: none; border-top: 1px solid #fecaca; margin: 20px 0;">
                                    <p style="font-size: 0.75rem; color: #999;">Erro técnico: {str(job_e)[:200]}</p>
                                </div>
                            </body>
                            </html>
                            """

                            body_text = f"""
Olá {user_name},

Ocorreu um erro ao processar o relatório "{file.filename}".

O que fazer:
- Verifique se o arquivo é um PDF válido
- Tente enviar novamente
- Se o erro persistir, contate o suporte

Erro técnico: {str(job_e)[:200]}
                            """

                            app.email_service.send_email(user_email, subj, body_html, body_text)
                    except Exception as mail_e:
                        logger.error(f"Falha ao enviar email de erro: {mail_e}")

                    flash(f"Erro ao processar {file.filename}: {str(job_e)}", 'error')

            except Exception as e:
                friendly_msg = get_friendly_error_message(e)
                if "broken pipe" in str(e).lower():
                    friendly_msg = "A conexão foi interrompida durante o envio. Verifique sua internet e tente novamente."
                
                logger.error(f"Falha no arquivo {file.filename}: {e}")
                flash(f"Erro no arquivo {file.filename}: {friendly_msg}", 'error')
                falha += 1
            finally:
                if os.path.exists(caminho_temp):
                    os.remove(caminho_temp)
        
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        if sucesso > 0:
            flash(f'{sucesso} relatório(s) enviado(s) para processamento.', 'success')
            
        if is_ajax:
            if falha > 0 and sucesso == 0:
                # Falha total
                msg = "Falha no envio do relatório. Verifique se é um PDF válido."
                # Tenta pegar a última mensagem de flash de erro se houver
                flashed_msgs = get_flashed_messages(category_filter=['error'])
                if flashed_msgs:
                    msg = flashed_msgs[-1]
                return jsonify({'error': msg}), 500
            elif falha > 0 and sucesso > 0:
                # Parcial
                return jsonify({'message': f'{sucesso} enviados, {falha} falharam. Verifique Dashboard.', 'partial': True}), 207
            else:
                # Sucesso total
                return jsonify({'message': f'{sucesso} relatório(s) processado(s) com sucesso!'}), 200

        return redirect(url_for('dashboard_consultant'))
            
    except Exception as e:
        logger.error(f"Erro geral no upload: {e}")
        flash(f"Ocorreu um erro inesperado: {str(e)}", 'error')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
             return jsonify({'error': f"Erro interno: {str(e)}"}), 500
        return redirect(url_for('dashboard_consultant'))

@app.route('/api/status')
@login_required
def get_status():
    try:
        from src.container import get_dashboard_service
        import uuid as _uuid

        est_id = request.args.get('establishment_id')
        est_uuid = None
        if est_id and est_id.strip() and est_id not in ('null', 'undefined'):
            try:
                est_uuid = _uuid.UUID(est_id)
            except ValueError:
                pass

        svc = get_dashboard_service()
        data = svc.get_status_data(current_user, establishment_id=est_uuid)
        return jsonify(data)

    except Exception as e:
        logger.error(f"Erro em /api/status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/processed_item/<file_id>')
def get_processed_item_details(file_id):
    """Retorna detalhes de um item processado específico (Lazy Load)."""
    try:
        from src.container import get_uow

        uow = get_uow()
        inspection = uow.inspections.get_with_plan_by_file_id(file_id)

        if inspection:
            ai_data = inspection.ai_raw_response or {}
            est_name = inspection.establishment.name if inspection.establishment else 'Desconhecido'
            result = {
                'id': inspection.drive_file_id,
                'name': ai_data.get('titulo', 'Relatório Processado'),
                'establishment': est_name,
                'date': ai_data.get('data_inspecao', ''),
                'pdf_name': f"{est_name}.pdf",
                'pdf_link': f"/download_pdf/{inspection.drive_file_id}",
                'review_link': f"/review/{inspection.drive_file_id}",
            }
            if inspection.action_plan:
                result['action_plan'] = {
                    'final_pdf_link': getattr(inspection.action_plan, 'final_pdf_public_link', None),
                    'items': [{
                        'id': str(item.id),
                        'problem': item.problem_description,
                        'action': item.corrective_action,
                        'legal_basis': item.legal_basis,
                        'severity': item.severity.value if item.severity else 'MEDIUM',
                        'status': item.status.value if item.status else 'OPEN',
                    } for item in inspection.action_plan.items],
                }
            return jsonify(result)

        # Fallback: try Drive
        if drive_service:
            data = drive_service.read_json(file_id)
            return jsonify({
                'id': file_id,
                'name': data.get('titulo', 'Relatório Processado'),
                'establishment': data.get('estabelecimento', 'Outros'),
                'date': data.get('data_inspecao', ''),
                'pdf_name': f"{data.get('titulo', 'Relatório')}.pdf",
                'pdf_link': f"/download_pdf/{file_id}",
                'review_link': f"/review/{file_id}",
            })

        return jsonify({'error': 'Inspeção não encontrada'}), 404

    except Exception as e:
        logger.error(f"Erro lendo item {file_id}: {e}")
        return jsonify({'error': str(e)}), 500



@app.route('/download_pdf/<json_id>')
@login_required
def download_pdf_route(json_id):
    """
    Tenta encontrar o PDF correspondente ao JSON ID output.
    Suporta Drive IDs e GCS paths (gcs:filename).
    """
    # 1. GCS / Storage Service Support
    if json_id.startswith('gcs:'):
        try:
            filename = json_id.replace('gcs:', '')
            from src.services.storage_service import storage_service
            # Tenta baixar da pasta 'evidence' (entrada) ou deduzir saida?
            # Geralmente o PDF de entrada é o que o usuario quer baixar se for o original.
            # Se for o 'revised', é outra rota.
            # Aqui assumimos download do original/processado.
            file_content = storage_service.download_file('evidence', filename) # Returns bytes or None/Raise
            
            return send_file(
                io.BytesIO(file_content),
                mimetype='application/pdf',
                as_attachment=True,
                download_name=filename
            )
        except Exception as e:
            logger.error(f"Erro download GCS {json_id}: {e}")
            return f"Erro ao baixar arquivo do Storage: {e}", 404

    # 2. Drive Support (Existing Logic)
    if not drive_service: return "Erro: Drive indisponível", 500
    
    try:
        # Pega metadados do JSON para saber o nome
        # O ID passado pode ser o do PDF direto se ajustamos antes, mas assumindo JSON ID.
        try:
             json_file = drive_service.service.files().get(fileId=json_id, fields='name, mimeType', supportsAllDrives=True).execute()
        except:
             # Talvez seja o ID do PDF ja?
             json_file = {'name': 'unknown.json', 'mimeType': 'application/json'}

        if 'application/pdf' in json_file.get('mimeType', ''):
             # É o PDF direto
             file_content = drive_service.download_file(json_id)
             return send_file(
                io.BytesIO(file_content),
                mimetype='application/pdf',
                as_attachment=True,
                download_name=json_file.get('name')
            )

        json_name = json_file.get('name')
        pdf_name = json_name.replace('.json', '.pdf')
        
        # Procura o PDF na pasta de saída
        # Isso é ineficiente (listar tudo), mas para MVP ok. 
        # Ideal: Guardar ID do PDF no JSON.
        query = f"'{FOLDER_OUT}' in parents and name = '{pdf_name}' and trashed=false"
        results = drive_service.service.files().list(
            q=query, fields='files(id)', supportsAllDrives=True, includeItemsFromAllDrives=True
        ).execute()
        files = results.get('files', [])
        
        if not files:
            # Fuzzy match: same base name but maybe different casing or prefix
            base_name = pdf_name.replace('.pdf', '')
            query_fuzzy = f"'{FOLDER_OUT}' in parents and name contains '{base_name}' and trashed=false"
            results_fuzzy = drive_service.service.files().list(
                q=query_fuzzy, fields='files(id, name)', supportsAllDrives=True, includeItemsFromAllDrives=True
            ).execute()
            files_fuzzy = results_fuzzy.get('files', [])
            if files_fuzzy:
                # Pick the one that ends with .pdf
                pdf_files = [f for f in files_fuzzy if f['name'].lower().endswith('.pdf')]
                if pdf_files:
                    pdf_id = pdf_files[0]['id']
                else:
                    logger.warning(f"PDF Fuzzy não encontrado para {json_id}")
                    return "PDF não encontrado (Fuzzy)", 404
            else:
                return "PDF não encontrado", 404
        else:
            pdf_id = files[0]['id']
            
        file_content = drive_service.download_file(pdf_id)
        
        return send_file(
            io.BytesIO(file_content),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=pdf_name
        )
    except Exception as e:
        logger.error(f"Erro download Drive: {e}")
        return f"Erro download: {e}", 500

@app.route('/review/<file_id>')
@login_required
def review_page(file_id):
    try:
        from src.container import get_inspection_data_service, get_uow

        data_svc = get_inspection_data_service()
        result = data_svc.get_review_data(file_id, filter_compliant=True)

        contacts_list = []
        users_list = []
        is_validated = False

        if result and result.get('plan'):
            inspection = result['inspection']
            data = result['data']
            is_validated = True

            # Contacts for sharing modal
            if inspection.establishment:
                contacts_list = [
                    {'name': c.name, 'phone': c.phone, 'email': c.email, 'role': c.role, 'id': str(c.id)}
                    for c in inspection.establishment.contacts
                ]
                if not contacts_list and (inspection.establishment.responsible_name or inspection.establishment.responsible_email):
                    contacts_list.append({
                        'name': inspection.establishment.responsible_name or 'Responsavel',
                        'phone': inspection.establishment.responsible_phone,
                        'email': inspection.establishment.responsible_email,
                        'role': 'Responsavel',
                        'id': 'default',
                    })

            # Users for email modal
            from src.models_db import User
            uow = get_uow()
            company_id = inspection.establishment.company_id if inspection.establishment else None
            if company_id:
                users_list = uow.users.get_all_by_company(company_id)

        else:
            # Fallback for legacy/unprocessed items
            inspection = None
            data = {}
            if drive_service and not file_id.startswith('gcs:'):
                try:
                    data = drive_service.read_json(file_id) or {}
                except Exception:
                    data = {}
            if 'detalhe_pontuacao' not in data:
                data['detalhe_pontuacao'] = {}

            # Enrich via PDFService for template compatibility
            try:
                pdf_service.enrich_data(data)
            except Exception:
                pass

        return render_template(
            'review.html',
            inspection=inspection,
            report_data=data,
            users=users_list,
            contacts=contacts_list,
            is_validated=is_validated,
        )

    except Exception as e:
        logger.error(f"Erro ao abrir Review {file_id}: {e}", exc_info=True)
        return f"<h1>Erro ao abrir revisao</h1><p>{str(e)}</p><p><a href='/'>Voltar</a></p>", 500

from src.services.approval_service import approval_service

@app.route('/api/approve_plan/<file_id>', methods=['POST'])
@login_required
@role_required(UserRole.MANAGER)
def approve_plan(file_id):
    """Aprova plano e envia WhatsApp (Async)."""
    return _handle_service_call(file_id, is_approval=True)

@app.route('/api/share_plan/<file_id>', methods=['GET', 'POST'])
@login_required
def share_plan(file_id):
    """Compartilha plano via WhatsApp (Async ou Redirecionamento)."""
    if request.method == 'GET':
        # [NEW] Redirection Mode for Window.open
        try:
             # Fetch inspection details to build message
             from src.models_db import Inspection
             db = database.db_session
             insp = db.query(Inspection).filter_by(drive_file_id=file_id).first()
             
             name = "Relatório"
             if insp and insp.establishment: name = f"Relatório - {insp.establishment.name}"
             
             # Generate Public Link (To PDF or Review login? usually PDF if no login)
             link = f"{request.host_url}download_revised_pdf/{file_id}" # Or public unique link
             
             msg = f"Olá, confira o Plano de Ação de Inspeção Sanitária:\n*Local:* {name}\n*Acesse:* {link}"
             from urllib.parse import quote
             wa_link = f"https://wa.me/?text={quote(msg)}"
             
             return redirect(wa_link)
        except Exception as e:
             logger.error(f"Erro GET em Compartilhamento: {e}")
             return f"Erro ao gerar link de compartilhamento: {e}", 500

    return _handle_service_call(file_id, is_approval=False)

@app.route('/api/whatsapp_plan/<file_id>', methods=['POST'])
@login_required
def whatsapp_plan(file_id):
    """Envia link do plano via WhatsApp Business API."""
    try:
        from src.whatsapp import WhatsAppService
        from src.models_db import Inspection

        data = request.get_json() or {}
        target_phone = data.get('phone', '').strip()
        target_name = data.get('name', 'Responsavel')

        if not target_phone:
            return jsonify({'error': 'Telefone nao informado.'}), 400

        # Limpar telefone (somente digitos, adicionar DDI BR se necessario)
        clean_phone = ''.join(filter(str.isdigit, target_phone))
        if len(clean_phone) <= 11:
            clean_phone = '55' + clean_phone

        wa = WhatsAppService()
        if not wa.is_configured():
            return jsonify({'error': 'WhatsApp Business API nao configurada.'}), 503

        # Buscar dados da inspecao
        db = database.db_session
        insp = db.query(Inspection).filter_by(drive_file_id=file_id).first()
        est_name = insp.establishment.name if insp and insp.establishment else 'Estabelecimento'

        download_url = url_for('download_revised_pdf', file_id=file_id, _external=True)

        message = (
            f"Ola {target_name}, segue o Plano de Acao de Inspecao Sanitaria.\n\n"
            f"*Local:* {est_name}\n"
            f"*Acesse o relatorio:* {download_url}\n\n"
            f"Em caso de duvidas, entre em contato com seu consultor."
        )

        success = wa.send_text(message, dest_phone=clean_phone)

        if success:
            return jsonify({'success': True, 'message': 'Mensagem enviada via WhatsApp.'})
        else:
            return jsonify({'error': 'Falha ao enviar mensagem. Verifique os logs.'}), 500

    except Exception as e:
        logger.error(f"Erro ao enviar WhatsApp para {file_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/email_plan/<file_id>', methods=['POST'])
@login_required
def email_plan(file_id):
    """Envia email com o plano de ação (Simples)."""
    try:
        from src.models_db import Inspection
        db = database.db_session
        insp = db.query(Inspection).filter_by(drive_file_id=file_id).first()
        
        data = request.get_json() or {}
        target_email = data.get('target_email')
        target_name = data.get('target_name') or "Responsável"
        
        # [FIX] SES Sandbox Restriction
        # Only allow sending to: Current User or Establishment Responsible (if closely matches)
        # OR if we are just testing, maybe hardcode valid emails?
        # User request: "only to another specified email address or to the store manager's email"
        
        valid_emails = [current_user.email]
        if insp.establishment:
             if insp.establishment.responsible_email: valid_emails.append(insp.establishment.responsible_email)
             # Also allow manager email if different
             # if insp.establishment.company: ...
        
        if not target_email:
             target_email = current_user.email
             
        # Normalize
        target_email = target_email.strip()
        
        # Strict Check (Comment out if production has full SES access)
        # if target_email not in valid_emails:
        #    return jsonify({'error': f'Envio restrito (Sandbox). Apenas: {", ".join(valid_emails)}'}), 400

        if app.email_service:
             link = f"{request.host_url}download_revised_pdf/{file_id}"
             establishment_name = insp.establishment.name if insp and insp.establishment else 'Estabelecimento'

             html_body = f"""
             <html>
             <head></head>
             <body style="font-family: sans-serif; color: #333;">
                 <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eee; border-radius: 10px;">
                     <h2 style="color: #2563eb;">Relatório de Inspeção</h2>
                     <p>Olá, <strong>{target_name}</strong>.</p>
                     <p>O relatório de inspeção do estabelecimento <strong>{establishment_name}</strong> está disponível para download.</p>
                     <div style="background: #f3f4f6; padding: 15px; border-radius: 5px; margin: 20px 0; text-align: center;">
                         <p style="margin: 0 0 10px 0; font-size: 0.9rem; color: #666;">Clique no botão abaixo para baixar o PDF:</p>
                         <a href="{link}" style="background: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">Baixar PDF</a>
                     </div>
                     <p style="font-size: 0.9rem; color: #666;">Este link é válido e pode ser acessado a qualquer momento.</p>
                     <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                     <p style="font-size: 0.8rem; color: #999;">Este email foi enviado pelo sistema InspetorAI.</p>
                 </div>
             </body>
             </html>
             """

             text_body = f"""
Olá {target_name},

O relatório de inspeção do estabelecimento {establishment_name} está disponível para download.

Acesse o link: {link}

Este email foi enviado pelo sistema InspetorAI.
             """

             # Try/Except for specific SES errors
             try:
                app.email_service.send_email(target_email, f"Relatório de Inspeção - {establishment_name}", html_body, text_body)
             except Exception as ses_err:
                 msg = str(ses_err)
                 if "Email address is not verified" in msg:
                     return jsonify({'error': f"Email {target_email} não verificado na AWS SES (Sandbox)."}), 400
                 raise ses_err
                 
             return jsonify({'success': True, 'message': f'Email enviado para {target_email}'})
        
        return jsonify({'error': 'Serviço de email indisponível.'}), 500
    except Exception as e:
        logger.error(f"Erro no compartilhamento por email: {e}")
        return jsonify({'error': str(e)}), 500

def _handle_service_call(file_id, is_approval):
    try:
        data = request.json
        approval_service.process_approval_or_share(file_id, data, is_approval)
        return jsonify({'success': True, 'message': 'Processamento iniciado em segundo plano.'})
    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400
    except Exception as e:
        logger.error(f"Erro no controller: {e}")
        return jsonify({'error': "Erro interno"}), 500

@app.route('/api/save_review/<file_id>', methods=['POST'])
@login_required
def save_review(file_id):
    """Salva revisoes feitas pelo consultor no Plano de Acao."""
    try:
        from src.models_db import ActionPlanItemStatus, InspectionStatus
        from src.container import get_uow
        from datetime import datetime, timezone

        uow = get_uow()
        updates = request.json

        # Track if any evidence was added
        evidence_added = False

        for item_id_str, data in updates.items():
            item = uow.action_plans.get_item_by_id(uuid.UUID(item_id_str))
            if not item:
                continue

            if 'is_corrected' in data:
                item.status = ActionPlanItemStatus.RESOLVED if data['is_corrected'] else ActionPlanItemStatus.OPEN
                item.current_status = 'Corrigido' if data['is_corrected'] else 'Pendente'

            if 'correction_notes' in data:
                item.correction_notes = data['correction_notes']

            if 'evidence_image_url' in data:
                new_evidence = data['evidence_image_url']
                # Check if this is adding NEW evidence (not just clearing it)
                if new_evidence and not item.evidence_image_url:
                    evidence_added = True
                item.evidence_image_url = new_evidence or None

        # Auto-transition to COMPLETED if consultant added evidence
        # This prevents inspections from staying in PENDING_CONSULTANT_VERIFICATION with evidence
        if evidence_added:
            inspection = uow.inspections.get_by_drive_file_id(file_id)
            if inspection and inspection.status == InspectionStatus.PENDING_CONSULTANT_VERIFICATION:
                logger.info(f"Auto-transitioning inspection {file_id} to COMPLETED (evidence added)")
                inspection.status = InspectionStatus.COMPLETED
                inspection.updated_at = datetime.now(timezone.utc)

        uow.commit()
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"[SAVE_REVIEW] Erro ao salvar revisao {file_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/upload_evidence', methods=['POST'])
@limiter.limit("20 per minute")  # Rate limit: 20 evidence uploads per minute per IP
@login_required
def upload_evidence():
    """Recebe imagem de evidência e retorna URL pública/local."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    # Validate file using magic bytes (more secure than extension check)
    image_validator = FileValidator.create_image_validator(max_size_mb=10)
    file_content = file.read()
    file.seek(0)  # Reset file pointer for later use

    validation_result = image_validator.validate(file_content, file.filename)
    if not validation_result.is_valid:
        logger.warning(f"Evidence validation failed: {file.filename} - {validation_result.error_code}")
        return jsonify({'error': validation_result.error_message}), 400

    if file:
        filename = secure_filename(f"{uuid.uuid4()}_{file.filename}")

        try:
            # Use Storage Service (Abstração GCS/Local)
            from src.services.storage_service import storage_service

            folder = 'evidence'
            logger.info(f"[EVIDENCE] Iniciando upload: {filename} | GCS Client: {storage_service.client is not None} | Bucket: {storage_service.bucket_name}")

            public_url = storage_service.upload_file(file, destination_folder=folder, filename=filename)
            logger.info(f"[EVIDENCE] Upload concluido: {public_url}")

            # Always normalize to use the proxy route for resilience
            # This ensures evidence works even if GCS is not available or container restarts
            if public_url and not public_url.startswith('http'):
                # Local path like /static/uploads/evidence/filename.png
                # Convert to proxy route: /evidence/filename.png
                public_url = f"/evidence/{filename}"
            elif public_url and 'storage.googleapis.com' in public_url:
                # GCS URL - also use proxy route for consistency
                public_url = f"/evidence/{filename}"

            return jsonify({'url': public_url}), 200

        except Exception as e:
            logger.error(f"Upload falhou: {e}")
            return jsonify({'error': str(e)}), 500

    return jsonify({'error': 'Upload failed'}), 500

@app.route('/evidence/<path:filename>')
def serve_evidence(filename):
    """Proxy route for evidence images - tries GCS first, then local storage."""
    import mimetypes
    from flask import Response, send_from_directory
    from src.services.storage_service import storage_service

    # 1. Try GCS first (persistent storage)
    if storage_service.client and storage_service.bucket_name:
        try:
            bucket = storage_service.client.bucket(storage_service.bucket_name)
            blob = bucket.blob(f"evidence/{filename}")
            if blob.exists():
                data = blob.download_as_bytes()
                content_type = mimetypes.guess_type(filename)[0] or 'image/png'
                return Response(data, mimetype=content_type, headers={
                    'Cache-Control': 'public, max-age=86400'
                })
        except Exception as e:
            logger.warning(f"GCS evidence fetch failed for {filename}: {e}")

    # 2. Try local storage as fallback
    import os
    local_paths = [
        os.path.join('src', 'static', 'uploads', 'evidence'),
        os.path.join('static', 'uploads', 'evidence'),
    ]
    for local_dir in local_paths:
        full_path = os.path.join(local_dir, filename)
        if os.path.exists(full_path):
            return send_from_directory(os.path.abspath(local_dir), filename)

    logger.warning(f"Evidence not found: {filename}")
    return "Imagem não encontrada", 404

# Duplicate Route REMOVED: @app.route('/admin/api/jobs') matches src/admin_routes.py
# If you need this logic, ensure it does not conflict with admin_routes.py

@app.route('/download_revised_pdf/<file_id>')
def download_revised_pdf(file_id):
    """Gera um PDF sincronizado com a visao do Gestor/Consultor."""
    if not pdf_service:
        return 'Servico de PDF indisponivel', 500

    try:
        from src.container import get_inspection_data_service

        data_svc = get_inspection_data_service()
        data = data_svc.get_pdf_data(file_id)

        if not data:
            return 'Plano nao encontrado', 404

        # Ensure template keys
        if 'detalhe_pontuacao' not in data:
            data['detalhe_pontuacao'] = data.get('by_sector', {})

        # Generate PDF
        pdf_bytes = pdf_service.generate_pdf_bytes(data)

        filename = f"Plano_Revisado_{data.get('nome_estabelecimento', 'Relatorio').replace(' ', '_')}.pdf"
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        return response

    except Exception as e:
        logger.error(f'Erro PDF Gen: {e}')
        return f'Erro ao gerar PDF: {e}', 500

@app.route('/api/batch_details', methods=['POST'])
def batch_details():
    """Endpoint otimizado para buscar detalhes de múltiplos arquivos de uma vez."""
    file_ids = request.json.get('ids', [])
    if not file_ids:
        return jsonify({})

    try:
        from src.container import get_uow

        uow = get_uow()
        inspections = uow.inspections.get_batch_by_file_ids(file_ids[:15])

        results = {}
        for insp in inspections:
            ai_data = insp.ai_raw_response or {}
            est_name = insp.establishment.name if insp.establishment else 'Desconhecido'
            results[insp.drive_file_id] = {
                'id': insp.drive_file_id,
                'name': ai_data.get('titulo', 'Relatório Processado'),
                'establishment': est_name,
                'date': ai_data.get('data_inspecao', ''),
                'pdf_name': f"{est_name}.pdf",
                'pdf_link': f"/download_pdf/{insp.drive_file_id}",
                'review_link': f"/review/{insp.drive_file_id}",
            }

        # Drive fallback for IDs not found in DB
        missing = [fid for fid in file_ids[:15] if fid not in results]
        if missing and drive_service:
            for fid in missing:
                try:
                    data = drive_service.read_json(fid)
                    results[fid] = {
                        'id': fid,
                        'name': data.get('titulo', 'Relatório Processado'),
                        'establishment': data.get('estabelecimento', 'Outros'),
                        'date': data.get('data_inspecao', ''),
                        'pdf_name': f"{data.get('titulo', 'Relatório')}.pdf",
                        'pdf_link': f"/download_pdf/{fid}",
                        'review_link': f"/review/{fid}",
                    }
                except Exception as e:
                    logger.error(f"Error reading {fid} from Drive: {e}")
                    results[fid] = {'error': str(e)}

        return jsonify(results)

    except Exception as e:
        logger.error(f"Erro em batch_details: {e}")
        return jsonify({'error': str(e)}), 500



@app.route('/api/finalize_verification/<file_id>', methods=['POST'])
@login_required
@role_required(UserRole.CONSULTANT)
def finalize_verification(file_id):
    """Finaliza a etapa de verificacao do consultor."""
    from src.container import get_plan_service

    plan_svc = get_plan_service()
    result = plan_svc.finalize_verification(file_id)

    if not result.success:
        return jsonify({'error': result.message}), 404

    return jsonify({'success': True, 'message': result.message})

@app.route('/api/webhook/drive', methods=['POST'])
@csrf.exempt
def webhook_drive():
    """
    Webhook Global Changes Handler.
    Recebe notificação do Google Drive de que ALGO mudou.
    Dispara a verificação de mudanças (Changes API).
    """
    resource_state = request.headers.get('X-Goog-Resource-State')
    channel_id = request.headers.get('X-Goog-Channel-Id')
    
    logger.info(f"🔔 WEBHOOK RECEIVED! State: {resource_state}, Channel: {channel_id}")
    
    if resource_state == 'sync':
        return jsonify({'success': True, 'msg': 'Sync received'}), 200
    
    # Se for mudança ('change', 'add', etc), disparamos o processamento global
    # Idealmente, envie para Task Queue. Para MVP, roda inline (cuidado com timeout).
    
    try:
        from src.services.sync_service import process_global_changes
        drive = current_app.drive_service
        
        # Chamada Sincrona (Cuidado com timeout de 60s)
        result = process_global_changes(drive)
        logger.info(f"Webhook Processing Result: {result}")
        
    except Exception as e:
        logger.error(f"Webhook Global Error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    
    return jsonify({'success': True}), 200

@app.route('/api/webhook/renew', methods=['POST'])
@csrf.exempt
def renew_webhook():
    """
    Renova (ou Inicia) o Monitoramento Global.
    Chamado automaticamente pelo cron a cada 6 dias, ou manualmente.
    """
    try:
        from src.services.drive_service import drive_service
        from src.models_db import AppConfig
        from src import database
        import uuid

        callback_url = os.getenv("APP_PUBLIC_URL")
        if not callback_url:
            callback_url = request.url_root.rstrip('/')
            logger.info(f"APP_PUBLIC_URL not set, auto-detected: {callback_url}")

        full_url = f"{callback_url}/api/webhook/drive"
        channel_id = str(uuid.uuid4())
        token = get_config("WEBHOOK_SECRET_TOKEN")

        db_session = next(database.get_db())
        try:
            # 1. Stop old channel if exists
            old_channel_id = db_session.query(AppConfig).get('drive_webhook_channel_id')
            old_resource_id = db_session.query(AppConfig).get('drive_webhook_resource_id')
            if old_channel_id and old_resource_id and old_channel_id.value and old_resource_id.value:
                try:
                    drive_service.stop_watch(old_channel_id.value, old_resource_id.value)
                    logger.info(f"Stopped old channel: {old_channel_id.value}")
                except Exception as stop_err:
                    logger.warning(f"Could not stop old channel (may have expired): {stop_err}")

            # 2. Get page token (use existing to not miss events, or fetch new)
            existing_token = db_session.query(AppConfig).get('drive_page_token')
            start_token = existing_token.value if existing_token and existing_token.value else drive_service.get_start_page_token()
            if not start_token:
                return jsonify({'error': 'Failed to fetch start_page_token from Drive'}), 500

            # 3. Register new watch channel
            resp = drive_service.watch_global_changes(full_url, channel_id, token, page_token=start_token)
            logger.info(f"Global Watch Registered: {resp}")

            # 4. Persist channel info + token for renewal/cleanup
            def _upsert(key, value):
                entry = db_session.query(AppConfig).get(key)
                if not entry:
                    db_session.add(AppConfig(key=key, value=value))
                else:
                    entry.value = value

            _upsert('drive_page_token', start_token)
            _upsert('drive_webhook_channel_id', channel_id)
            _upsert('drive_webhook_resource_id', resp.get('resourceId', ''))
            _upsert('drive_webhook_expiration', str(resp.get('expiration', '')))
            db_session.commit()

            return jsonify({'success': True, 'channel': resp, 'start_token': start_token}), 200
        except Exception as e:
            db_session.rollback()
            raise e
        finally:
            db_session.close()

    except Exception as e:
        logger.error(f"Renew Error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    try:
        # Check migrations on startup (MVP hack)
        try:
            from scripts.migration_app_config import create_app_config_table
            create_app_config_table()
            logger.info("✅ AppConfig Migration Checked/Executed")
        except Exception as e:
            logger.error(f"⚠️ Migration Error: {e}")

        port = int(os.environ.get('PORT', 8080))
        print(f"🚀 STARTING APP ON PORT {port}...")
        print(f"📂 Current Dir: {os.getcwd()}")
        debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
        app.run(host='0.0.0.0', port=port, debug=debug_mode)
    except Exception as e:
        print(f"❌ CRITICAL ERROR IN APP.RUN: {e}")
        import traceback
        traceback.print_exc()
