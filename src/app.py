# v1.1.2 - CI/CD & Security Verified (Log Permission Fix)
import os
import glob
import json
import logging
import io
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
from src.auth import role_required, admin_required, login_manager, auth_bp
from src.tasks import task_manager
from src.services.email_service import EmailService

# Configurações do App
app.secret_key = os.urandom(24)
app.config['SECRET_KEY'] = config.SECRET_KEY
csrf = CSRFProtect(app)

# Cloud Run Load Balancer Fix (HTTPS / CSRF)
# Trust only one proxy by default for Cloud Run
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Inicializa Flask-Login
login_manager.init_app(app)

# Registra Blueprints
# Import Blueprints - Late Import to avoid circular dependencies
logger.info("🔧 Carregando Blueprints...")
try:
    from src.auth import auth_bp
    from src.admin_routes import admin_bp
    from src.manager_routes import manager_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp) 
    app.register_blueprint(manager_bp)
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
        logger.info("🔄 Iniciando Migrações Unificadas...")
        # Use database.db_session to ensure we get the initialized object
        run_migrations(database.db_session)
        logger.info("✅ Migrações executadas com sucesso")
except ImportError as e:
    logger.error(f"❌ Erro ao importar migrações: {e}")
except Exception as e:
    logger.error(f"❌ Erro Crítico nas Migrações: {e}")

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
    return render_template('dashboard_consultant.html', user_role='CONSULTANT')

# Rota legado (redireciona para root para tratar auth)
@app.route('/dashboard')
def dashboard_legacy():
    return redirect(url_for('root'))

def get_friendly_error_message(e):
    msg = str(e).lower()
    if "quota" in msg or "insufficient storage" in msg or "403" in msg:
        return "Erro de Permissão ou Quota no Google Drive. Contate o suporte técnico."
    if "token" in msg or "expired" in msg:
        return "Sessão de conexão expirada. Contate o suporte."
    if "not found" in msg or "404" in msg:
        return "Recurso não encontrado no sistema."
    if "pdf" in msg or "corrupt" in msg:
        return "O arquivo PDF parece estar corrompido ou não é válido."
    if "timeout" in msg:
        return "O processamento demorou muito. Tente novamente mais tarde."
    return f"Erro no processamento: {msg}"

@app.route('/upload', methods=['POST'])
@login_required
@role_required(UserRole.CONSULTANT)
def upload_file():
    """
    Rota para upload de múltiplos relatórios de vistoria.
    Realiza o processamento inicial e enfileira jobs assíncronos.
    """
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
                if drive_service:
                    id_drive, link_drive = drive_service.upload_file(caminho_temp, pasta_id, file.filename)
                    
                    # 5. Criar Job (company_id agora pode ser nulo se est_alvo for None)
                    db = next(get_db())
                    try:
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
                        
                        # Enfileira tarefa no Cloud Tasks
                        task_manager.enqueue_job(job.id, payload={
                            "type": "PROCESS_REPORT", 
                            "file_id": id_drive, 
                            "filename": file.filename
                        })
                        sucesso += 1
                    except Exception as job_e:
                        logger.error(f"Erro ao criar Job para {file.filename}: {job_e}")
                        db.rollback()
                        falha += 1
                else:
                    logger.error(f"Google Drive não configurado para {file.filename}")
                    falha += 1

            except Exception as e:
                friendly_msg = get_friendly_error_message(e)
                logger.error(f"Falha no arquivo {file.filename}: {e}")
                flash(f"Erro no arquivo {file.filename}: {friendly_msg}", 'error')
                falha += 1
            finally:
                if os.path.exists(caminho_temp):
                    os.remove(caminho_temp)
        
        if sucesso > 0:
            flash(f'{sucesso} relatório(s) enviado(s) para processamento.', 'success')
        # if falha > 0: flash message handled inside loop for specificity
            
        return redirect(url_for('dashboard_consultant'))
            
    except Exception as e:
        logger.error(f"Erro geral no upload: {e}")
        flash(f"Ocorreu um erro inesperado: {str(e)}", 'error')
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
                pending_jobs = get_pending_jobs(company_id=current_user.company_id) 
                
                # Fix: User has no establishment_id, use relationship list
                est_id = current_user.establishments[0].id if current_user.establishments else None
                
                # Fetch Waiting Approval
                pending_approval = get_consultant_pending_inspections(establishment_id=est_id)
                
                # Combine technical jobs with business pending items for display
                # Or keep separate? Let's add 'in_approval' key
                pending = pending_jobs 
                
                processed_raw = get_consultant_inspections(establishment_id=est_id)
            else:
                # Gestor vê tudo ou filtrado
                pending = get_pending_jobs(company_id=current_user.company_id, allow_all=(current_user.company_id is None)) 
                pending_approval = [] # Gestor sees everything in processed_raw usually, or we can add specific section too
                processed_raw = get_processed_inspections_raw(establishment_id=est_uuid)
            
            # Se o banco retornou dados (ou consultor vazio mas ok), usa eles
            if processed_raw is not None:  
                def list_errors():
                    # Improve error mapping here or just return raw names
                    files = drive_service.list_files(FOLDER_ERROR, extension='.pdf')
                    mapped_errors = []
                    for f in files[:10]:
                        mapped_errors.append({'name': f['name'], 'error': 'Erro no processamento (Verificar logs)'})
                    return mapped_errors
                
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
        files = drive_service.list_files(FOLDER_IN, extension='.pdf')
        return [{'name': f['name']} for f in files[:10]]

    def list_errors():
        files = drive_service.list_files(FOLDER_ERROR, extension='.pdf')
        return [{'name': f['name']} for f in files[:10]]

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
        
    # Original Drive-based logic (fallback)
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
            return "PDF não encontrado", 404
            
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

@app.route('/review/<file_id>') # file_id aqui é o ID do JSON no Drive
@login_required
def review_page(file_id):
    if not drive_service:
        flash("Drive indisponível", "error")
        return redirect(url_for('dashboard'))

    try:
        data = drive_service.read_json(file_id)
        
        # Fetch Establishment Info for Approval Modal
        establishment_info = None
        try:
            from src.database import get_db
            from src.models_db import Establishment
            db = database.db_session
            est_name = data.get('estabelecimento')
            if est_name:
                establishment_info = db.query(Establishment).filter_by(name=est_name).first()
                # Force load contacts if lazy loading issues (though SQLA usually handles it in template if session open, but we close session)
                # Since session is closed in finally block (or here manual close loop?), better to eager load or convert to list
                if establishment_info:
                    print(f"Estabelecimento encontrado: {establishment_info.name}, Contatos: {len(establishment_info.contacts)}")
            
            # Note: We keep session open? No, db acts as scoped usually but here we derived it.
            # safe approach: pass establishment_info but ensure contacts are accessed before close, 
            # OR pass list of contacts explicitly.
            contacts_list = []
            if establishment_info:
                contacts_list = [{'name': c.name, 'phone': c.phone, 'id': c.id} for c in establishment_info.contacts]
                # Fallback: if no contacts but we have responsible_name on est
                if not contacts_list and establishment_info.responsible_name:
                     contacts_list.append({'name': establishment_info.responsible_name, 'phone': establishment_info.responsible_phone, 'id': 'default'})
            
            # db.close() handled by teardown
        except Exception as db_e:
            logger.error(f"Error fetching establishment for review: {db_e}")
            contacts_list = []

        return render_template('review.html', file_id=file_id, data=data, 
                             establishment=establishment_info, 
                             contacts=contacts_list)
    except Exception as e:
        logger.error(f"Erro ao abrir Review {file_id}: {e}")
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

@app.route('/admin/api/jobs')
@login_required
@role_required(UserRole.ADMIN)
def admin_api_jobs():
    """Retorna todos os jobs ativos para o painel de monitoramento."""
    # Reutiliza get_pending_jobs com allow_all=True
    jobs = get_pending_jobs(allow_all=True)
    return jsonify({'success': True, 'jobs': jobs})

@app.route('/download_revised_pdf/<file_id>')
def download_revised_pdf(file_id):
    """Gera um novo PDF baseado no estado atual do JSON (inclui correções do usuário)."""
    if not drive_service or not pdf_service:
        return "Serviços indisponíveis", 500
        
    try:
        # 1. Ler dados atuais
        data = drive_service.read_json(file_id)
        
        # 2. Gerar PDF em memória
        pdf_bytes = pdf_service.generate_pdf_bytes(data)
        
        # 3. Retornar arquivo
        filename = f"Plano_Revisado_{data.get('estabelecimento', 'Relatorio').replace(' ', '_')}.pdf"
        
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
    expected_token = os.getenv('DRIVE_WEBHOOK_TOKEN')
    
    if token != expected_token:
        logger.warning(f"Webhook Unauthorized: {token}")
        return jsonify({'error': 'Unauthorized'}), 401

    # 2. Verifica Estado do Recurso
    resource_state = request.headers.get('X-Goog-Resource-State')
    # 'sync' é o teste inicial, 'add'/'update'/'trash' são eventos
    logger.info(f"Webhook Received: {resource_state}")

    if resource_state in ['add', 'update', 'chagne']: # 'change' typo fix if needed
        # Dispara processamento em Thread para não bloquear o Google
        # Google espera 200 OK rápido.
        try:
            from src.services.processor import processor_service
            thread = threading.Thread(target=processor_service.process_pending_files)
            thread.start()
            logger.info("Webhook: Processing triggered in background.")
        except Exception as e:
            logger.error(f"Webhook Trigger Error: {e}")
    
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

# --- Cloud Tasks Worker ---
@app.route('/worker/process', methods=['POST'])
@csrf.exempt
def worker_process():
    """
    Handler para tarefas do Cloud Tasks.
    Recebe { "job_id": "...", ... }
    """
    try:
        raw_data = request.data
        logger.info(f"📨 Worker raw body: {raw_data}")
        logger.info(f"📨 Worker headers: {request.headers}")

        payload = request.get_json(force=True)
        logger.info(f"📦 Worker parsed payload: {payload}")

        job_id = payload.get('job_id')
        
        if not job_id:
            logger.error(f"❌ Worker received task without job_id. Keys: {payload.keys()}")
            return f"Missing job_id. Keys received: {list(payload.keys())}", 400

        logger.info(f"👷 Worker received Job {job_id}")

        # Execute Job
        from src.services.job_processor import job_processor
        from src.models_db import Job
        
        # Use existing session
        job = database.db_session.query(Job).get(job_id)
        if not job:
            logger.error(f"❌ Job {job_id} not found in DB")
            # Return 200 to consume task and prevent infinite retries if it's a data issue?
            # Or 404? Cloud Tasks retries on 404/500/429.
            # If it's gone, it's gone. Consuming.
            return "Job not found", 200 
            
        job_processor.process_job(job)
        
        return "OK", 200
        
    except Exception as e:
        logger.error(f"❌ Worker Error: {e}")
        return str(e), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
