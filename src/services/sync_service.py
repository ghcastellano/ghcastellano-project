
import logging
from datetime import datetime
from src.database import get_db
from src.models_db import Job, JobStatus, Inspection, InspectionStatus
from src.config_helper import get_config

logger = logging.getLogger('sync_service')


def process_global_changes(drive_service):
    """
    Processa mudanças globais do Drive (Changes API).
    Identifica arquivos criados nas pastas de Lojas conhecidas.
    Inclui Zombie Killer para auto-recovery de jobs/inspeções travadas.
    """
    if not drive_service:
        return {'error': 'Drive Service unavailable'}

    db = next(get_db())
    logger.info("🌍 [GLOBAL SYNC] Checking for Drive changes...")

    try:
        from src.models_db import AppConfig, Establishment, Job, JobStatus, Inspection, InspectionStatus
        from src.services.processor import processor_service
        from datetime import timedelta

        # 0. Zombie Killer: Fail stuck jobs (Auto-Recovery)
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

            stuck_inspections = db.query(Inspection).filter(
                Inspection.status == InspectionStatus.PROCESSING,
                Inspection.created_at < cutoff
            ).all()

            if stuck_inspections:
                logger.warning(f"🧟 [ZOMBIE KILLER] Found {len(stuck_inspections)} stuck INSPECTIONS. Marking as REJECTED.")
                for z_insp in stuck_inspections:
                    z_insp.status = InspectionStatus.REJECTED

            db.commit()
        except Exception as z_err:
            logger.error(f"Zombie Killer Error: {z_err}")

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
               
                # Create Job & Inspection
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
                    result = processor_service.process_single_file(
                        {'id': file['id'], 'name': file['name']},
                        job_id=job_id_saved,
                        establishment_id=establishment_id
                    )

                    # Cleanup: If processor skipped (duplicate), mark as REJECTED to prevent retry
                    if result and result.get('status') == 'skipped':
                        logger.info(f"🔒 Webhook processor skipped {file['id']}, marking as REJECTED.")
                        orphan = db.query(Inspection).filter_by(drive_file_id=file['id'], status=InspectionStatus.PROCESSING).first()
                        if orphan:
                            orphan.status = InspectionStatus.REJECTED
                            db.commit()

                        # Move SKIPPED files to backup folder
                        backup_folder = get_config('FOLDER_ID_03_PROCESSADOS_BACKUP')
                        if backup_folder:
                            try:
                                drive_service.move_file(file['id'], backup_folder)
                                logger.info(f"📦 Arquivo duplicado movido para backup: {file.get('name')}")
                            except Exception as move_e:
                                logger.warning(f"⚠️ Falha ao mover duplicado {file.get('name')}: {move_e}")
                    else:
                        # Update job status to COMPLETED
                        try:
                            fresh_job = db.query(Job).get(job_id_saved)
                            if fresh_job:
                                fresh_job.status = JobStatus.COMPLETED
                                fresh_job.finished_at = datetime.utcnow()
                                fresh_job.execution_time_seconds = (fresh_job.finished_at - fresh_job.created_at.replace(tzinfo=None)).total_seconds()
                                fresh_job.attempts = (fresh_job.attempts or 0) + 1
                                db.commit()
                        except Exception as job_err:
                            logger.warning(f"⚠️ Falha ao atualizar job {job_id_saved}: {job_err}")

                        # Mover arquivo processado para pasta de backup (evita reprocessamento)
                        backup_folder = get_config('FOLDER_ID_03_PROCESSADOS_BACKUP')
                        if backup_folder:
                            try:
                                drive_service.move_file(file['id'], backup_folder)
                                logger.info(f"      📦 Arquivo movido para backup: {file.get('name')}")
                            except Exception as move_e:
                                logger.warning(f"      ⚠️ Falha ao mover {file.get('name')} para backup: {move_e}")

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
