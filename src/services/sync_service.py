
import logging
from datetime import datetime
from src.database import get_db
from src.models_db import Job, JobStatus, Inspection, InspectionStatus

logger = logging.getLogger('sync_service')

def perform_drive_sync(drive_service, limit=5, user_trigger=False):
    """
    Core synchronization logic.
    Returns dict with stats: {'processed': int, 'errors': list}
    """
    if not drive_service:
        return {'error': 'Drive Service unavailable'}

    db = next(get_db())
    processed_count = 0
    errors = []

    try:
        from src.config import config
        from src.models_db import Establishment, Company
        from datetime import datetime, timedelta

        # 0. Zombie Killer: Fail stuck jobs (Auto-Recovery)
        # Identifies jobs stuck in PROCESSING for > 30 minutes (likely crashed/timeout)
        try:
            cutoff = datetime.utcnow() - timedelta(minutes=30)
            stuck_jobs = db.query(Job).filter(
                Job.status == JobStatus.PROCESSING,
                Job.created_at < cutoff
            ).all()
            
            if stuck_jobs:
                logger.warning(f"🧟 [ZOMBIE KILLER] Found {len(stuck_jobs)} stuck jobs. Marking as FAILED.")
                for z_job in stuck_jobs:
                    z_job.status = JobStatus.FAILED
                    z_job.result_details = {'error': 'Processamento interrompido (Timeout/Crash detectado)'}
                    z_job.result_details = {'error': 'Processamento interrompido (Timeout/Crash detectado)'}
                    
                    # Also update Inspection status if linked
                    # Assuming Job.inspection_id exists or linked via meta. 
                    # If not direct link, we try to find via created_at approximation or if Job has 'resource_id'
                    # Checking Job model... It usually has a relationship.
                    # Let's try to update inspection if we can find it.
                    # For MVP, mostly we care about the Job status for metrics, but Inspection status drives the UI.
                    
                    # Try to find inspection created by this job (fuzzy match or if job stores it)
                    # Ideally Job table handles this.
                    # Fallback: Find PROCESSING inspections older than 30min and kill them too.
            
            # 0.1 Zombie Inspections Killer (The direct UI ghosts)
            cutoff_insp = datetime.utcnow() - timedelta(minutes=30)
            stuck_inspections = db.query(Inspection).filter(
                Inspection.status == InspectionStatus.PROCESSING,
                Inspection.created_at < cutoff_insp
            ).all()
            
            if stuck_inspections:
                 logger.warning(f"🧟 [ZOMBIE KILLER] Found {len(stuck_inspections)} stuck INSPECTIONS. Marking as FAILED.")
                 for z_insp in stuck_inspections:
                     z_insp.status = InspectionStatus.REJECTED # Or REJECTED if FAILED not in Enum
                     # z_insp.status_details = "Timeout/Crash" # If field exists
            
            db.commit()
        except Exception as z_err:
             logger.error(f"Zombie Killer Error: {z_err}")

        # 1. Prepare
        # Fetch ID and Status to allow retries on failure
        existing_inspections = {
            r[0]: r[1] 
            for r in db.query(Inspection.drive_file_id, Inspection.status).all()
        }
        files_to_process = [] # List of tuples: (file_meta, establishment_id)
        
        # 2. Hierarchy Scan: Iterate Establishments
        # Prioritize establishments with explicit folders
        establishments = db.query(Establishment).filter(Establishment.drive_folder_id != None).all()
        logger.info(f"🔍 [SYNC] Scanning {len(establishments)} Establishment Folders...")
        
        for est in establishments:
            if not est.drive_folder_id or est.drive_folder_id.strip() == "":
                continue
                
            est_files = drive_service.list_files(est.drive_folder_id, extension='.pdf')
            logger.info(f"   📂 [SYNC] Loja '{est.name}': {len(est_files)} arquivos encontrados.")
            
            for f in est_files:
                current_status = existing_inspections.get(f['id'])
                
                # Rule: Process if NEW or if existing FAILED/REJECTED
                should_process = False
                if current_status is None:
                    should_process = True
                elif current_status in [InspectionStatus.REJECTED, InspectionStatus.REJECTED]:
                    logger.info(f"      ♻️ Retrying FAILED file: {f['name']}")
                    should_process = True
                
                if should_process:
                    # Enqueue with Context
                    logger.info(f"      🆕 Enfileirando: {f['name']} ({f['id']})")
                    files_to_process.append((f, est.id))
                    if len(files_to_process) >= limit:
                        break
                else:
                    # Debug log for ignored files (only show first 3 to avoid spam)
                    pass 

            if len(files_to_process) >= limit:
                break

        # 3. Legacy Scan (Inbox Fallback) - If quota permits
        if len(files_to_process) < limit:
            FOLDER_IN = config.FOLDER_ID_01_ENTRADA_RELATORIOS
            if FOLDER_IN:
                legacy_files = drive_service.list_files(FOLDER_IN, extension='.pdf')
                for f in legacy_files:
                     # Check status for legacy files too
                     current_status = existing_inspections.get(f['id'])
                     should_process = False
                     if current_status is None:
                         should_process = True
                     elif current_status in [InspectionStatus.REJECTED, InspectionStatus.REJECTED]:
                         logger.info(f"      ♻️ Retrying FAILED legacy file: {f['name']}")
                         should_process = True

                     if should_process and not any(queued[0]['id'] == f['id'] for queued in files_to_process):
                         files_to_process.append((f, None)) # No Est ID linked
                         if len(files_to_process) >= limit:
                             break

        if not files_to_process:
            return {'status': 'ok', 'message': 'No new files.', 'processed': 0}

        # 4. Process Queue
        if files_to_process:
            logger.info(f"⚡ Processing {len(files_to_process)} prioritized files...")
            
            from src.services.processor import processor_service
            
            for file, est_id in files_to_process:
                job = None # Initialize job to None for error handling
                try:
                    # 4.1 Check & Clean Old Failed Record (Idempotency)
                    old_insp = db.query(Inspection).filter_by(drive_file_id=file['id']).first()
                    if old_insp:
                        logger.warning(f"      🧹 Cleaning up old record for {file['name']} before retry.")
                        db.delete(old_insp)
                        db.commit()

                    # 4.2 Resolve Context (Company ID)
                    company_id = None
                    est_obj = None
                    if est_id:
                        est_obj = db.query(Establishment).get(est_id)
                        if est_obj: company_id = est_obj.company_id

                    logger.info(f"⏳ [SYNC] Processing: {file['name']} (Est ID: {est_id})")
                    
                    # Job
                    job = Job(
                        type="SYNC_PROCESS",
                        status=JobStatus.PENDING,
                        input_payload={
                            'file_id': file['id'], 
                            'filename': file['name'], 
                            'source': 'admin_sync' if user_trigger else 'cron_scheduler',
                            'establishment_id': str(est_id) if est_id else None,
                            'company_name': est_obj.company.name if est_obj and est_obj.company else None
                        },
                        company_id=company_id
                    )
                    db.add(job)
                    db.commit() # Get Job ID

                    # Save IDs before processor detaches objects from session
                    job_id_saved = job.id

                    # Inspection (Pre-Create with Linked Est)
                    new_insp = Inspection(
                        drive_file_id=file['id'],
                        drive_web_link=file.get('webViewLink'),
                        status=InspectionStatus.PROCESSING,
                        establishment_id=est_id
                    )
                    db.add(new_insp)
                    db.commit()

                    # Process (processor uses its own sessions internally)
                    processor_service.process_single_file(
                        {'id': file['id'], 'name': file['name']},
                        job_id=job_id_saved,
                        establishment_id=est_id
                    )

                    # Re-fetch job in a fresh session (processor detaches our objects)
                    db_fresh = next(get_db())
                    try:
                        fresh_job = db_fresh.query(Job).get(job_id_saved)
                        if fresh_job:
                            fresh_job.status = JobStatus.COMPLETED
                            fresh_job.finished_at = datetime.utcnow()
                            fresh_job.execution_time_seconds = (fresh_job.finished_at - fresh_job.created_at.replace(tzinfo=None)).total_seconds()
                            fresh_job.attempts = (fresh_job.attempts or 0) + 1
                            db_fresh.commit()
                    finally:
                        db_fresh.close()

                    processed_count += 1
                except Exception as e:
                    msg = f"Error capturing {file['name']}: {str(e)}"
                    logger.error(msg)
                    errors.append(msg)
                    if job_id_saved:
                        try:
                            db_err = next(get_db())
                            err_job = db_err.query(Job).get(job_id_saved)
                            if err_job:
                                err_job.status = JobStatus.FAILED
                                err_job.result_details = {'error': msg}
                                db_err.commit()
                            db_err.close()
                        except Exception:
                            logger.error(f"Failed to update job status for {job_id_saved}")

        return {'status': 'ok', 'processed': processed_count, 'errors': errors}

    except Exception as e:
        logger.error(f"Global Sync Error: {e}", exc_info=True)
        return {'error': str(e)}
    finally:
        db.close()

def process_global_changes(drive_service):
    """
    Processa mudanças globais do Drive (Changes API).
    Identifica arquivos criados nas pastas de Lojas conhecidas.
    """
    if not drive_service:
        return {'error': 'Drive Service unavailable'}
        
    db = next(get_db())
    logger.info("🌍 [GLOBAL SYNC] Checking for Drive changes...")
    
    try:
        from src.models_db import AppConfig, Establishment, Job, JobStatus, Inspection, InspectionStatus
        from src.services.processor import processor_service
        
        # 1. Obter Token Atual
        config_token = db.query(AppConfig).get('drive_page_token')
        page_token = config_token.value if config_token else None
        
        # Se não tiver token, pega o start token (ignora passado) e SALVA.
        if not page_token:
            logger.info("🌍 [GLOBAL SYNC] No page token found. Fetching start token (ignoring history).")
            page_token = drive_service.get_start_page_token()
            if page_token:
                # Save Initial Token
                if not config_token:
                    db.add(AppConfig(key='drive_page_token', value=page_token))
                else:
                    config_token.value = page_token
                db.commit()
                return {'status': 'ok', 'message': 'Initialized Watch Token', 'processed': 0}
            else:
                return {'error': 'Failed to get start token'}

        # 2. Listar Mudanças
        changes, new_token = drive_service.list_changes(page_token)
        
        if not changes:
            logger.info("🌍 [GLOBAL SYNC] No changes found.")
            # Even if no changes, we might get a new token? usually only if changes exist or periodically.
            # But list_changes returns newStartPageToken if provided.
            # Update token anyway to keep fresh? logic says yes if new_token differs.
            if new_token and new_token != page_token:
                if not config_token:
                     db.add(AppConfig(key='drive_page_token', value=new_token))
                else:
                     config_token.value = new_token
                db.commit()
            return {'status': 'ok', 'processed': 0}

        # 3. Preparar Cache de Pastas (Map: FolderID -> EstID)
        # TODO: Otimizar para centenas de lojas? load all IDs is fine for now (<10k rows).
        all_est = db.query(Establishment).filter(Establishment.drive_folder_id != None).all()
        folder_map = {e.drive_folder_id: e.id for e in all_est}
        
        processed_file_ids = {r[0] for r in db.query(Inspection.drive_file_id).all()}
        
        processed_count = 0
        
        for change in changes:
            if change.get('removed'):
                continue
                
            file = change.get('file')
            if not file or file.get('mimeType') == 'application/vnd.google-apps.folder':
                continue
            
            # Check Parents
            parents = file.get('parents', [])
            establishment_id = None
            
            for parent_id in parents:
                if parent_id in folder_map:
                    establishment_id = folder_map[parent_id]
                    break
            
            # [NEW] Validação de Coerência Pasta-Documento
            # Verifica se arquivo JSON está na pasta correta antes de processar
            if file.get('name', '').endswith('.json'):
                try:
                    from src.services.document_validator import DocumentFolderValidator
                    validator = DocumentFolderValidator(drive_service, db)
                    validation_result = validator.validate_and_fix_location(file['id'], file)
                    
                    if validation_result.get('moved'):
                        # Arquivo foi movido! Atualizar establishment_id
                        logger.warning(f"📦 Arquivo movido para pasta correta: {validation_result.get('message')}")
                        validator.create_alert_for_manager(file, validation_result)
                        
                        # Re-buscar pasta correta após movimento
                        for parent_id in file.get('parents', []):
                            if parent_id in folder_map:
                                establishment_id  = folder_map[parent_id]
                                break
                except Exception as val_err:
                    logger.error(f"Erro na validação de pasta: {val_err}")
            
            # Se achou loja OU é da pasta legacy (se suportado), processa.
            # Aqui focamos apenas na HIERARQUIA para garantir o "Company Recognition".
            if establishment_id and file['id'] not in processed_file_ids:
                logger.info(f"✨ [GLOBAL SYNC] New File detected in Store Folder! StoreID: {establishment_id}, File: {file.get('name')}")
               
                # Create Job & Inspection (Similar logic to sync)
                # DRY: This block matches perform_drive_sync logic.
                job = Job(
                    type="WEBHOOK_PROCESS",
                    status=JobStatus.PENDING,
                    input_payload={
                        'file_id': file['id'], 
                        'filename': file['name'], 
                        'source': 'webhook_global',
                        'establishment_id': str(establishment_id)
                    }, 
                    company_id=None 
                )
                db.add(job)
                db.commit()

                # Save job_id before processor detaches objects
                job_id_saved = job.id

                new_insp = Inspection(
                    drive_file_id=file['id'],
                    drive_web_link=file.get('webViewLink'),
                    status=InspectionStatus.PROCESSING,
                    establishment_id=establishment_id
                )
                db.add(new_insp)
                db.commit()

                try:
                    processor_service.process_single_file(
                        {'id': file['id'], 'name': file['name']},
                        job_id=job_id_saved,
                        establishment_id=establishment_id
                    )
                    processed_count += 1
                except Exception as e:
                    logger.error(f"Error processing file {file['id']}: {e}")
        
        # 4. Save New Token
        if new_token:
            if not config_token:
                db.add(AppConfig(key='drive_page_token', value=new_token))
            else:
                config_token.value = new_token
            db.commit()
            
        return {'status': 'ok', 'processed': processed_count}
        
    except Exception as e:
        logger.error(f"Global Sync Logic Error: {e}", exc_info=True)
        return {'error': str(e)}
    finally:
        db.close()
