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
from src.models_db import Client, Inspection, ActionPlan, ActionPlanItem, InspectionStatus, SeverityLevel, ActionPlanItemStatus

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
        
        logger.info("Initializing ProcessorService (OpenAI Mode)", folder_in=self.folder_in)
        
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

    def process_single_file(self, file_meta, company_id: Optional[uuid.UUID] = None, establishment_id: Optional[uuid.UUID] = None):
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
            
            # 3. Hash
            file_hash = self.calculate_hash(file_content)
            
            # 4. Generate & Upload
            output_link = self.generate_pdf(report_data, filename)
            logger.info("Plano gerado e salvo", link=output_link)

            # 5. Save to DB
            self._save_to_db_logic(report_data, file_id, filename, output_link, file_hash, company_id=company_id, override_est_id=establishment_id)

            # Return usage for caller (JobProcessor)
            return {
                'usage': usage,
                'output_link': output_link
            }

            # 6. Backup
            self.drive_service.move_file(file_id, self.folder_backup)
            
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
        Você é um Engenheiro Sanitário Sênior. Analise o TEXTO do relatório.
        Objetivos:
        1. Identificar Não Conformidades e Parcialmente Conformes.
        2. Ignorar itens resolvidos.
        3. Propor ações (RDC 216).
        4. Resumir.
        Responda JSON Schema.
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
            logger.error("PDF Gen Error", error=str(e))
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
            target_est = None
            
            if override_est_id:
                target_est = session.query(Establishment).get(override_est_id)
            
            if not target_est and company_id:
                # Auto-Discovery by Name
                raw_name = report_data.estabelecimento.strip()
                clean_name = self.normalize_name(raw_name)
                
                # Try Exact Match on Clean Name (assuming DB has clean names or we match gently)
                # Ideally DB names should be clean. For now, we try matching against 'name' column.
                
                candidates = session.query(Establishment).filter(
                    Establishment.company_id == company_id
                ).all()
                
                # In-memory fuzzy match (better than limited SQL like on encrypted/messy data)
                # or just iterate and normalize data
                for cand in candidates:
                    if self.normalize_name(cand.name) == clean_name:
                        target_est = cand
                        break
                
                if not target_est:
                    # Auto-Register New Establishment
                    logger.info(f"🆕 Auto-Registering new Establishment: {clean_name} (Raw: {raw_name})")
                    target_est = Establishment(
                        name=clean_name, # Storing Clean Name!
                        company_id=company_id,
                        drive_folder_id="" 
                    )
                    session.add(target_est)
                    session.flush() # Get ID
            
            # If still no establishment (e.g. no company_id context?), we might have a problem.
            # Fallback to Legacy Client behavior ONLY if absolutely necessary, but preferably fail or use dummy.
            if not target_est:
                 logger.warning("Construction of Establishment failed (No context).")
                 # For MVP safety, skip saving if we can't link, or save as Orphan (nullable).
            
            est_id = target_est.id if target_est else None

            # 2. Web Link extraction logic (Simplified)
            file_web_link = "" 
            pdf_drive_id = "pending_search" 

            # Create Inspection (V3 Model)
            inspection = Inspection(
                establishment_id=est_id,
                # client_id=None, # Deprecated
                drive_file_id=file_id,
                drive_web_link=file_web_link,
                file_hash=file_hash,
                status=InspectionStatus.WAITING_APPROVAL,
                ai_raw_response=report_data.model_dump() # Pydantic v2
            )
            session.add(inspection)
            session.flush()
            
            action_plan = ActionPlan(
                inspection_id=inspection.id,
                final_pdf_drive_id=pdf_drive_id,
                final_pdf_public_link=output_link
            )
            session.add(action_plan)
            session.flush()
            
            # Items
            severity_map = {"Crítico": SeverityLevel.CRITICAL, "Alto": SeverityLevel.HIGH, "Médio": SeverityLevel.MEDIUM, "Baixo": SeverityLevel.LOW}
            
            for item in report_data.nao_conformidades:
                # Parse item status if available in model, else assume OPEN
                # item is NaoConformidade model
                # Check mapping
                # The model NaoConformidade has field 'status_item'.
                # But ActionPlanItemStatus is OPEN/RESOLVED.
                # Logic: If 'Conforme', maybe don't add? But prompt asked to ignore resolved.
                # So all present here are deficiencies.
                
                # Determine severity. 'item' doesn't have severity field in NaoConformidade model? 
                # Wait, let's check NaoConformidade model in previous turn.
                # It has `acoes_corretivas` list. `AcaoCorretiva` has `prioridade`.
                # We can map Priority -> Severity.
                
                sev = SeverityLevel.MEDIUM
                if item.acoes_corretivas:
                    prio = item.acoes_corretivas[0].prioridade
                    if prio == "Alta": sev = SeverityLevel.HIGH
                    elif prio == "Baixa": sev = SeverityLevel.LOW
                
                # correction action text
                correction_text = "\n".join([ac.descricao for ac in item.acoes_corretivas])
                
                plan_item = ActionPlanItem(
                    action_plan_id=action_plan.id,
                    problem_description=f"{item.item}: {item.descricao}",
                    corrective_action=correction_text,
                    legal_basis=item.legislacao_relacionada or "",
                    severity=sev,
                    status=ActionPlanItemStatus.OPEN
                )
                session.add(plan_item)
            
            session.commit()
            logger.info("DB Save Success (Establishment/Inspection)")
            
        except Exception as e:
            logger.error(f"DB Save Error: {e}")
            session.rollback()
            # Don't raise, continue flow
            
            
# Instantiate Singleton Safely at Module Level
try:
    processor_service = ProcessorService()
except Exception as e:
    logger.error(f"Failed to instantiate ProcessorService: {e}")
    processor_service = None

