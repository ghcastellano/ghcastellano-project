# v1.1.2 - CI/CD & Security Verified (Log Permission Fix)
import os
import glob
import json
import logging
import io
import threading
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, send_file
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
    logger.warning("⚠️ SECRET_KEY not found in environment. Generating random key (Sessions will invalidate on restart).")
    import secrets
    app.secret_key = secrets.token_hex(32)
    
app.config['SECRET_KEY'] = app.secret_key
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # 16MB Upload Limit
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
logger.info("🛠️ Dev Routes registered at /dev")
try:
    from src.auth import auth_bp
    from src.admin_routes import admin_bp, cron_sync_drive
    from src.manager_routes import manager_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp) 
    app.register_blueprint(manager_bp)
    
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
    return "Erro Interno no Servidor (500). Verifique os logs do Cloud Run para o Traceback.", 500

try:
    from src.services.drive_service import DriveService
    app.drive_service = DriveService()
    drive_service = app.drive_service # Global alias for routes
    logger.info("✅ Serviço do Drive Inicializado")
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
    from src.db_queries import get_consultant_inspections
    from src.db_queries import get_consultant_inspections
    from datetime import datetime
    
    # [SECURITY] Scope to Consultant's Establishments
    my_est_ids = [est.id for est in current_user.establishments] if current_user.establishments else []
    
    inspections = get_consultant_inspections(
        company_id=current_user.company_id, 
        allowed_establishment_ids=my_est_ids
    )
    
    # [UX] Calculate Quick Stats for Dashboard
    stats = {
        'total': len(inspections),
        'pending': sum(1 for i in inspections if i['status'] in ['PROCESSING', 'PENDING_VERIFICATION', 'WAITING_APPROVAL', 'PENDING_MANAGER_REVIEW']),
        'approved': sum(1 for i in inspections if i['status'] in ['APPROVED', 'COMPLETED']),
        'last_sync': datetime.utcnow().strftime('%H:%M')
    }
    
    return render_template('dashboard_consultant.html', 
                         user_role='CONSULTANT',
                         inspections=inspections,
                         stats=stats)

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
                est_alvo = None
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
                            logger.warning(f"⚠️ Drive Quota Error via API. Falling back to Alternate Storage for {file.filename}")
                            # Fallback to GCS / Local
                            try:
                                link_drive = storage_service.upload_file(file, "evidence", file.filename)
                                # Generate a "Fake" ID that indicates GCS/Local source
                                # Processor will see "gcs:" prefix and use storage_service.download_file
                                id_drive = f"gcs:{file.filename}"
                                logger.info(f"✅ Fallback Upload Success: {id_drive}")
                            except Exception as store_e:
                                logger.error(f"❌ Fallback Upload Failed: {store_e}")
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
                                'establishment_id': str(est_alvo.id) if est_alvo else None
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
                        
                        # Updates Status
                        job.status = JobStatus.COMPLETED
                        job.finished_at = datetime.utcnow()
                        db.commit()
                        
                        sucesso += 1
                        logger.info(f"✅ [SYNC] Processamento concluído: {file.filename}")
                        
                    except Exception as job_e:
                        logger.error(f"Erro no processamento síncrono para {file.filename}: {job_e}")
                        if job:
                            job.status = JobStatus.FAILED
                            job.error_log = str(job_e)
                            db.commit()
                        falha += 1
                        
                        # [NOTIFY] Avisar consultor sobre erro crítico
                        try:
                            if app.email_service and current_user.email:
                                subj = f"Erro no Processamento: {file.filename}"
                                body = f"""
                                Olá {current_user.name},
                                
                                Ocorreu um erro ao processar o relatório "{file.filename}".
                                
                                Detalhes do erro:
                                {str(job_e)}
                                
                                Por favor, verifique o arquivo e tente novamente. Se o erro persistir, contate o suporte.
                                """
                                app.email_service.send_email(current_user.email, subj, body)
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
    if not drive_service:
        return jsonify({'error': 'Drive unavailable'}), 500

    # Retrieve filter param
    import uuid
    est_id = request.args.get('establishment_id')
    est_uuid = None
    if est_id:
        try:
            est_uuid = uuid.UUID(est_id)
        except:
            pass # Ignore invalid UUID
            
    # Tenta banco primeiro, fallback para Drive se vazio ou erro
    use_db = os.getenv('DATABASE_URL') is not None
    
    if use_db:
        try:
            from src.db_queries import get_pending_inspections, get_processed_inspections_raw, get_consultant_inspections, get_pending_jobs, get_consultant_pending_inspections
            
            # Lógica baseada em Role
            if current_user.role == UserRole.CONSULTANT:
                # Consultor vê apenas seus trabalhos
                # Jobs pendentes (técnico) + Vistorias em Aprovação (negócio)
                try:
                    my_est_ids = [est.id for est in current_user.establishments] if current_user.establishments else []
                except: my_est_ids = []
                
                pending_jobs = get_pending_jobs(
                    company_id=current_user.company_id, 
                    establishment_ids=my_est_ids
                ) 
                
                # Fix: User has no establishment_id, use relationship list
                est_id = current_user.establishments[0].id if current_user.establishments else None
                
                # Fetch Waiting Approval (Legacy View)
                pending_approval = get_consultant_pending_inspections(establishment_id=est_id)
                
                # Combine technical jobs with business pending items
                pending = pending_jobs 
                
                processed_raw = get_consultant_inspections(company_id=current_user.company_id, establishment_id=est_id)
            else:
                # Gestor vê tudo ou filtrado
                pending = get_pending_jobs(
                    company_id=current_user.company_id, 
                    allow_all=(current_user.company_id is None),
                    establishment_ids=[est_uuid] if est_uuid else None
                ) 
                pending_approval = [] # Gestor sees everything in processed_raw usually, or we can add specific section too
                processed_raw = get_processed_inspections_raw(company_id=current_user.company_id, establishment_id=est_uuid)
            
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
                logger.info("Database returned None, falling back to Drive")
        except Exception as e:
            logger.warning(f"Database query failed, falling back to Drive: {e}")
    
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
            logger.warning(f"Database query failed for {file_id}, falling back to Drive: {e}")
        
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
def download_pdf_route(json_id):
    """
    Tenta encontrar o PDF correspondente ao JSON ID.
    Estratégia: 
    1. Ler JSON para saber nome do arquivo original (ou deduzir).
    2. Procurar PDF com mesmo nome base na pasta de saída.
    """
    if not drive_service: return "Erro", 500
    
    try:
        # Pega metadados do JSON para saber o nome
        json_file = drive_service.service.files().get(fileId=json_id, fields='name', supportsAllDrives=True).execute()
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
        return f"Erro download: {e}", 500

@app.route('/review/<file_id>') # file_id aqui é o ID do JSON no Drive (ou drive_file_id na table inspections)
@login_required
def review_page(file_id):
    if not drive_service:
        flash("Drive indisponível", "error")
        return redirect(url_for('dashboard'))

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

            # [FIX] Polyfill: Calculate items_nc for existing data (Required by template)
            if 'areas_inspecionadas' in data:
                for area in data['areas_inspecionadas']:
                    items_in_area = area.get('itens', [])
                    # Count items where status is NOT 'Conforme'
                    area['items_nc'] = sum(1 for item in items_in_area if item.get('status') != 'Conforme')
            
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
            data = drive_service.read_json(file_id)
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

            flash("Este relatório ainda não foi processado completamente para a nova visualização.", "warning")

        return render_template('review.html', 
                             inspection=inspection, 
                             data=data,
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

@app.route('/api/share_plan/<file_id>', methods=['POST'])
@login_required
def share_plan(file_id):
    """Compartilha plano via WhatsApp (Async)."""
    return _handle_service_call(file_id, is_approval=False)

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
            stats = plan.stats_json or {}
            
            # Format data to match base_layout.html expectations
            # Also include the new rich stats
            data = {
                'nome_estabelecimento': inspection.establishment.name if inspection.establishment else "Estabelecimento",
                'data_inspecao': inspection.created_at.strftime('%d/%m/%Y'),
                'resumo_geral': plan.summary_text,
                'pontos_fortes': plan.strengths_text,
                'pontuacao_geral': stats.get('score', 0),
                'pontuacao_maxima': stats.get('max_score', 0),
                'aproveitamento_geral': stats.get('percentage', 0),
                'detalhe_pontuacao': stats.get('by_sector', {}),
                'areas_inspecionadas': [] # We'll fill this below
            }
            
            # Group items by area for the template
            areas_map = {}
            for item in plan.items:
                area_name = item.area or "Geral"
                if area_name not in areas_map:
                    areas_map[area_name] = []
                
                areas_map[area_name].append({
                    'item_verificado': item.problem_description,
                    'status': item.status.value if hasattr(item.status, 'value') else str(item.status),
                    'observacao': item.problem_description,
                    'fundamento_legal': item.fundamento_legal,
                    'acao_corretiva_sugerida': item.corrective_action,
                    'prazo_sugerido': item.ai_suggested_deadline or str(item.deadline_date or '')
                })
            
            for area_name, items in areas_map.items():
                data['areas_inspecionadas'].append({
                    'nome_area': area_name,
                    'itens': items
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
        
        # 3. Retornar arquivo
        filename = f"Plano_Revisado_{data.get('nome_estabelecimento', 'Relatorio').replace(' ', '_')}.pdf"
        
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
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


# --- Webhook Drive ---
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

    if resource_state in ['add', 'update', 'chagne', 'change']:
        # Dispara processamento via Cloud Tasks (Job System)
        try:
            from src.models_db import Job, JobStatus
            from src import database
            from src.services.cloud_tasks import cloud_tasks_service
            
            # Create Job
            job = Job(
                type="CHECK_DRIVE_CHANGES",
                status=JobStatus.PENDING,
                input_payload={"trigger": "webhook", "resource_state": resource_state}
            )
            database.db_session.add(job)
            database.db_session.commit()
            
            # Enqueue Task
            cloud_tasks_service.create_http_task(payload={"job_id": job.id})
            
            logger.info(f"Webhook: Job {job.id} enqueued to Cloud Tasks.")
        except Exception as e:
            logger.error(f"Webhook Trigger Error: {e}", exc_info=True)
    
    return jsonify({'success': True}), 200

# Endpoint para Renovação (Chamar via Cron/Scheduler)
@app.route('/api/webhook/renew', methods=['POST'])
@csrf.exempt 
# @basic_auth_required (Idealmente proteger com token ou IP do Scheduler)
def renew_webhook():
    """
    Renova a assinatura do Webhook.
    """
    # Simplificação: Apenas tenta registrar novamente.
    # O ideal é persistir channel_id e parar o anterior, mas para MVP
    # registrar um novo funciona (o antigo expira).
    try:
        from src.services.drive_service import drive_service
        import uuid
        
        folder_id = config.FOLDER_ID_01_ENTRADA_RELATORIOS
        # Tenta descobrir a própria URL pública (difícil em serverless sem config)
        # Vamos usar uma env var APP_URL or pass it via request
        callback_url = os.getenv("APP_PUBLIC_URL") 
        if not callback_url:
            # Fallback se não configurado
            return jsonify({'error': 'APP_PUBLIC_URL not set'}), 500
            
        full_url = f"{callback_url}/api/webhook/drive"
        channel_id = str(uuid.uuid4())
        token = os.getenv("DRIVE_WEBHOOK_TOKEN", "segredo-webhook-drive-dev")
        
        resp = drive_service.watch_changes(folder_id, full_url, channel_id, token)
        
        return jsonify({'success': True, 'channel': resp}), 200
    except Exception as e:
        logger.error(f"Renew Error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    try:
        port = int(os.environ.get('PORT', 8080))
        print(f"🚀 STARTING APP ON PORT {port}...")
        print(f"📂 Current Dir: {os.getcwd()}")
        debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
        app.run(host='0.0.0.0', port=port, debug=debug_mode)
    except Exception as e:
        print(f"❌ CRITICAL ERROR IN APP.RUN: {e}")
        import traceback
        traceback.print_exc()
