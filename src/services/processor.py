
import os
import json
import logging
import io
from datetime import datetime, timezone, timedelta
BRAZIL_TZ = timezone(timedelta(hours=-3))
import uuid
import structlog
import pypdf
from weasyprint import HTML, CSS
from sqlalchemy.orm import Session

# Local Imports
from src.config import config
from src.config_helper import get_config
from src.database import get_db, SessionLocal
from src import database # access to db_session
from src.services.drive_service import drive_service
from src.services.storage_service import storage_service
from src.models_db import Inspection, ActionPlan, ActionPlanItem, ActionPlanItemStatus, SeverityLevel, InspectionStatus, Company, Establishment, Job, JobStatus
from src.error_codes import ErrorCode

# ... (rest of imports)


# Updated Model Import
from src.models import ChecklistSanitario

logger = structlog.get_logger()

class ProcessorService:
    def __init__(self):
        # Configuracoes GCP
        self.project_id = get_config("GCP_PROJECT_ID")
        self.location = get_config("GCP_LOCATION", "us-central1")

        # Load Folder IDs (DB > env > empty string)
        self.folder_in = get_config("FOLDER_ID_01_ENTRADA_RELATORIOS", "")
        self.folder_out = get_config("FOLDER_ID_02_PLANOS_GERADOS", "")
        self.folder_backup = get_config("FOLDER_ID_03_PROCESSADOS_BACKUP", "")
        self.folder_error = get_config("FOLDER_ID_99_ERROS", "")
        
        logger.info("Initializing ProcessorService (OpenAI Mode)", 
                    folder_in=self.folder_in, 
                    folder_out=self.folder_out, 
                    folder_backup=self.folder_backup, 
                    folder_error=self.folder_error)
        
        # Drive Service (Singleton injection preferred, or use global)
        self.drive_service = drive_service

        # Inicializa OpenAI
        try:
            api_key = get_config("OPENAI_API_KEY")
            if api_key:
                # Security: Only log that key is present, never log any part of the key
                logger.info("OpenAI API key configured: YES")
            else:
                logger.warning("OpenAI API key configured: NO - OPENAI_API_KEY not found")
                
            from openai import OpenAI
            self.client = OpenAI(api_key=api_key) if api_key else None
            self.model_name = "gpt-4o-mini" # [COST-OPTIMIZATION] 15x Cheaper, supports Structured Outputs
        except Exception as e:
            logger.error("Falha ao inicializar OpenAI", error=str(e))
            self.client = None

        # Inicializa Jinja
        from jinja2 import Environment, FileSystemLoader
        self.jinja_env = Environment(loader=FileSystemLoader('src/templates'), autoescape=True)

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
                # For basic processing we just need file meta
                self.process_single_file(file_meta)
                count += 1
            return count

        except Exception as e:
            logger.error(f"Erro no processamento em lote: {e}")
            return 0

    def _log_trace(self, file_id, stage, status, message, details=None):
        """
        Appends a log entry to the Inspection's processing_logs.
        Creates Inspection if it doesn't exist yet (for initial steps).
        """
        # [FIX] Use a dedicated session for logging to avoid closing the main shared session
        # This prevents 'Instance not bound to Session' errors in the main flow
        from src.database import engine
        from sqlalchemy.orm import sessionmaker
        
        # Create a new session factory just for this operation if needed, or use raw engine
        SessionLog = sessionmaker(bind=engine)
        session = SessionLog()
        
        try:
            # Avoid circular imports if possible, but localized import is safe here
            from src.models_db import Inspection, InspectionStatus
            
            inspection = session.query(Inspection).filter_by(drive_file_id=file_id).first()
            if not inspection:
                inspection = Inspection(drive_file_id=file_id, status=InspectionStatus.PROCESSING)
                session.add(inspection)
                session.flush() # Get ID
            
            entry = {
                "timestamp": datetime.now().isoformat(),
                "stage": stage,
                "status": status,
                "message": message,
                "details": details or {}
            }
            
            # Append to list (Postgres JSONB needs re-assignment to detect change usually, or mutable flag)
            current_logs = list(inspection.processing_logs) if inspection.processing_logs else []
            current_logs.append(entry)
            inspection.processing_logs = current_logs 
            
            # Update overall status if Error
            if status == "FAILED":
                inspection.status = InspectionStatus.REJECTED # Or specialized 'FAILED' status if enum allows
            
            session.commit()
            logger.info(f"📝 Trace [{stage}]: {message}", file_id=file_id)
        except Exception as e:
            logger.error(f"Failed to write trace log: {e}")
            session.rollback()
        finally:
            session.close() # Safe to close this private session

    def process_single_file(self, file_meta, company_id=None, establishment_id=None, job_id=None, job=None, file_content=None):
        file_id = file_meta['id']
        filename = file_meta['name']

        # 0. Start Trace
        self._log_trace(file_id, "INIT", "STARTED", f"Iniciando processamento de {filename}")

        try:
            # 1. Download & Hash Check (Idempotency)
            if file_content:
                self._log_trace(file_id, "DOWNLOAD", "SUCCESS", "Arquivo recebido diretamente (sem Drive)")
            else:
                self._log_trace(file_id, "DOWNLOAD", "RUNNING", "Baixando arquivo do Drive...")
                file_content = self.drive_service.download_file(file_id)
                self._log_trace(file_id, "DOWNLOAD", "SUCCESS", "Download concluído")
            
            file_hash = self.calculate_hash(file_content)

            # Check for duplicate processing (skip only REJECTED - allows retry)
            session = database.db_session()
            existing_insp = session.query(Inspection).filter_by(file_hash=file_hash).filter(
                Inspection.status.notin_([InspectionStatus.REJECTED])
            ).filter(
                Inspection.drive_file_id != file_id  # Nao bloquear a si mesmo
            ).first()

            if existing_insp:
                session.close()
                logger.info(f"♻️ Skipping duplicate file (Hash: {file_hash}) - existing: {existing_insp.drive_file_id} ({existing_insp.status.value})")
                self._log_trace(file_id, "SKIPPED", "SUCCESS", f"Arquivo duplicado detectado (existe como {existing_insp.drive_file_id}). Pulando.")

                # Update Job as Skipped
                if job_id:
                    self._update_job_status(job_id, "SKIPPED", {
                        "code": "DUPLICATE",
                        "admin_msg": f"Arquivo duplicado (hash identico a {existing_insp.drive_file_id}, status: {existing_insp.status.value})",
                        "user_msg": "Este arquivo ja foi enviado e processado anteriormente.",
                        "reason": "duplicate",
                        "existing_id": existing_insp.drive_file_id,
                    })

                return {'status': 'skipped', 'reason': 'duplicate', 'existing_id': existing_insp.drive_file_id}
            session.close()

            # 2. Update Job to PROCESSING status
            if job_id:
                self._update_job_status(job_id, JobStatus.PROCESSING)
                self._log_trace(file_id, "JOB_STATUS", "UPDATED", "Job marcado como PROCESSING")

            # 3. Extract text (OCR)
            self._log_trace(file_id, "OCR", "RUNNING", "Extraindo texto do PDF...")
            try:
                pdf_text = self.extract_text_from_pdf_bytes(file_content)
                char_count = len(pdf_text.strip())

                if char_count == 0:
                    raise ValueError("PDF vazio (sem texto extraível)")

                self._log_trace(file_id, "OCR", "SUCCESS", f"Texto extraído com sucesso ({char_count} caracteres)")
            except Exception as ocr_error:
                error_obj = ErrorCode.get_error(ocr_error)
                self._log_trace(file_id, "OCR", "FAILED", error_obj['user_msg'], details=error_obj)
                if job_id:
                    self._update_job_status(job_id, JobStatus.FAILED, error_data=error_obj)
                raise

            # 4. Analyze with OpenAI
            self._log_trace(file_id, "AI_ANALYSIS", "RUNNING", f"Enviando para análise da IA ({self.model_name})...")
            try:
                result = self.analyze_with_openai(file_content)
                data: ChecklistSanitario = result['data']
                usage = result['usage']

                areas_count = len(data.areas_inspecionadas) if hasattr(data, 'areas_inspecionadas') else 0
                items_count = sum(len(area.itens) for area in data.areas_inspecionadas) if hasattr(data, 'areas_inspecionadas') else 0

                self._log_trace(file_id, "AI_ANALYSIS", "SUCCESS",
                              f"Análise concluída: {areas_count} áreas, {items_count} itens detectados",
                              details={'areas': areas_count, 'items': items_count, **usage})
            except Exception as ai_error:
                error_obj = ErrorCode.get_error(ai_error)
                self._log_trace(file_id, "AI_ANALYSIS", "FAILED", error_obj['user_msg'], details=error_obj)
                if job_id:
                    self._update_job_status(job_id, JobStatus.FAILED, error_data=error_obj)
                raise
            
            # Update Job Metrics immediately (Persisted)
            if job_id:
                self._update_job_metrics(job_id, usage)

            # 3. Hash
            file_hash = self.calculate_hash(file_content)
            
            # 4. Generate & Upload PDF (REMOVED as per V17 Flow - On Demand Only)
            output_link = None


            # 5. Save to DB (Crucial Step: Mapping Nested Areas to Flat Items)
            self._log_trace(file_id, "DB_SAVE", "RUNNING", "Salvando dados no Banco de Dados...")
            self._save_to_db_logic(data, file_id, filename, output_link, file_hash, company_id=company_id, override_est_id=establishment_id)
            self._log_trace(file_id, "COMPLETED", "SUCCESS", "Processamento finalizado com sucesso.")

            # Final Job Success
            if job_id:
                final_result = {
                    'usage': usage,
                    'output_link': output_link,
                    'title': getattr(data, 'titulo', None),
                    'summary': getattr(data, 'summary', None) or getattr(data, 'summary_text', None)
                }
                self._update_job_status(job_id, JobStatus.COMPLETED, result=final_result)

            # Return usage for caller (JobProcessor)
            return {
                'usage': usage,
                'output_link': output_link
            }
            
        except Exception as e:
            # Get structured error code
            error_obj = ErrorCode.get_error(e)

            logger.error("Erro processando arquivo",
                        filename=filename,
                        error_code=error_obj['code'],
                        error_msg=str(e))

            self._log_trace(file_id, "ERROR", "FAILED", error_obj['user_msg'], details=error_obj)

            if job_id:
                self._update_job_status(job_id, JobStatus.FAILED, error_data=error_obj)

            try:
                if not file_id.startswith('gcs:') and not file_id.startswith('upload:'):
                    self.drive_service.move_file(file_id, self.folder_error)
                    self._log_trace(file_id, "ERROR", "MOVED", "Arquivo movido para pasta de Erros")
            except:
                pass

            raise # Re-raise to let caller (app.py) know it failed

    def _update_job_metrics(self, job_id, usage):
        """Update job metrics independently of main session"""
        from src.models_db import Job
        session = database.db_session()
        try:
            job = session.query(Job).get(job_id)
            if job:
                job.cost_tokens_input = usage.get('prompt_tokens', 0)
                job.cost_tokens_output = usage.get('completion_tokens', 0)
                job.api_calls_count = (job.api_calls_count or 0) + 1
                
                # Costs
                cost_in = (job.cost_tokens_input / 1_000_000) * 0.15
                cost_out = (job.cost_tokens_output / 1_000_000) * 0.60
                job.cost_input_usd = cost_in
                job.cost_output_usd = cost_out
                job.cost_input_brl = cost_in * 6.0
                job.cost_output_brl = cost_out * 6.0
                
                job.result_payload = {'usage': usage}
                session.commit()
                logger.info(f"Job {job_id} metrics updated.")
            else:
                logger.warning(f"Job {job_id} not found in DB during metric update.")
        except Exception as e:
            logger.error(f"Failed to update job metrics {job_id}: {e}")
            session.rollback()
        finally:
            session.close()

    def _update_job_status(self, job_id, status, error_data=None, result=None):
        """Update job status independently"""
        from src.models_db import Job, JobStatus # Re-import locally to be safe
        session = database.db_session()
        try:
            job = session.query(Job).get(job_id)
            if job:
                # Handle String vs Enum
                if isinstance(status, str):
                    try:
                        status = JobStatus(status)
                    except:
                        # Fallback try mapping
                        status = JobStatus[status] if status in JobStatus.__members__ else status

                job.status = status
                if status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.SKIPPED]:
                    job.finished_at = datetime.utcnow()

                # [FIX] Robust error logging
                if error_data:
                    try:
                        # Ensure error_data is a dict
                        if not isinstance(error_data, dict):
                            error_data = {"code": "ERR_9001", "admin_msg": str(error_data), "user_msg": "Erro desconhecido"}

                        # Get existing errors (parse if JSON string, or start empty list)
                        existing_errors = []
                        if job.error_log:
                            try:
                                # Try to parse as JSON array first
                                existing_errors = json.loads(job.error_log)
                                if not isinstance(existing_errors, list):
                                    # If it's a string or other type, convert to list
                                    existing_errors = [existing_errors]
                            except json.JSONDecodeError:
                                # If parsing fails, treat as legacy string format
                                existing_errors = [{"legacy_error": job.error_log}]

                        # Append new error with timestamp
                        error_entry = {
                            "timestamp": datetime.utcnow().isoformat(),
                            **error_data
                        }
                        existing_errors.append(error_entry)

                        # Save as JSON array
                        job.error_log = json.dumps(existing_errors, ensure_ascii=False)

                        logger.info(f"Error logged for job {job_id}: {error_data.get('code', 'UNKNOWN')}")
                    except Exception as error_log_exception:
                        # If error logging fails, at least save something
                        logger.error(f"Failed to log structured error for job {job_id}: {error_log_exception}")
                        job.error_log = json.dumps([{
                            "timestamp": datetime.utcnow().isoformat(),
                            "code": "ERR_9001",
                            "admin_msg": f"Error logging failed: {str(error_log_exception)}",
                            "user_msg": "Erro ao registrar erro (sistema instável)",
                            "original_error": str(error_data)
                        }], ensure_ascii=False)

                if result:
                    # Merge with existing payload
                    current_payload = job.result_payload or {}
                    # If current is not dict (rare), force it
                    if not isinstance(current_payload, dict): current_payload = {}
                    current_payload.update(result)
                    job.result_payload = current_payload

                session.commit()
                logger.info(f"Job {job_id} status updated to {status}.")
            else:
                logger.warning(f"Job {job_id} not found for status update.")
        except Exception as e:
            logger.error(f"Failed to update job status {job_id}: {e}")
            session.rollback()
        finally:
            session.close()

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

    def _extract_areas_below_100(self, pdf_text: str) -> list:
        """Pre-process PDF text to extract areas with < 100% from summary table."""
        import re
        areas = []
        # Match patterns like: "Cozinha / Área de Manipulação 15.52 27.27 56.90%"
        # The summary table has: Area Name | Nota obtida | Máximo | Aproveitamento
        pattern = r'([A-ZÀ-Ú][^\n\d]{3,50}?)\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)%'
        for match in re.finditer(pattern, pdf_text[:2000]):  # Summary table is at the top
            name = match.group(1).strip()
            score = match.group(2).replace(',', '.')
            max_score = match.group(3).replace(',', '.')
            pct = match.group(4).replace(',', '.')
            # Skip non-area entries
            skip_words = ['não se aplica', 'acompanhante', 'inconformidade', 'comentário', 'observaç']
            if any(w in name.lower() for w in skip_words):
                continue
            if float(pct) < 100.0:
                areas.append({'name': name, 'score': score, 'max': max_score, 'pct': pct})
        if areas:
            logger.info(f"Pre-processed {len(areas)} areas below 100%: {[a['name'] for a in areas]}")
        return areas

    def _extract_section_text(self, pdf_text: str, area_name: str) -> str:
        """Extract the text of a specific section from the PDF by area name."""
        import re
        # Find the section header: "N - Area Name" where N is the section number
        # Build patterns to match variations of the area name
        name_parts = area_name.split('/')
        first_part = name_parts[0].strip()
        # Escape regex special chars
        escaped = re.escape(first_part)
        pattern = rf'(\d+)\s*-\s*{escaped}'
        match = re.search(pattern, pdf_text, re.IGNORECASE)
        if not match:
            # Try shorter match (first word)
            first_word = first_part.split()[0] if first_part.split() else first_part
            pattern = rf'(\d+)\s*-\s*[^\\n]*{re.escape(first_word)}'
            match = re.search(pattern, pdf_text, re.IGNORECASE)
        if not match:
            return ""

        section_num = match.group(1)
        start = match.start()
        # Find next top-level section (different number)
        next_section = re.search(rf'\n(\d+)\s*-\s*(?!.*\d+\.\d+)', pdf_text[start + 10:])
        if next_section:
            end = start + 10 + next_section.start()
        else:
            end = len(pdf_text)
        return pdf_text[start:end]

    def _validate_and_retry_missing_areas(self, data, areas_below_100, pdf_text, total_usage):
        """Check if AI response covers all expected areas; retry for missing ones."""
        if not areas_below_100:
            return data, total_usage

        # Normalize area names from AI response for comparison
        ai_area_names = [a.nome_area.lower().strip() for a in data.areas_inspecionadas]

        missing_areas = []
        for expected in areas_below_100:
            expected_lower = expected['name'].lower().strip()
            # Fuzzy match: check if expected name is contained in any AI area name or vice versa
            found = any(
                expected_lower in ai_name or ai_name in expected_lower
                or expected_lower.split('/')[0].strip() in ai_name
                for ai_name in ai_area_names
            )
            if not found:
                missing_areas.append(expected)

        if not missing_areas:
            logger.info("All expected areas found in AI response")
            return data, total_usage

        logger.warning(f"Missing {len(missing_areas)} areas: {[a['name'] for a in missing_areas]}. Retrying...")

        # Extract section texts for each missing area
        sections_text = ""
        for area in missing_areas:
            section = self._extract_section_text(pdf_text, area['name'])
            if section:
                sections_text += f"\n\n--- SEÇÃO: {area['name']} ({area['score']}/{area['max']} = {area['pct']}%) ---\n{section}"

        if not sections_text.strip():
            logger.error("Could not extract section text for missing areas")
            return data, total_usage

        # Focused retry for missing areas
        from src.models import AreaInspecao
        retry_prompt = f"""Você é um Auditor Sanitário. Analise SOMENTE as seções abaixo e extraia os itens NÃO CONFORMES e PARCIALMENTE CONFORMES.

REGRAS:
- "Resposta: Parcial" = "Parcialmente Conforme" → INCLUIR
- "Resposta: Não" com "(0.00% - 0.00 pontos)" em pergunta POSITIVA = "Não Conforme" → INCLUIR
- "Resposta: Não" em pergunta NEGATIVA (ex: "Foram encontrados produtos vencidos?") com pontuação > 0 = Conforme → NÃO INCLUIR
- "Resposta: Sim" com "(0.00% - 0.00 pontos)" em pergunta NEGATIVA = "Não Conforme" → INCLUIR
- Item com "Fotos da questão" ou "Comentário:" com evidência de problema = INCLUIR
- Para cada item: inclua item_verificado, status, observacao, fundamento_legal, acao_corretiva_sugerida, prazo_sugerido

Retorne um JSON com areas_inspecionadas contendo SOMENTE as áreas analisadas. Use o nome EXATO de cada área.
Os campos nome_estabelecimento, resumo_geral, pontuacao_geral, pontuacao_maxima_geral, aproveitamento_geral podem ser preenchidos com valores placeholder.

JSON Schema:
{json.dumps(ChecklistSanitario.model_json_schema(), indent=2)}"""

        try:
            retry_completion = self.client.beta.chat.completions.parse(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": retry_prompt},
                    {"role": "user", "content": f"Analise estas {len(missing_areas)} seções e extraia todos os itens com problema:\n{sections_text}"}
                ],
                response_format=ChecklistSanitario,
            )

            retry_data = retry_completion.choices[0].message.parsed
            retry_usage = {
                'prompt_tokens': retry_completion.usage.prompt_tokens,
                'completion_tokens': retry_completion.usage.completion_tokens,
                'total_tokens': retry_completion.usage.total_tokens
            }

            # Merge usage
            total_usage['prompt_tokens'] += retry_usage['prompt_tokens']
            total_usage['completion_tokens'] += retry_usage['completion_tokens']
            total_usage['total_tokens'] += retry_usage['total_tokens']

            # Merge areas that have actual items
            added = 0
            for area in retry_data.areas_inspecionadas:
                if area.itens:
                    data.areas_inspecionadas.append(area)
                    added += 1
                    logger.info(f"  Added missing area: {area.nome_area} ({len(area.itens)} items)")

            if added:
                logger.info(f"Retry added {added} missing areas")
            else:
                logger.warning("Retry returned no areas with items")

        except Exception as e:
            logger.error(f"Retry for missing areas failed: {e}")

        return data, total_usage

    def analyze_with_openai(self, file_content: bytes):
        pdf_text = self.extract_text_from_pdf_bytes(file_content)
        if not pdf_text.strip():
            raise ValueError("PDF vazio ou sem texto detectável.")

        # Updated Prompt: Uses user's trusted approach (Areas) + our requirements (Action/Deadline)
        schema_json = ChecklistSanitario.model_json_schema()

        # Pre-process: extract areas with < 100% from summary table to enforce completeness
        areas_below_100 = self._extract_areas_below_100(pdf_text)
        areas_instruction = ""
        if areas_below_100:
            areas_list = "\n".join([f"        - {a['name']} ({a['score']}/{a['max']} = {a['pct']}%)" for a in areas_below_100])
            areas_instruction = f"""
        ÁREAS OBRIGATÓRIAS (extraídas da tabela resumo do relatório):
        As seguintes {len(areas_below_100)} áreas possuem aproveitamento < 100% e DEVEM OBRIGATORIAMENTE aparecer em areas_inspecionadas com seus itens não conformes:
{areas_list}
        Se alguma dessas áreas estiver faltando na sua resposta, sua análise está INCOMPLETA e INCORRETA.
"""

        prompt = f"""
        Você é um Auditor Sanitário Sênior, especialista na legislação brasileira (RDC 216/2004, CVS-5/2013).
        Sua tarefa é analisar o texto COMPLETO do relatório de auditoria e transformá-lo em um CHECKLIST DE PLANO DE AÇÃO ESTRUTURADO, cobrindo TODAS as áreas do relatório.

        FORMATO DO RELATÓRIO DE ENTRADA:
        O relatório possui uma tabela resumo "Notas por tópico" no início, com cada área e seu aproveitamento.
        Em seguida, os itens de cada área seguem este padrão:
        - Número e pergunta do item, seguido de "(X.XX% - X.XX pontos)" que indica a pontuação OBTIDA naquele item
        - "Resposta: Sim/Não/Parcial/N.A./Não Aplicável/Não aplicável"
        - Opcionalmente: "Fotos da questão X.X" (indica evidência fotográfica de problema)
        - Opcionalmente: "Comentário: ..." (observação do auditor in-loco)

        REGRAS DE CLASSIFICAÇÃO DOS ITENS:
        1. "Resposta: Parcial" = SEMPRE "Parcialmente Conforme" → INCLUIR OBRIGATORIAMENTE
        2. "Resposta: Não" com pontuação "(0.00% - 0.00 pontos)" em pergunta POSITIVA = "Não Conforme" → INCLUIR
        3. "Resposta: Não" em perguntas NEGATIVAS (ex: "Foram encontrados produtos vencidos?", "Há outras inconformidades?", "Percepção de inconformidade?") onde "Não" = ausência de problema E pontuação > 0 = Conforme → NÃO INCLUIR
        4. "Resposta: Sim" com pontuação > 0 em pergunta POSITIVA (ex: "Está limpo?", "Está adequado?") = Conforme → NÃO INCLUIR
        5. "Resposta: Sim" com pontuação "(0.00% - 0.00 pontos)" em pergunta NEGATIVA (ex: "Foram encontrados produtos vencidos?", "Percepção de inconformidade?") = O "Sim" confirma a existência do PROBLEMA → "Não Conforme" → INCLUIR OBRIGATORIAMENTE
        6. "Resposta: Sim" em qualquer pergunta com Fotos ou Comentário de problema = "Não Conforme" → INCLUIR OBRIGATORIAMENTE
        7. "Resposta: N.A." ou "Não Aplicável" ou "Não aplicável" = Não se aplica → NÃO INCLUIR
        8. Se o item possui "Fotos da questão" ou "Comentário:" com evidência de problema = INCLUIR OBRIGATORIAMENTE como "Não Conforme" ou "Parcialmente Conforme"
{areas_instruction}
        REGRA DE COMPLETUDE (CRÍTICA - MÁXIMA PRIORIDADE):
        - Você DEVE processar o relatório INTEIRO do início ao fim, seção por seção.
        - Você DEVE capturar ABSOLUTAMENTE TODOS os itens não conformes e parcialmente conformes de TODAS as áreas.
        - NÃO pare após processar a primeira área. Continue até a última área do relatório.
        - NÃO resuma. NÃO agrupe itens similares. NÃO pule nenhum item.
        - Cada item com problema deve aparecer como um ChecklistItem individual na área correspondente.
        - MESMO que uma área tenha apenas 1 item com problema, ela DEVE ser incluída.

        DIRETRIZES:
        1. Identifique o Estabelecimento e a DATA DA INSPEÇÃO (Checklist Base).
        2. Crie um Resumo Geral robusto indicando as principais áreas críticas.
        3. Calcule ou extraia a PONTUAÇÃO GERAL e o APROVEITAMENTO GERAL do relatório.
        4. Para cada ÁREA FÍSICA com aproveitamento < 100%:
           - Use o nome da área EXATAMENTE como aparece no relatório (ex: 'Cozinha / Área de Manipulação', 'Estoque / Depósito', 'Sanitário / Vestiário de Funcionários').
           - Extraia 'pontuacao_obtida', 'pontuacao_maxima' e 'aproveitamento' da tabela resumo.
           - Liste TODOS os itens não conformes e parcialmente conformes desta área.
        5. Para cada item com problema:
           - item_verificado: Use o número e texto da pergunta original (ex: "2.1 - HIGIENIZAÇÃO: A área de manipulação...").
           - Status: 'Não Conforme' ou 'Parcialmente Conforme'.
           - Observação: Descreva a evidência. Se houver "Comentário:" do auditor, INCLUA-o na observação.
           - Fundamento Legal: Cite a legislação específica (RDC 216/2004, CVS-5/2013, etc.).
           - Ação Corretiva: Sugira a correção técnica IMEDIATA.
           - Prazo Sugerido: Baseado no risco (Imediato, 24 horas, 7 dias, 15 dias, 30 dias).

        REGRA CRÍTICA - O QUE NÃO É ÁREA:
        NÃO inclua como área seções que são metadados:
        - "Inconformidades resolvidas", "Acompanhante de visita", "Comentários gerais e observações"
        - Qualquer seção sem pontuação numérica real

        Sua resposta deve ser APENAS o objeto JSON compatível com o schema abaixo.
        IMPORTANTE: Os valores dentro do JSON devem ser texto puro (sem markdown).

        JSON Schema:
        {json.dumps(schema_json, indent=2)}
        """

        try:
            completion = self.client.beta.chat.completions.parse(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"Analise o relatório COMPLETO abaixo. Processe TODAS as {len(areas_below_100)} áreas com problemas identificadas na tabela resumo.\n\n{pdf_text}"}
                ],
                response_format=ChecklistSanitario,
            )

            usage = {
                'prompt_tokens': completion.usage.prompt_tokens,
                'completion_tokens': completion.usage.completion_tokens,
                'total_tokens': completion.usage.total_tokens
            }

            data = completion.choices[0].message.parsed

            # Post-processing: validate all expected areas are present, retry if missing
            data, usage = self._validate_and_retry_missing_areas(data, areas_below_100, pdf_text, usage)

            return {
                'data': data,
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
            
            import tempfile
            temp_dir = tempfile.gettempdir()
            temp_pdf = os.path.join(temp_dir, output_filename)
            temp_json = os.path.join(temp_dir, json_filename)
            
            # Render HTML
            template = self.jinja_env.get_template('pdf_template.html') # Updated to Validated Template
            # Pass data as 'relatorio' to match template
            html_out = template.render(relatorio=data, data_geracao=datetime.now(tz=BRAZIL_TZ).strftime("%d/%m/%Y"))
            
            css = []
            if os.path.exists('src/templates/style.css'):
                css.append(CSS('src/templates/style.css'))
                
            HTML(string=html_out, base_url="src/templates").write_pdf(temp_pdf, stylesheets=css)
            
            # Local Backup for Verification (Run BEFORE upload to ensure capture even if upload fails)
            local_output_dir = "data/output"
            if os.path.exists(local_output_dir):
                import shutil
                local_path = os.path.join(local_output_dir, output_filename)
                shutil.copy(temp_pdf, local_path)
                logger.info(f"📂 PDF Saved Locally: {local_path}")
            
            # Upload PDF
            try:
                # Primary: Drive
                upload_res = self.drive_service.upload_file(temp_pdf, self.folder_out, output_filename)
                if isinstance(upload_res, tuple) and len(upload_res) >= 2:
                    _, pdf_link = upload_res
                else:
                    pdf_link = None # Handle unexpected return (e.g. Mock returning single value or None)
                    logger.warning(f"⚠️ Drive upload returned unexpected format: {upload_res}")
            except Exception as e:
                if "quota" in str(e).lower() or "403" in str(e) or "storage" in str(e).lower():
                     logger.warning(f"⚠️ Drive Quota Limit for Output PDF. Falling back to StorageService for {output_filename}")
                     from src.services.storage_service import StorageService # Lazy import
                     # Assuming storage_service is not a class member yet? Wait, it is global in app.py but here? 
                     # Better to use the one passed or import global. 
                     # Checking imports... storage_service is not imported in this file globally. 
                     # I see 'storage_service' in process_single_file in previous edits (Step 15426). 
                     # Let's import it safely.
                     from src.app import storage_service
                     with open(temp_pdf, 'rb') as f_obj:
                        pdf_link = storage_service.upload_file(f_obj, "output", output_filename) # Using 'output' bucket/folder
                else:
                    raise e
            
            # Upload JSON
            with open(temp_json, "w", encoding="utf-8") as f:
                f.write(data.model_dump_json(indent=2))
            
            try:
                self.drive_service.upload_file(temp_json, self.folder_out, json_filename)
            except:
                pass # JSON backup failure is acceptable
            
            # Cleanup
            if os.path.exists(temp_pdf): os.remove(temp_pdf)
            if os.path.exists(temp_json): os.remove(temp_json)

            return pdf_link
        except Exception as e:
            import traceback
            import sys
            error_details = traceback.format_exc()
            print(f"CRITICAL PDF ERROR: {error_details}") # Force stdout
            logger.error("PDF Gen Error", error=str(e), traceback=error_details)
            return None

    def calculate_hash(self, content: bytes) -> str:
        import hashlib
        return hashlib.md5(content, usedforsecurity=False).hexdigest()

    def normalize_name(self, name: str) -> str:
        if not name: return ""
        import re
        import unicodedata
        nfkd_form = unicodedata.normalize('NFKD', name)
        only_ascii = nfkd_form.encode('ASCII', 'ignore').decode('utf-8')
        clean = re.sub(r'[^a-zA-Z0-9\s]', ' ', only_ascii)
        return re.sub(r'\s+', ' ', clean).strip().upper()

    def _save_to_db_logic(self, report_data: ChecklistSanitario, file_id, filename, output_link, file_hash, company_id=None, override_est_id=None):
        """Save structured ChecklistSanitario (Nested) to Flat DB Models"""
        session = database.db_session()
        try:
            # 1. Resolve Establishment
            from src.models_db import Establishment

            # Handle existing inspection
            existing = session.query(Inspection).filter_by(drive_file_id=file_id).first()
            if existing:
                inspection = existing
            else:
                inspection = Inspection(drive_file_id=file_id)
                session.add(inspection)
            
            target_est = None
            if override_est_id:
                target_est = session.query(Establishment).get(override_est_id)
            
            if not target_est and company_id:
                # Auto-Discovery by Name
                raw_name = report_data.nome_estabelecimento.strip()
                clean_name = self.normalize_name(raw_name)
                
                candidates = session.query(Establishment).filter(Establishment.company_id == company_id).all()
                for cand in candidates:
                    if self.normalize_name(cand.name) == clean_name:
                        target_est = cand
                        break
                
                if not target_est:
                    # Auto-Register New Establishment
                    logger.info(f"🆕 Auto-Registering: {clean_name}")
                    target_est = Establishment(
                        name=clean_name, 
                        company_id=company_id,
                        drive_folder_id="" 
                    )
                    session.add(target_est)
                    session.flush() 
            
            est_id = target_est.id if target_est else None
            logger.info(f"📍 Target Establishment: {target_est.name if target_est else 'None'} (ID: {est_id})")

            # Filter out non-area sections BEFORE saving ai_raw_response
            # Safety: rescue NC/partial items from excluded areas into "Geral"
            EXCLUDED_AREA_KEYWORDS = [
                'inconformidade', 'observaç', 'comentário', 'acompanhante',
                'responsável técnico', 'conclus', 'parecer', 'resumo geral',
                'resultado geral', 'não conformidades resolvidas', 'dados do responsável',
                'informações gerais', 'dados gerais', 'assinatura',
            ]
            original_count = len(report_data.areas_inspecionadas)
            filtered_areas = []
            rescued_items = []
            for area in report_data.areas_inspecionadas:
                area_name_lower = area.nome_area.lower().strip()
                is_excluded = any(kw in area_name_lower for kw in EXCLUDED_AREA_KEYWORDS)
                if is_excluded:
                    # Rescue NC/Partial items before discarding the area
                    nc_items = [
                        it for it in area.itens
                        if 'não conforme' in it.status.lower() or 'parcialmente' in it.status.lower()
                    ]
                    if nc_items:
                        rescued_items.extend(nc_items)
                        logger.warning(f"  🚨 Rescued {len(nc_items)} NC items from excluded area: '{area.nome_area}'")
                    else:
                        logger.info(f"  ⚠️ Filtering non-area section: '{area.nome_area}'")
                    continue
                if area.pontuacao_maxima == 0 and len(area.itens) == 0:
                    logger.info(f"  ⚠️ Filtering empty area (0 max score, 0 items): '{area.nome_area}'")
                    continue
                filtered_areas.append(area)

            # Merge rescued items into first area or create "Geral"
            if rescued_items:
                if filtered_areas:
                    filtered_areas[0].itens.extend(rescued_items)
                    logger.info(f"  ✅ Merged {len(rescued_items)} rescued items into '{filtered_areas[0].nome_area}'")
                else:
                    from src.models import AreaInspecao
                    geral = AreaInspecao(
                        nome_area="Geral",
                        itens=rescued_items,
                        pontuacao_obtida=0, pontuacao_maxima=0,
                        aproveitamento=0, resumo_area=""
                    )
                    filtered_areas.append(geral)
                    logger.info(f"  ✅ Created 'Geral' area with {len(rescued_items)} rescued items")

            report_data.areas_inspecionadas = filtered_areas
            if original_count != len(filtered_areas):
                logger.info(f"🔍 Areas filtered: {original_count} → {len(filtered_areas)}")

            # Update Inspection
            inspection.establishment_id = est_id
            inspection.file_hash = file_hash
            inspection.status = InspectionStatus.PENDING_MANAGER_REVIEW
            inspection.ai_raw_response = report_data.model_dump()
            
            session.flush()
            logger.info(f"✅ Inspection {inspection.id} updated/created")
            
            # Action Plan (Upsert)
            action_plan = session.query(ActionPlan).filter_by(inspection_id=inspection.id).first()
            if not action_plan:
                action_plan = ActionPlan(inspection_id=inspection.id)
                session.add(action_plan)
                logger.info("🆕 ActionPlan created")
                
            # action_plan.final_pdf_public_link = output_link # REMOVED (Field Deleted)
            if output_link:
                pass # Logic related to link moved/removed
            
            # Enrich Action Plan Fields
            action_plan.summary_text = report_data.resumo_geral
            action_plan.strengths_text = report_data.pontos_fortes or ""
            
            # Calculate Stats (Total Items, NCs, By Sector)
            total_items = 0
            total_nc = 0
            sector_stats = {}
            
            # Clear old items (if re-processing)
            deleted_count = session.query(ActionPlanItem).filter_by(action_plan_id=action_plan.id).delete()
            logger.info(f"🗑️ Deleted {deleted_count} old items")
            
            # ITERATE AREAS (The User's Nested Structure)
            logger.info(f"🔍 Iterating {len(report_data.areas_inspecionadas)} areas")
            for area in report_data.areas_inspecionadas:
                area_nc_count = 0
                logger.info(f"  📂 Area: {area.nome_area} ({len(area.itens)} items)")
                for idx, item in enumerate(area.itens):
                    total_items += 1
                    
                    is_nc = "não conforme" in item.status.lower() or "parcialmente" in item.status.lower()
                    status_db = ActionPlanItemStatus.OPEN if is_nc else ActionPlanItemStatus.RESOLVED
                    
                    if is_nc:
                        total_nc += 1
                        area_nc_count += 1
                    
                    # Determine Severity (Default based on logic or Prompt could give it)
                    severity = SeverityLevel.HIGH if is_nc else SeverityLevel.LOW
                    
                    db_item = ActionPlanItem(
                        id=uuid.uuid4(),
                        action_plan=action_plan,
                        problem_description=item.observacao,
                        sector=area.nome_area, # VITAL: Use Area Name as Sector
                        severity=severity,
                        status=status_db,
                        
                        # [V16] Persist AI Metadata
                        # [V16] Persist AI Metadata
                        original_status=item.status,
                        original_score=getattr(item, 'pontuacao', 0) or 0.0, # Force 0.0 if None

                        legal_basis=item.fundamento_legal,
                        corrective_action=item.acao_corretiva_sugerida,
                        ai_suggested_deadline=item.prazo_sugerido,
                        order_index=idx # Persist sorting order
                    )
                    session.add(db_item)
                
                sector_stats[area.nome_area] = {
                    "nc_count": area_nc_count,
                    "resumo_area": area.resumo_area,
                    "pontuacao": area.pontuacao_obtida,
                    "maximo": area.pontuacao_maxima,
                    "aproveitamento": area.aproveitamento
                }
            
            # Save Stats to JSON (recalculate percentage from actual scores)
            score = report_data.pontuacao_geral
            max_score = report_data.pontuacao_maxima_geral
            pct = round((score / max_score * 100), 2) if max_score > 0 else 0

            action_plan.stats_json = {
                "total_items": total_items,
                "total_nc": total_nc,
                "score": score,
                "max_score": max_score,
                "percentage": pct,
                "by_sector": sector_stats
            }
            logger.info(f"📊 Stats generated: {total_items} items, {total_nc} NCs")
            
            session.commit()
            logger.info("✅ DB Save Success (ChecklistSanitario Structure)")
            
        except Exception as e:
            logger.error(f"DB Save Error: {e}")
            session.rollback()
            raise e

# Instantiate Singleton
try:
    processor_service = ProcessorService()
except Exception as e:
    logger.error(f"Failed to instantiate ProcessorService: {e}")
    processor_service = None
