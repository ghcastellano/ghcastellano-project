
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
        FOLDER_IN = config.FOLDER_ID_01_ENTRADA_RELATORIOS
        
        # 1. List Files
        files = drive_service.list_files(FOLDER_IN, extension='.pdf')
        logger.info(f"🔄 [SYNC] Found {len(files)} files. Trigger: {'User' if user_trigger else 'Cron'}")

        # 2. Filter New
        processed_file_ids = [r[0] for r in db.query(Inspection.drive_file_id).all()]
        
        files_to_process = []
        for f in files:
            if f['id'] not in processed_file_ids:
                files_to_process.append(f)
                if len(files_to_process) >= limit: 
                    break
        
        if not files_to_process:
            return {'status': 'ok', 'message': 'No new files.', 'processed': 0}

        # 3. Process
        from src.services.processor import processor_service
        
        for file in files_to_process:
            logger.info(f"⏳ [SYNC] Processing: {file['name']}")
            try:
                # Job
                job = Job(
                    type="SYNC_PROCESS",
                    status=JobStatus.PENDING,
                    input_payload={
                        'file_id': file['id'], 
                        'filename': file['name'], 
                        'source': 'admin_sync' if user_trigger else 'cron_scheduler'
                    }
                )
                db.add(job)
                
                # Inspection
                new_insp = Inspection(
                    drive_file_id=file['id'], 
                    drive_web_link=file.get('webViewLink'), 
                    status=InspectionStatus.PROCESSING
                )
                db.add(new_insp)
                db.commit()

                # Process
                processor_service.process_single_file({'id': file['id'], 'name': file['name']}, job=job)
                
                job.status = JobStatus.COMPLETED
                job.finished_at = datetime.utcnow()
                db.commit()
                processed_count += 1
            except Exception as e:
                msg = f"Error {file['name']}: {e}"
                logger.error(f"❌ {msg}")
                errors.append(msg)
                if 'job' in locals() and job:
                    job.status = JobStatus.FAILED
                    job.error_log = str(e)
                    db.commit()

        return {'status': 'success', 'processed': processed_count, 'errors': errors}

    except Exception as e:
        logger.error(f"❌ Sync Fatal Error: {e}")
        return {'error': str(e)}
    finally:
        db.close()
