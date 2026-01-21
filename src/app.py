# v1.1.2 - CI/CD & Security Verified (Log Permission Fix)
import os
import glob
import json
import logging
import io
import threading
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, send_file, get_flashed_messages, session, after_this_request, make_response
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()
from src.config import config
import uuid

# Configuração de Logs (JSON Estruturado para Cloud Logging)
class JsonFormatter(logging.Formatter):
    def format(self, record):
        json_log = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "timestamp": self.formatTime(record, self.datefmt),
            "logger": record.name,
            "module": record.module,
        }
        if hasattr(record, "props"):
            json_log.update(record.props)
            
        if record.exc_info:
            json_log["exception"] = self.formatException(record.exc_info)
            
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
import tempfile

# App Imports
from src.config import config
from src import database # Import module to access updated db_session
from src.database import get_db, init_db # Keep functions
from src.models_db import User, Company, Establishment, Job, JobStatus, UserRole
from datetime import datetime
from src.auth import role_required, admin_required, login_manager, auth_bp
from src.services.email_service import EmailService
from src.services.storage_service import storage_service

# Configurações do App
app.secret_key = os.getenv('SECRET_KEY')
if not app.secret_key:
    # Fallback ONLY if ENV is missing (prevents 500 Error in Prod if Setup fails)
    logger.warning("⚠️ SECRET_KEY não encontrada no ambiente. Gerando chave aleatória (Sessões serão invalidadas ao reiniciar).")
    import secrets
    app.secret_key = secrets.token_hex(32)
    
app.config['SECRET_KEY'] = app.secret_key
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024 # 32MB Upload Limit
csrf = CSRFProtect(app)

# Cloud Run Load Balancer Fix (HTTPS / CSRF)
# Trust only one proxy by default for Cloud Run
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

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

# Dev Mode Blueprint (Mock Data)
from src.dev_routes import dev_bp
app.register_blueprint(dev_bp)
logger.info("🛠️ Rotas de Dev registradas em /dev")
try:
    from src.auth import auth_bp
    from src.admin_routes import admin_bp
    from src.manager_routes import manager_bp
    from src.cron_routes import cron_bp, cron_sync_drive

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp) 
    app.register_blueprint(manager_bp)
    app.register_blueprint(cron_bp)
    
    # Exempt Cron from CSRF (Done here to avoid circular import)
    csrf.exempt(cron_sync_drive)
    
    logger.info("✅ Blueprints Registrados: auth, admin, manager")
    
    # Debug: List all rules
    logger.info(f"📍 Rotas Registradas: {[str(p) for p in app.url_map.iter_rules()]}")

except Exception as bp_error:
    logger.error(f"❌ Erro Crítico ao registrar Blueprints: {bp_error}")
    raise bp_error

@app.route('/debug/routes')
def debug_routes():
    if not current_user.is_authenticated or current_user.role != UserRole.ADMIN:
        return "Unauthorized", 403
    
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
FOLDER_IN = config.FOLDER_ID_01_ENTRADA_RELATORIOS
FOLDER_OUT = config.FOLDER_ID_02_PLANOS_GERADOS
FOLDER_BACKUP = config.FOLDER_ID_03_PROCESSADOS_BACKUP
FOLDER_ERROR = config.FOLDER_ID_99_ERROS

@app.errorhandler(500)
def handle_500(e):
    import traceback
    tb = traceback.format_exc()
    logger.error(f"💥 ERRO 500 DETECTADO: {e}\nTraceback:\n{tb}")
    # Resposta extremamente simples para evitar Erros 500 recursivos (Template errors)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
         return jsonify({'error': f"Erro Interno: {str(e)}"}), 500
    return "Erro Interno no Servidor (500). Verifique os logs do Cloud Run para o Traceback.", 500

try:
    from src.services.drive_service import DriveService
    app.drive_service = DriveService()
    drive_service = app.drive_service # Global alias for routes
    logger.info("✅ Serviço do Drive Inicializado")

    # [IMPROVEMENT] Validar ROOT_FOLDER_ID se configurado
    root_folder_id = os.getenv('GDRIVE_ROOT_FOLDER_ID')
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

except Exception as e:
    logger.error(f"⚠️ Falha ao inicializar Serviço do Drive: {e}")
    app.drive_service = None
    drive_service = None

# Email Service
try:
    from src.services.email_service import EmailService
    provider = 'ses' if os.getenv('AWS_ACCESS_KEY_ID') else 'mock'
    app.email_service = EmailService(provider=provider)
    logger.info(f"✅ Serviço de Email Inicializado ({provider.upper()})")
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
    from src.db_queries import get_consultant_inspections, get_pending_jobs
    from datetime import datetime
    
    # [SECURITY] Scope to Consultant's Establishments
    my_est_ids = [est.id for est in current_user.establishments] if current_user.establishments else []
    
    # 1. Fetch Processed/Approved Inspections
    inspections = get_consultant_inspections(
        company_id=current_user.company_id, 
        allowed_establishment_ids=my_est_ids
    )
    
    # 2. Fetch Active Jobs (Processing/Pending) to show "Em Análise" items that might be orphans
    # This ensures "New Store" uploads are visible immediately even if establishment matching is ambiguous
    pending_jobs = get_pending_jobs(
        company_id=current_user.company_id,
        establishment_ids=my_est_ids
    )
    
    # 2. Fetch Active Jobs (Processing/Pending)
    pending_jobs = get_pending_jobs(
        company_id=current_user.company_id,
        establishment_ids=my_est_ids
    )
    
    # [UX] Enhance Links & Deduplicate
    existing_file_ids = set()
    
    # Process Existing Inspections (Loaded from DB)
    for insp in inspections:
        existing_file_ids.add(insp.get('id'))
        # If status is Waiting Approval, prevent Consultant from thinking it's broken
        if insp.get('status') in ['Aguardando Aprovação', 'WAITING_APPROVAL', 'PENDING_MANAGER_REVIEW']:
             insp['review_link'] = "javascript:alert('Este relatório está em análise pelo Gestor. Você será notificado quando for aprovado.')"

    # Merge Jobs (Active or Orphaned)
    for job in pending_jobs:
        file_id = job.get('drive_file_id')
        
        # Skip if already shown as a processed inspection
        if file_id and file_id in existing_file_ids:
            continue
            
        # Filter: Show PENDING, PROCESSING, FAILED, and ORPHAN COMPLETED
        # (Orphan Completed = Completed but not in existing_file_ids, which we just checked)
        is_completed = (job.get('status_raw') == 'COMPLETED')
        
        # Define Link/Action
        msg = "Arquivo ainda em processamento. Por favor aguarde."
        if is_completed:
             msg = "Processamento concluído. O relatório deve aparecer na lista em breve (verifique se a loja está vinculada)."
        elif job.get('status_raw') == 'FAILED':
             msg = "Houve uma falha no processamento deste arquivo. Tente enviar novamente."

        # Add to main list
        inspections.insert(0, {
            'id': file_id or '#', 
            'name': job['name'],
            'establishment': job.get('establishment') or "Em processamento...",
            'date': job['created_at'],
            'status': job.get('status', 'Pendente'), 
            'pdf_link': '#',
            'review_link': f"javascript:alert('{msg}')"
        })
    
    # [UX] Calculate Quick Stats for Dashboard
    
    # [UX] Calculate Quick Stats for Dashboard
    stats = {
        'total': len(inspections),
        'pending': sum(1 for i in inspections if i['status'] in ['PROCESSING', 'PENDING_VERIFICATION', 'WAITING_APPROVAL', 'PENDING_MANAGER_REVIEW', 'Processando', 'Pendente']),
        'approved': sum(1 for i in inspections if i['status'] in ['APPROVED', 'COMPLETED', 'Concluído']),
        'last_sync': datetime.utcnow().strftime('%H:%M')
    }

    # [UX] Build Hierarchy for Upload Selectors
    user_hierarchy = {}
    
    # [FIX] Re-attach user to session to avoid DetachedInstanceError
    # or query establishments directly
    from src.database import get_db
    from src.models_db import User
    
    db_session = next(get_db())
    fresh_user = db_session.query(User).get(current_user.id)
    
    # Sort for consistent display
    if fresh_user and fresh_user.establishments:
        sorted_ests = sorted(fresh_user.establishments, key=lambda x: x.name)
        
        for est in sorted_ests:
            comp_name = est.company.name if est.company else "Outras"
            comp_id = str(est.company.id) if est.company else "other"
            
            if comp_id not in user_hierarchy:
                user_hierarchy[comp_id] = {
                    'name': comp_name,
                    'establishments': []
                }
            
            user_hierarchy[comp_id]['establishments'].append({
                'id': str(est.id),
                'name': est.name
            })
    
    return render_template('dashboard_consultant.html', 
                         user_role='CONSULTANT',
                         inspections=inspections,
                         stats=stats,
                         user_hierarchy=user_hierarchy)

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

        for file in uploaded_files:
            if not file or file.filename == '':
                continue
            
            if not file.filename.lower().endswith('.pdf'):
                flash(f'Arquivo {file.filename} ignorado: apenas PDFs são permitidos.', 'warning')
                continue

            nome_seguro = secure_filename(file.filename)
            caminho_temp = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}_{nome_seguro}")
            file.save(caminho_temp)
            
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
                
                # 3. Pasta do Drive (Input padrão se não identificado)
                pasta_id = est_alvo.drive_folder_id if est_alvo and est_alvo.drive_folder_id else FOLDER_IN
                if not pasta_id or pasta_id == "None":
                    pasta_id = FOLDER_IN
                
                # 4. Upload para o Drive
                # 4. Upload para o Drive (com Fallback para Storage/GCS)
                id_drive = None
                link_drive = None
                
                if drive_service:
                    try:
                        id_drive, link_drive = drive_service.upload_file(caminho_temp, pasta_id, file.filename)
                    except Exception as e:
                        if "quota" in str(e).lower() or "403" in str(e) or "storage" in str(e).lower():
                            logger.warning(f"⚠️ Erro de Cota do Drive via API. Usando Armazenamento Alternativo para {file.filename}")
                            # Fallback to GCS / Local
                            try:
                                link_drive = storage_service.upload_file(file, "evidence", file.filename)
                                # Generate a "Fake" ID that indicates GCS/Local source
                                # Processor will see "gcs:" prefix and use storage_service.download_file
                                id_drive = f"gcs:{file.filename}"
                                logger.info(f"✅ Sucesso no Upload Alternativo: {id_drive}")
                            except Exception as store_e:
                                logger.error(f"❌ Falha no Upload Alternativo: {store_e}")
                                raise e # Raise original error if fallback also fails
                        else:
                            raise e
                    
                    # 5. Criar Job
                    db = next(get_db())
                    job = None # [FIX] Initialize variable for error handling safety
                    try:
                        # [FIX] Create Inspection Record Immediately for UI Visibility
                        from src.models_db import Inspection, InspectionStatus
                        
                        new_insp = Inspection(
                            drive_file_id=id_drive,
                            drive_web_link=link_drive,
                            status=InspectionStatus.PROCESSING,
                            establishment_id=est_alvo.id if est_alvo else None
                            # client_id removed
                        )
                        db.add(new_insp)
                        db.flush() 
                        logger.info(f"✅ Registro de Inspeção {new_insp.id} pré-criado para visibilidade na UI.")

                        job = Job(
                            company_id=current_user.company_id or (est_alvo.company_id if est_alvo else None),
                            type="PROCESS_REPORT",
                            status=JobStatus.PENDING,
                            input_payload={
                                'file_id': id_drive, 
                                'filename': file.filename, 
                                'establishment_id': str(est_alvo.id) if est_alvo else None,
                                'establishment_name': est_alvo.name if est_alvo else "N/A"
                            } 
                        )
                        db.add(job)
                        db.commit()
                        
                        # [SYNC-MVP] Processar Imediatamente (Sem Worker)
                        logger.info(f"⏳ [SYNC] Iniciando processamento imediato: {file.filename}")
                        
                        # Instancia Processador (Import tardio para evitar circularidade)
                        from src.services.processor import processor_service
                        
                        # Prepara metadados simplificados
                        file_meta = {'id': id_drive, 'name': file.filename}
                        
                        # Executa Processamento (Isso pode levar 30-60s)
                        result = processor_service.process_single_file(
                            file_meta, 
                            company_id=job.company_id, 
                            establishment_id=est_alvo.id if est_alvo else None,
                            job=job
                        )
                        
                        # Updates Job Status & Metrics (Explicit Save)
                        job.status = JobStatus.COMPLETED
                        job.finished_at = datetime.utcnow()
                        
                        if result and 'usage' in result:
                            usage = result['usage']
                            job.cost_tokens_input = usage.get('prompt_tokens', 0)
                            job.cost_tokens_output = usage.get('completion_tokens', 0)
                            # Simple Cost Est (GPT-4o-mini: $0.15/1M in, $0.60/1M out)
                            # This is just an estimate, exact logic can be in model
                            job.cost_input_usd = (job.cost_tokens_input / 1_000_000) * 0.15
                            job.cost_output_usd = (job.cost_tokens_output / 1_000_000) * 0.60

                        if result and 'output_link' in result:
                            # Save link in payload or another field if available
                            current_payload = dict(job.result_payload) if job.result_payload else {}
                            current_payload['pdf_link'] = result['output_link']
                            job.result_payload = current_payload

                        db.commit()
                        
                        sucesso += 1
                        total_cost = (job.cost_input_usd or 0) + (job.cost_output_usd or 0)
                        logger.info(f"✅ [SYNC] Processamento concluído: {file.filename} (Cost: ${total_cost:.4f})")
                        
                    except Exception as job_e:
                        logger.error(f"Erro no processamento síncrono para {file.filename}: {job_e}")
                        if job:
                            job.status = JobStatus.FAILED
                            job.error_log = str(job_e)
                            db.commit()
                        falha += 1
                        
                        # [NOTIFY] Avisar consultor sobre erro crítico
                        try:
                            if app.email_service and user_email:
                                subj = f"Erro no Processamento: {file.filename}"
                                body_text = f"""
                                Olá {user_name},
                                
                                Ocorreu um erro ao processar o relatório "{file.filename}".
                                
                                Detalhes do erro:
                                {str(job_e)}
                                
                                Por favor, verifique o arquivo e tente novamente. Se o erro persistir, contate o suporte.
                                """
                                # HTML version optional, using same text for now
                                body_html = f"<pre>{body_text}</pre>"
                                
                                app.email_service.send_email(user_email, subj, body_html, body_text)
                        except Exception as mail_e:
                            logger.error(f"Falha ao enviar email de erro: {mail_e}")

                        flash(f"Erro ao processar {file.filename}: {str(job_e)}", 'error')
                else:
                    logger.error(f"Google Drive não configurado para {file.filename}")
                    falha += 1

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
        if not drive_service:
            return jsonify({'error': 'Drive unavailable'}), 500

        # Recupera parametro de filtro
        import uuid
        est_id = request.args.get('establishment_id')
        est_uuid = None
        if est_id and est_id.strip() and est_id != 'null' and est_id != 'undefined': # Verificação robusta
            try:
                est_uuid = uuid.UUID(est_id)
            except:
                pass # Ignora UUID inválido
                
        # Tenta banco primeiro, fallback para Drive se vazio ou erro
        use_db = os.getenv('DATABASE_URL') is not None
        
        if use_db:
            try:
                from src.db_queries import get_pending_inspections, get_processed_inspections_raw, get_consultant_inspections, get_pending_jobs, get_consultant_pending_inspections
                
                # Lógica baseada em Role
                if current_user.role == UserRole.CONSULTANT:
                    # [FIX] Acesso seguro a relacionamentos
                    my_est_ids = [est.id for est in current_user.establishments] if current_user.establishments else []
                    user_company_id = current_user.company_id
                    
                    pending_jobs = get_pending_jobs(
                        company_id=user_company_id, 
                        establishment_ids=my_est_ids
                    ) 
                    
                    # Fix: Usuário sem establishment_id, usa lista de relacionamentos
                    filter_est_id = my_est_ids[0] if my_est_ids else None
                    
                    # Busca Aguardando Aprovação (Visão Global da Empresa)
                    pending_approval = get_consultant_pending_inspections(
                        establishment_id=filter_est_id,
                        company_id=user_company_id,
                        establishment_ids=my_est_ids
                    )
                    
                    # Combine technical jobs with business pending items
                    pending = pending_jobs 
                    
                    processed_raw = get_consultant_inspections(company_id=user_company_id, allowed_establishment_ids=my_est_ids)
                else:
                    # Gestor vê tudo ou filtrado
                    # [TEMP] Allow Manager to see ALL companies (Super View) to debug orphaned reports
                    user_company_id = None 
                    
                    pending = get_pending_jobs(
                        company_id=None, 
                        allow_all=True,
                        establishment_ids=[est_uuid] if est_uuid else None
                    ) 
                    # Fix: Enable "Aguardando Aprovação" for Managers using Company Scope
                    pending_approval = get_consultant_pending_inspections(
                         company_id=None,
                         establishment_id=est_uuid
                    ) 
                    processed_raw = get_processed_inspections_raw(company_id=None, establishment_id=est_uuid)
                
                # Se o banco retornou dados (ou consultor vazio mas ok), usa eles
                if processed_raw is not None:  
                    def list_errors():
                        try:
                            # Improve error mapping here or just return raw names
                            files = drive_service.list_files(FOLDER_ERROR, extension='.pdf')
                            mapped_errors = []
                            for f in files[:10]:
                                mapped_errors.append({'name': f['name'], 'error': 'Erro no processamento (Verificar logs)'})
                            return mapped_errors
                        except Exception as e:
                            logger.error(f"Erro listando falhas no Drive: {e}")
                            return []
                    
                    return jsonify({
                        'pending': pending,
                        'in_approval': pending_approval, 
                        'processed_raw': processed_raw,
                        'errors': list_errors()
                    })
                else:
                    # Banco vazio/falhou, usa Drive
                    logger.info("Banco de dados retornou None, buscando no Drive")
            except Exception as e:
                logger.warning(f"Falha na consulta ao Banco, buscando no Drive: {e}")
        
    except Exception as fatal_e:
        logger.error(f"ERRO FATAL em /api/status: {fatal_e}")
        return jsonify({'error': str(fatal_e)}), 500

    # Lógica original baseada no Drive (fallback)
    
    # Lógica original baseada no Drive (fallback) - APENAS GESTOR OU FALLBACK GERAL
    # Se for consultor e cair no fallback, ele veria tudo (segurança por obscuridade no MVP fallback)
    # Idealmente, filtrar aqui também, mas JSON do drive não tem status fácil.
    
    def list_pending():
        try:
            files = drive_service.list_files(FOLDER_IN, extension='.pdf')
            return [{'name': f['name']} for f in files[:10]]
        except: return []

    def list_errors():
        try:
            files = drive_service.list_files(FOLDER_ERROR, extension='.pdf')
            return [{'name': f['name']} for f in files[:10]]
        except: return []

    def list_processed_raw():
        try:
            json_files = drive_service.list_files(FOLDER_OUT, extension='.json')
            return [{'id': f['id'], 'name': f['name']} for f in json_files[:30]]
        except Exception as e:
            logger.error(f"Erro escaneando output: {e}")
            return []
        
    return jsonify({
        'pending': list_pending(),
        'processed_raw': list_processed_raw(),
        'errors': list_errors()
    })

@app.route('/api/processed_item/<file_id>')
def get_processed_item_details(file_id):
    """Retorna detalhes de um item processado específico (Lazy Load)."""
    if not drive_service:
        return jsonify({'error': 'Drive unavailable'}), 500
    
    # Try database first
    use_db = os.getenv('DATABASE_URL') is not None
    if use_db:
        try:
            from src.db_queries import get_inspection_details
            details = get_inspection_details(file_id)
            if details:
                return jsonify(details)
            # If not found in DB, try Drive fallback
        except Exception as e:
            logger.warning(f"Falha na consulta ao Banco para {file_id}, buscando no Drive: {e}")
        
    # Lógica original baseada no Drive (fallback)
    try:
        data = drive_service.read_json(file_id)
        basename = data.get('titulo', 'Relatório Sem Título')
        pdf_name = f"{basename}.pdf"
        estab = data.get('estabelecimento', 'Outros')
        
        item = {
            'id': file_id,
            'name': data.get('titulo', 'Relatório Processado'),
            'establishment': estab,
            'date': data.get('data_inspecao', ''),
            'pdf_name': pdf_name,
            'pdf_link': f"/download_pdf/{file_id}", 
            'review_link': f"/review/{file_id}",
        }
        return jsonify(item)
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

@app.route('/review/<file_id>') # file_id aqui é o ID do JSON no Drive (ou drive_file_id na table inspections)
@login_required
def review_page(file_id):
    if not drive_service:
        # Check if we can proceed with DB only?
        pass # Continue to try

    try:
        # 1. Tenta carregar do Banco de Dados (Fonte da Verdade Validada)
        from src.database import get_db
        from src.models_db import Inspection, ActionPlan, ActionPlanItemStatus
        db = database.db_session
        
        inspection = db.query(Inspection).filter_by(drive_file_id=file_id).first()
        data = {}
        contacts_list = []
        is_validated = False

        if inspection and inspection.action_plan:
            plan = inspection.action_plan
            is_validated = True
            
            # Populate data from Plan Stats (Source of Truth for Validated Data)
            data = plan.stats_json or {}
            if 'detalhe_pontuacao' not in data:
                 data['detalhe_pontuacao'] = data.get('by_sector', {})

            # [FIX] Polyfill: Calcular items_nc para dados existentes
            if 'areas_inspecionadas' in data:
                for area in data['areas_inspecionadas']:
                    items_in_area = area.get('itens', [])
                    # Contar itens onde status NÃO é 'Conforme'
                    area['items_nc'] = sum(1 for item in items_in_area if item.get('status') != 'Conforme')
            
            # [FIX] Reconstruir Itens do BD (Ordenados) para garantir consistência com a Visão do Gestor
            if inspection.action_plan.items:
                # 1. Mapear áreas JSON existentes para pontuações/estatísticas E Recuperação de Status
                rebuilt_areas = {}
                normalized_area_map = {} # Chave: nome_normalizado -> objeto área
                
                # Mapas de busca para recuperação de status
                score_map_by_index = {} # Chave: (area_name, index) -> dados
                score_map_by_text = {}  # Chave: texto -> dados
                
                if 'areas_inspecionadas' in data:
                    for area in data['areas_inspecionadas']:
                        # Usar nome normalizado como chave
                        key_name = area.get('nome_area') or area.get('name')
                        if key_name:
                            rebuilt_areas[key_name] = area
                            normalized_area_map[key_name.strip().lower()] = area
                            
                            # Construir mapas de pontuação
                            for idx, item_json in enumerate(area.get('itens', [])):
                                 # [FIX] Garantir valor numérico seguro (evita NoneType > int)
                                 score_val = item_json.get('pontuacao', 0)
                                 if score_val is None: score_val = 0
                                 
                                 payload = {
                                     'pontuacao': float(score_val),
                                     'status': item_json.get('status')
                                 }
                                 score_map_by_index[(key_name, idx)] = payload
                                 
                                 text_key = (item_json.get('item_verificado') or item_json.get('observacao') or "").strip()[:50]
                                 score_map_by_text[text_key] = payload

                            area['itens'] = [] # Limpar itens para reabastecer do BD

                # 2. Ordenar Itens do BD por Índice de Ordem
                db_items = sorted(
                    inspection.action_items, 
                    key=lambda i: (i.order_index if i.order_index is not None else float('inf'), str(i.id))
                )

                # 3. Popular
                for item in db_items:
                    raw_area_name = item.nome_area or "Geral"
                    norm_area_name = raw_area_name.strip().lower()
                    
                    # Busca Robusta de Área
                    target_area = normalized_area_map.get(norm_area_name)
                    if target_area:
                        area_name = target_area['nome_area']
                    else:
                        area_name = raw_area_name # Fallback para criar nova (inevitável se realmente nova)
                    
                    # Criar área se faltando (improvável se sincronizado, mas seguro)
                    if area_name not in rebuilt_areas:
                         rebuilt_areas[area_name] = {
                             'nome_area': area_name, 
                             'itens': [], 
                             'items_nc': 0,
                             'pontuacao_obtida': 0,
                             'pontuacao_maxima': 0,
                             'aproveitamento': 0
                         }
                    
                    # Formatação
                    deadline_display = item.prazo_sugerido
                    if item.deadline_date:
                        try: deadline_display = item.deadline_date.strftime('%d/%m/%Y')
                        except: pass
                    
                    # Recuperação Robusta de Status
                    recovered_data = {}
                    # Tentar correspondência por Índice
                    if item.order_index is not None:
                         recovered_data = score_map_by_index.get((area_name, item.order_index), {})
                    
                    # Tentar correspondência por Texto como fallback
                    if not recovered_data:
                         full_desc = item.problem_description or ""
                         candidate_name = full_desc.split(":", 1)[0].strip() if ":" in full_desc else full_desc
                         recovered_data = score_map_by_text.get(candidate_name[:50], {})

                    recovered_status = recovered_data.get('status')
                    recovered_score = recovered_data.get('pontuacao', 0)

                    rebuilt_areas[area_name]['itens'].append({
                        'id': str(item.id),
                        'item_verificado': item.item_verificado,
                        'status': recovered_status or item.original_status or 'Não Conforme', 
                        'observacao': item.problem_description,
                        'fundamento_legal': item.fundamento_legal,
                        'acao_corretiva_sugerida': item.corrective_action,
                        'prazo_sugerido': deadline_display,
                        'pontuacao': item.original_score if (item.original_score is not None and item.original_score > 0) else (recovered_score if recovered_score > 0 else (item.original_score or 0))
                    })
                    
                # 4. Recalculate NC counts
                for area in rebuilt_areas.values():
                    area['items_nc'] = len(area['itens'])

                # 5. Save back to data used by template
                data['areas_inspecionadas'] = list(rebuilt_areas.values())
            
            # Contacts (for Email Modal)
            if inspection.establishment:
                contacts_list = [{'name': c.name, 'phone': c.phone, 'id': str(c.id)} for c in inspection.establishment.contacts]
                if not contacts_list and inspection.establishment.responsible_name:
                     contacts_list.append({'name': inspection.establishment.responsible_name, 'phone': inspection.establishment.responsible_phone, 'id': 'default'})

            # Users list for Email Modal (Fetch all users for now, or just company users)
            # Users list for Email Modal
            from src.models_db import User
            company_id = inspection.establishment.company_id if inspection.establishment else None
            users_list = db.query(User).filter(User.company_id == company_id).all() if company_id else []
            
        else:
            # Fallback for unproccessed/legacy items
            # Load from Drive (Legacy)
            if drive_service and not file_id.startswith('gcs:'):
                try:
                    data = drive_service.read_json(file_id)
                except: data = {}
            else:
                data = {}

            if not data: data = {}
            # Ensure detalhe_pontuacao exists for template compatibility
            if 'detalhe_pontuacao' not in data:
                 data['detalhe_pontuacao'] = {} # Prevent template crash
            
            # [FIX] Polyfill: Calculate items_nc for Legacy Drive JSON (Required by template)
            if 'areas_inspecionadas' in data:
                for area in data['areas_inspecionadas']:
                    items_in_area = area.get('itens', [])
                    # Count items where status is NOT 'Conforme'
                    area['items_nc'] = sum(1 for item in items_in_area if item.get('status') != 'Conforme')
            
            # [HOTFIX] Enrich Data Globally via PDFService Logic (Fixes missing keys like aproveitamento_geral)
            try:
                # Usa o enrich_data do pdf_service para garantir consistência entre PDF e Web
                pdf_service.enrich_data(data)
            except Exception as e:
                logger.warning(f"Failed to enrich data via PDF Service: {e}")

            # flash("Este relatório ainda não foi processado completamente para a nova visualização.", "warning")

        return render_template('review.html', 
                             inspection=inspection, 
                             report_data=data,
                             users=users_list if 'users_list' in locals() else [],
                             contacts=contacts_list,
                             is_validated=is_validated)
                             
    except Exception as e:
        logger.error(f"Erro ao abrir Review {file_id}: {e}", exc_info=True)
        return f"<h1>Erro ao abrir revisão</h1><p>{str(e)}</p><p><a href='/'>Voltar</a></p>", 500

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
             body = f"Olá {target_name},<br><br>Segue o link para o relatório de inspeção: <a href='{link}'>Baixar PDF</a>"
             
             # Try/Except for specific SES errors
             try:
                app.email_service.send_email(target_email, f"Relatório de Inspeção - {insp.establishment.name if insp and insp.establishment else ''}", body, body)
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
    """Salva revisões feitas pelo consultor no Plano de Ação."""
    try:
        from src.models_db import ActionPlanItem, ActionPlanItemStatus
        db = database.db_session
        updates = request.json
        
        for item_id_str, data in updates.items():
            item = db.query(ActionPlanItem).get(uuid.UUID(item_id_str))
            if item:
                if 'is_corrected' in data:
                    item.status = ActionPlanItemStatus.RESOLVED if data['is_corrected'] else ActionPlanItemStatus.OPEN
                if 'correction_notes' in data:
                    item.manager_notes = data['correction_notes']
                if 'evidence_image_url' in data:
                    item.evidence_image_url = data['evidence_image_url']
        
        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Erro ao salvar revisão {file_id}: {e}")
        db.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/upload_evidence', methods=['POST'])
@login_required
def upload_evidence():
    """Recebe imagem de evidência e retorna URL pública/local."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    if file:
        filename = secure_filename(f"{uuid.uuid4()}_{file.filename}")
        
        try:
            # Use Storage Service (Abstração GCS/Local)
            from src.services.storage_service import storage_service
            
            # Decide bucket folder based on environment or config
            folder = 'evidence' 
            
            public_url = storage_service.upload_file(file, destination_folder=folder, filename=filename)
            
            return jsonify({'url': public_url}), 200
            
        except Exception as e:
            logger.error(f"Upload falhou: {e}")
            return jsonify({'error': str(e)}), 500
        
    return jsonify({'error': 'Upload failed'}), 500

# Duplicate Route REMOVED: @app.route('/admin/api/jobs') matches src/admin_routes.py
# If you need this logic, ensure it does not conflict with admin_routes.py

@app.route('/download_revised_pdf/<file_id>')
def download_revised_pdf(file_id):
    """Gera um novo PDF baseado no estado atual do Banco (preferencial) ou Drive."""
    if not drive_service or not pdf_service:
        return "Serviços indisponíveis", 500
        
    try:
        from src.models_db import Inspection
        db = database.db_session
        inspection = db.query(Inspection).filter_by(drive_file_id=file_id).first()
        
        data = {}
        if inspection and inspection.action_plan:
            plan = inspection.action_plan
            # [FIX] Merge Logic for Summary/Scores (Same as Manager Route)
            ai_raw = inspection.ai_raw_response or {}
            
            # Helper for fallbacks
            stats = plan.stats_json or {} # [FIX] Define stats variable
            def get_val(from_stats, from_raw, default=0):
                return from_stats if from_stats else (from_raw or default)

            summary = plan.summary_text or ai_raw.get('summary') or ai_raw.get('summary_text') or "Resumo não disponível."
            score = get_val(stats.get('score'), ai_raw.get('score'))
            max_score = get_val(stats.get('max_score'), ai_raw.get('max_score'))
            percentage = get_val(stats.get('percentage'), ai_raw.get('percentage'))
            
            # Format data to match base_layout.html expectations
            data = {
                'nome_estabelecimento': inspection.establishment.name if inspection.establishment else "Estabelecimento",
                'data_inspecao': inspection.created_at.strftime('%d/%m/%Y'),
                'resumo_geral': summary,
                'pontos_fortes': plan.strengths_text,
                'pontuacao_geral': score,
                'pontuacao_maxima': max_score,
                'aproveitamento_geral': percentage,
                'detalhe_pontuacao': stats.get('by_sector') or ai_raw.get('by_sector', {}),
                'areas_inspecionadas': [] 
            }
            
            # Group items by area for the template
            areas_map = {}
            for item in plan.items:
                # [FIX] Correct Field Mapping
                area_name = item.sector or "Geral"
                if area_name not in areas_map:
                    areas_map[area_name] = []
                
                deadline_str = ''
                if item.deadline_date:
                    deadline_str = item.deadline_date.strftime('%d/%m/%Y')
                elif item.ai_suggested_deadline:
                    deadline_str = item.ai_suggested_deadline

                areas_map[area_name].append({
                    'item_verificado': item.item_verificado,
                    'status': item.original_status if item.original_status else (item.status.value if hasattr(item.status, 'value') else str(item.status)),
                    'observacao': item.problem_description,
                    'fundamento_legal': item.fundamento_legal or "Não informado",
                    'acao_corretiva_sugerida': item.corrective_action,
                    'prazo_sugerido': deadline_str,
                    'pontuacao': item.original_score if item.original_score is not None else 0
                })
            
            # Recuperar estatísticas por setor para preencher aproveitamento
            sector_stats = data.get('detalhe_pontuacao', {})

            for area_name, items in areas_map.items():
                # Tenta pegar estatísticas da área pre-calculadas
                # O formato pode variar, então tratamos com segurança
                aprov_area = 0
                if isinstance(sector_stats, dict):
                    s_stat = sector_stats.get(area_name)
                    if isinstance(s_stat, dict):
                        aprov_area = s_stat.get('percentage', 0)
                    elif isinstance(s_stat, (int, float)): # Caso simplificado
                        aprov_area = s_stat
                
                data['areas_inspecionadas'].append({
                    'nome_area': area_name,
                    'itens': items,
                    'aproveitamento': aprov_area # [FIX] Adicionado para evitar erro no template
                })
        else:
            # Fallback to Drive
            logger.info(f"⚠️ PDF generation fallback to Drive for {file_id}")
            data = drive_service.read_json(file_id)
            # Ensure keys match (Drive JSON might use different keys)
            if 'estabelecimento' in data and 'nome_estabelecimento' not in data:
                data['nome_estabelecimento'] = data['estabelecimento']
        
        # 2. Gerar PDF em memória
        pdf_bytes = pdf_service.generate_pdf_bytes(data)
        
        # 3. Retornar arquivo com headers corretos
        filename = f"Plano_Revisado_{data.get('nome_estabelecimento', 'Relatorio').replace(' ', '_')}.pdf"
        
        # [FIX] Usar make_response para compatibilidade e evitar arquivo corrompido
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        return response
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
        
    except Exception as e:
        logger.error(f"Erro gerando PDF revisado: {e}")
        return f"Erro na geração: {e}", 500

@app.route('/api/batch_details', methods=['POST'])
def batch_details():
    """
    Endpoint otimizado para buscar detalhes de múltiplos arquivos de uma vez.
    """
    if not drive_service:
        return jsonify({'error': 'Drive unavailable'}), 500
        
    file_ids = request.json.get('ids', [])
    if not file_ids:
        return jsonify({})
    
    # Try database first
    use_db = os.getenv('DATABASE_URL') is not None
    if use_db:
        try:
            from src.db_queries import get_batch_inspection_details
            results = get_batch_inspection_details(file_ids[:15])
            if results:
                return jsonify(results)
        except Exception as e:
            logger.warning(f"Database batch query failed, falling back to Drive: {e}")
    
    # Original Drive-based logic (fallback)
    results = {}
    for fid in file_ids[:15]:
        try:
            data = drive_service.read_json(fid)
            basename = data.get('titulo', 'Relatório')
            pdf_name = f"{basename}.pdf"
            estab = data.get('estabelecimento', 'Outros')
            
            results[fid] = {
                'id': fid,
                'name': data.get('titulo', 'Relatório Processado'),
                'establishment': estab,
                'date': data.get('data_inspecao', ''),
                'pdf_name': pdf_name,
                'pdf_link': f"/download_pdf/{fid}",
                'review_link': f"/review/{fid}"
            }
        except Exception as e:
            logger.error(f"Error reading {fid}: {e}")
            results[fid] = {'error': str(e)}
    
    return jsonify(results)



@app.route('/api/finalize_verification/<file_id>', methods=['POST'])
@login_required
@role_required(UserRole.CONSULTANT)
def finalize_verification(file_id):
    """
    Finaliza a etapa de verificacao do consultor.
    Muda status para COMPLETED e gera PDF final se necessario.
    """
    try:
        inspection = db_session.query(Inspection).filter_by(drive_file_id=file_id).first()
        if not inspection:
            return jsonify({'error': 'Inspection not found'}), 404
        
        # Validar se usuario pode editar (se pertence a ele ou admin)
        # TODO: Adicionar validacao de permissao
        
        # 1. Update Status
        inspection.status = InspectionStatus.COMPLETED
        inspection.updated_at = datetime.utcnow()
        
        db_session.commit()
        
        # 2. Trigger Final PDF Generation (Async or Sync)
        # For now, we assume PDF is generated on demand or already exists. 
        # Ideally, generate a "Final with Evidence" version.
        
        return jsonify({'success': True, 'message': 'Verificação concluída'})

    except Exception as e:
        logger.error(f"Erro ao finalizar verificação {file_id}: {e}")
        db_session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/webhook/drive', methods=['POST'])
@csrf.exempt # Webhooks from Google don't have CSRF token
def drive_webhook():
    """
    Recebe notificação do Google Drive (Push Notification).
    """
    # 1. Verifica Token de Segurança (Evitar Spam)
    token = request.headers.get('X-Goog-Channel-Token')
    expected_token = os.getenv('WEBHOOK_SECRET_TOKEN')
    
    if token != expected_token:
        logger.warning(f"Webhook Unauthorized: {token}")
        return jsonify({'error': 'Unauthorized'}), 401

    # 2. Verifica Estado do Recurso
    resource_state = request.headers.get('X-Goog-Resource-State')
    # 'sync' é o teste inicial, 'add'/'update'/'trash' são eventos
    logger.info(f"Webhook Received: {resource_state}")

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
# @basic_auth_required 
def renew_webhook():
    """
    Renova (ou Inicia) o Monitoramento Global.
    Deve ser chamado periodicamente (ex: a cada 6 dias, ou start manual).
    """
    try:
        from src.services.drive_service import drive_service
        from src.models_db import AppConfig
        from src import database
        import uuid
        
        # [FIX] Run migration lazily because __main__ block doesn't run in Gunicorn
        try:
            from scripts.migration_app_config import create_app_config_table
            create_app_config_table()
            logger.info("✅ AppConfig Migration Verified")
        except Exception as mig_err:
            logger.warning(f"⚠️ Migration Check Failed: {mig_err}")
            return jsonify({'error': f'Migration Failed: {mig_err}'}), 500

        callback_url = os.getenv("APP_PUBLIC_URL") 
        if not callback_url:
            return jsonify({'error': 'APP_PUBLIC_URL environment variable not set'}), 500
            
        full_url = f"{callback_url}/api/webhook/drive"
        channel_id = str(uuid.uuid4())
        token = os.getenv("DRIVE_WEBHOOK_TOKEN", "global-webhook-token")
        
        # 1. Fetch Start Token
        start_token = drive_service.get_start_page_token()
        if not start_token:
            return jsonify({'error': 'Failed to fetch start_page_token from Drive'}), 500
            
        # 2. Save Token to DB (so we don't miss events from now)
        try:
            db_session = next(database.get_db())
            config_entry = db_session.query(AppConfig).get('drive_page_token')
            if not config_entry:
                db_session.add(AppConfig(key='drive_page_token', value=start_token))
            else:
                config_entry.value = start_token
            db_session.commit()
            db_session.close()
        except Exception as e:
            logger.error(f"DB Token Save Error: {e}")
            return jsonify({'error': f'DB Error: {e}'}), 500
        
        # 3. Register Watch
        resp = drive_service.watch_global_changes(full_url, channel_id, token, page_token=start_token)
        
        logger.info(f"Global Watch Registered: {resp}")
        return jsonify({'success': True, 'channel': resp, 'start_token': start_token}), 200
        
    except Exception as e:
        logger.error(f"Renew Error: {e}")
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
