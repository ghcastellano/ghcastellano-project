import os
import io
import pypdf
import logging
from datetime import datetime
from typing import List, Optional
import uuid # Fix NameError
import structlog
from openai import OpenAI
from weasyprint import HTML, CSS
from jinja2 import Environment, FileSystemLoader
from dotenv import load_dotenv

from src import models # Corrected import path
from src.services.drive_service import drive_service
from src import database
from src.models_db import Client, Inspection, ActionPlan, ActionPlanItem, InspectionStatus, SeverityLevel, ActionPlanItemStatus, Job

# Configuração de Logs
logger = structlog.get_logger()

class ProcessorService:
    def __init__(self):
        # Configurações GCP
        self.project_id = os.getenv("GCP_PROJECT_ID")
        self.location = os.getenv("GCP_LOCATION", "us-central1")
        
        # Load Folder IDs from .env (Safe Defaults to avoid NoneType error)
        self.folder_in = os.getenv("FOLDER_ID_01_ENTRADA_RELATORIOS", "")
        self.folder_out = os.getenv("FOLDER_ID_02_PLANOS_GERADOS", "")
        self.folder_backup = os.getenv("FOLDER_ID_03_PROCESSADOS_BACKUP", "")
        self.folder_error = os.getenv("FOLDER_ID_99_ERROS", "")
        
        logger.info("Initializing ProcessorService (OpenAI Mode)", 
                    folder_in=self.folder_in, 
                    folder_out=self.folder_out, 
                    folder_backup=self.folder_backup, 
                    folder_error=self.folder_error)
        
        # Drive Service (Singleton injection preferred, or use global)
        self.drive_service = drive_service

        # Inicializa OpenAI
        try:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                # Security Log: Only show prefix and suffix
                prefix = api_key[:10] if len(api_key) > 10 else "SHORT"
                suffix = api_key[-4:] if len(api_key) > 4 else "????"
                logger.info("OpenAI Key Status", prefix=f"{prefix}...", suffix=f"...{suffix}")
            else:
                logger.warning("OPENAI_API_KEY não encontrada nas variáveis de ambiente.")
                
            self.client = OpenAI(api_key=api_key) if api_key else None
            self.model_name = "gpt-4o-mini"
        except Exception as e:
            logger.error("Falha ao inicializar OpenAI", error=str(e))
            self.client = None

        # Inicializa Jinja
        self.jinja_env = Environment(loader=FileSystemLoader('src/templates'))

    def process_pending_files(self):
        """
        Processa todos os arquivos na pasta de entrada.
        Pode ser chamado via Cron, Webhook ou Loop.
        """
        logger.info("🔍 Processor: Verificando arquivos pendentes...")
        try:
            files = self.drive_service.list_files(self.folder_in, mime_type='application/pdf')
            
            if not files:
                logger.info("Nenhum arquivo pendente encontrado.")
                return 0
            
            logger.info(f"📁 Encontrados {len(files)} arquivos.")
            count = 0
            for file_meta in files:
                self.process_single_file(file_meta)
                count += 1
            return count

        except Exception as e:
            logger.error(f"Erro no processamento em lote: {e}")
            return 0

    def process_single_file(self, file_meta, company_id: Optional[uuid.UUID] = None, establishment_id: Optional[uuid.UUID] = None, job: Optional[Job] = None):
        file_id = file_meta['id']
        filename = file_meta['name']
        logger.info("Processando Arquivo Único", filename=filename, id=file_id, company_id=company_id, est_id=establishment_id)
        
        try:
            # 1. Download
            file_content = self.drive_service.download_file(file_id)
            
            # 2. Analyze
            analysis_result = self.analyze_with_openai(file_content)
            report_data = analysis_result['data']
            usage = analysis_result['usage']
            
            # Update Job Metrics immediately (even if next steps fail)
            if job:
                job.cost_tokens_input = usage.get('prompt_tokens', 0)
                job.cost_tokens_output = usage.get('completion_tokens', 0)
                
                PRICE_IN = 0.15 / 1_000_000
                PRICE_OUT = 0.60 / 1_000_000
                job.cost_input_usd = job.cost_tokens_input * PRICE_IN
                job.cost_output_usd = job.cost_tokens_output * PRICE_OUT
                
                # BRL conversion (Fixed rate for now: 6.00)
                USD_BRL_RATE = 6.00
                job.cost_input_brl = job.cost_input_usd * USD_BRL_RATE
                job.cost_output_brl = job.cost_output_usd * USD_BRL_RATE
                
                # Flush to ensure if we crash later, some record of cost might remain? 
                # (Assuming nested transaction or just prepared for commit)
                try:
                    database.db_session.flush()
                except: pass

            # 3. Hash
            file_hash = self.calculate_hash(file_content)
            
            # 4. Generate & Upload
            output_link = None
            try:
                output_link = self.generate_pdf(report_data, filename)
                logger.info("Plano gerado e salvo", link=output_link)
            except Exception as pdf_err:
                 # CRITICAL FIX: Don't block DB save if PDF fails. We can retry PDF later.
                 logger.error(f"⚠️ PDF Gen Failed (Ignored to save Inspection): {pdf_err}")
                 import traceback
                 logger.error(traceback.format_exc())

            # 5. Save to DB (Always save if Analysis succeeded)
            self._save_to_db_logic(report_data, file_id, filename, output_link, file_hash, company_id=company_id, override_est_id=establishment_id)

            # Return usage for caller (JobProcessor)
            return {
                'usage': usage,
                'output_link': output_link
            }

            # 6. Backup (moved inside finally or similar if robustness needed, but OK here)
            try:
                self.drive_service.move_file(file_id, self.folder_backup)
            except: pass
            
        except Exception as e:
            logger.error("Erro processando arquivo", filename=filename, error=str(e))
            try:
                self.drive_service.move_file(file_id, self.folder_error)
            except:
                pass

    def extract_text_from_pdf_bytes(self, file_content: bytes) -> str:
        try:
            pdf_file = io.BytesIO(file_content)
            reader = pypdf.PdfReader(pdf_file)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            logger.error("Erro OCR/Text", error=str(e))
            raise

    def analyze_with_openai(self, file_content: bytes):
        pdf_text = self.extract_text_from_pdf_bytes(file_content)
        if not pdf_text.strip():
            raise ValueError("PDF vazio ou sem texto detectável.")

        prompt = """
        Você é um Engenheiro Sanitário Sênior e Auditor de Segurança Alimentar. 
        Analise o TEXTO extraído do relatório de inspeção e gere um Plano de Ação detalhado.
        
        DIRETRIZES CRÍTICAS:
        1. IDENTIFICAÇÃO: Ignore itens "Conformes" ou "Resolvidos". Foque apenas em "Não Conforme" ou "Parcialmente Conforme".
        2. BASE LEGAL: Para cada item, cite a legislação específica (ex: RDC 216/04, CVS 5/13, Portaria 2619, etc.). Seja preciso.
        3. AÇÃO CORRETIVA: Proponha soluções técnicas realistas e imediatas.
        4. PRAZO SUGERIDO: Estime um prazo sugerido baseado no risco (ex: "Imediato", "24h", "7 dias", "15 dias").
        5. RESUMO GERAL: Crie um resumo executivo de 2-3 parágrafos sobre o estado sanitário geral.
        6. PONTOS FORTES: Liste pelo menos 3 pontos onde o estabelecimento se destaca positivamente.
        7. ESTATÍSTICAS: Conte o total de itens, conformes e não conformes.

        Siga rigorosamente o JSON Schema fornecido.
        """
        
        try:
            completion = self.client.beta.chat.completions.parse(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": pdf_text}
                ],
                response_format=models.RelatorioInspecao,
            )

            
            # Extract usage
            usage = {
                'prompt_tokens': completion.usage.prompt_tokens,
                'completion_tokens': completion.usage.completion_tokens,
                'total_tokens': completion.usage.total_tokens
            }
            
            return {
                'data': completion.choices[0].message.parsed,
                'usage': usage
            }
        except Exception as e:
            logger.error("OpenAI Error", error=str(e))
            raise

    def generate_pdf(self, data, original_filename: str) -> str:
        try:
            clean_name = original_filename.replace('.pdf', '')
            output_filename = f"Plano_Acao_{clean_name}.pdf"
            json_filename = f"Plano_Acao_{clean_name}.json"
            
            temp_pdf = f"/tmp/{output_filename}"
            temp_json = f"/tmp/{json_filename}"
            
            # Render HTML
            template = self.jinja_env.get_template('base_layout.html')
            html_out = template.render(relatorio=data, data_geracao=datetime.now().strftime("%d/%m/%Y"))
            
            css = []
            if os.path.exists('src/templates/style.css'):
                css.append(CSS('src/templates/style.css'))
                
            HTML(string=html_out, base_url="src/templates").write_pdf(temp_pdf, stylesheets=css)
            
            # Upload PDF
            _, pdf_link = self.drive_service.upload_file(temp_pdf, self.folder_out, output_filename)
            
            # Upload JSON
            with open(temp_json, "w") as f:
                f.write(data.model_dump_json(indent=2))
            self.drive_service.upload_file(temp_json, self.folder_out, json_filename)
            
            # Cleanup
            if os.path.exists(temp_pdf): os.remove(temp_pdf)
            if os.path.exists(temp_json): os.remove(temp_json)

            return pdf_link
        except Exception as e:
            import traceback
            import sys
            logger.error("PDF Gen Error", error=str(e), traceback=traceback.format_exc())
            # logger.info(f"Modules Loaded: {'fpdf' in sys.modules}, {'pypdf' in sys.modules}")
            raise

    def calculate_hash(self, content: bytes) -> str:
        import hashlib
        return hashlib.md5(content).hexdigest()

    def normalize_name(self, name: str) -> str:
        """
        Standardizes establishment name: Uppercase, Remove Special Chars, Single Spaces.
        Ex: " Padaria  do João - (Matriz) " -> "PADARIA DO JOAO MATRIZ"
        """
        if not name: return ""
        import re
        import unicodedata
        
        # Normalize unicode (accents)
        nfkd_form = unicodedata.normalize('NFKD', name)
        only_ascii = nfkd_form.encode('ASCII', 'ignore').decode('utf-8')
        
        # Remove special chars (keep alphanumeric and space)
        clean = re.sub(r'[^a-zA-Z0-9\s]', ' ', only_ascii)
        
        # Collapse spaces and Uppercase
        return re.sub(r'\s+', ' ', clean).strip().upper()

    def _save_to_db_logic(self, report_data, file_id, filename, output_link, file_hash, company_id=None, override_est_id=None):
        """Helper to save to DB using Scoped Session"""
        session = database.db_session()
        try:
            # 1. Resolve Establishment
            from src.models_db import Establishment, Company, User
            
            # CHECK FOR DUPLICITY (Robustness)
            existing = session.query(Inspection).filter_by(drive_file_id=file_id).first()
            if existing:
                logger.info(f"♻️ Inspection for {file_id} already exists. Updating...")
                inspection = existing
                # Update status if needed, or just keep as is.
            else:
                inspection = Inspection(drive_file_id=file_id)
                session.add(inspection)
            
            target_est = None
            if override_est_id:
                target_est = session.query(Establishment).get(override_est_id)
            
            if not target_est and company_id:
                # Auto-Discovery by Name
                raw_name = report_data.estabelecimento.strip()
                clean_name = self.normalize_name(raw_name)
                
                candidates = session.query(Establishment).filter(
                    Establishment.company_id == company_id
                ).all()
                
                for cand in candidates:
                    if self.normalize_name(cand.name) == clean_name:
                        target_est = cand
                        break
                
                if not target_est:
                    # Auto-Register New Establishment
                    logger.info(f"🆕 Auto-Registering new Establishment: {clean_name} (Raw: {raw_name})")
                    target_est = Establishment(
                        name=clean_name, 
                        company_id=company_id,
                        drive_folder_id="" 
                    )
                    session.add(target_est)
                    session.flush() 
            
            if not target_est:
                 logger.warning("Construction of Establishment failed (No context).")
            
            est_id = target_est.id if target_est else None

            # 2. Web Link extraction logic (Simplified)
            file_web_link = "" 
            pdf_drive_id = "pending_search" 

            # Update Inspection
            inspection.establishment_id = est_id
            inspection.drive_web_link = file_web_link
            inspection.file_hash = file_hash
            inspection.status = InspectionStatus.WAITING_APPROVAL
            inspection.ai_raw_response = report_data.model_dump()
            
            session.flush()
            
            # Action Plan (Upsert logic)
            action_plan = session.query(ActionPlan).filter_by(inspection_id=inspection.id).first()
            if not action_plan:
                action_plan = ActionPlan(inspection_id=inspection.id)
                session.add(action_plan)
                
            action_plan.final_pdf_drive_id = pdf_drive_id
            action_plan.final_pdf_public_link = output_link
            
            # Save POC Rich Data
            action_plan.summary_text = report_data.resumo_geral
            action_plan.strengths_text = ", ".join(report_data.pontos_fortes) if report_data.pontos_fortes else ""
            
            # Simple Stats Calculation
            total = len(report_data.nao_conformidades)
            action_plan.stats_json = {
                "total_items": total,
                "score": report_data.pontuacao_geral
            }
            
            session.flush()
            
            # Items (Clear old and re-add for simplicity of 'sync')
            session.query(ActionPlanItem).filter_by(action_plan_id=action_plan.id).delete()
            
            severity_map = {"Crítico": SeverityLevel.CRITICAL, "Alto": SeverityLevel.HIGH, "Médio": SeverityLevel.MEDIUM, "Baixo": SeverityLevel.LOW}
            
            for item in report_data.nao_conformidades:
                sev = SeverityLevel.MEDIUM
                if item.acoes_corretivas:
                    prio = item.acoes_corretivas[0].prioridade
                    if prio == "Alta": sev = SeverityLevel.HIGH
                    elif prio == "Baixa": sev = SeverityLevel.LOW
                
                correction_text = "\n".join([ac.descricao for ac in item.acoes_corretivas])
                
                plan_item = ActionPlanItem(
                    action_plan_id=action_plan.id,
                    problem_description=f"{item.item}: {item.descricao}",
                    corrective_action=correction_text,
                    legal_basis=item.legislacao_relacionada or "",
                    ai_suggested_deadline=item.acoes_corretivas[0].prazo_sugerido if item.acoes_corretivas else "Imediato",
                    severity=sev,
                    status=ActionPlanItemStatus.OPEN
                )
                session.add(plan_item)
            
            session.commit()
            logger.info("DB Save Success (Establishment/Inspection)")
            
        except Exception as e:
            logger.error(f"DB Save Error: {e}")
            session.rollback()
            raise e # RE-RAISE to notify JobProcessor!

            
            
# Instantiate Singleton Safely at Module Level
try:
    processor_service = ProcessorService()
except Exception as e:
    logger.error(f"Failed to instantiate ProcessorService: {e}")
    processor_service = None

