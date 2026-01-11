
from flask import Blueprint, jsonify, request, current_app
import logging
from src.database import get_db
from src.models_db import Inspection, Job, JobStatus, InspectionStatus
from datetime import datetime
import os

cron_bp = Blueprint('cron', __name__)

@cron_bp.route('/api/cron/sync_drive', methods=['GET', 'POST'])
def cron_sync_drive():
    """
    WORKERLESS SYNC: Scheduled by Cloud Scheduler (e.g., every 15 min).
    """
    logger = logging.getLogger('cron_sync')
    
    # Check Auth
    is_cron = request.headers.get('X-Appengine-Cron') == 'true'
    secret = request.args.get('secret')
    valid_secret = os.getenv('WEBHOOK_SECRET_TOKEN')
    
    if not is_cron and (not secret or secret != valid_secret):
        return jsonify({'error': 'Unauthorized'}), 401

    drive = current_app.drive_service
    if not drive:
        return jsonify({'error': 'Drive Unavailable'}), 503

    db = next(get_db())
    processed_count = 0
    errors = []

    try:
        from src.config import config
        FOLDER_IN = config.FOLDER_ID_01_ENTRADA_RELATORIOS
        
        files = drive.list_files(FOLDER_IN, extension='.pdf')
        logger.info(f"🔄 [CRON] Found {len(files)} files.")

        processed_file_ids = [r[0] for r in db.query(Inspection.drive_file_id).all()]
        
        files_to_process = []
        for f in files:
            if f['id'] not in processed_file_ids:
                files_to_process.append(f)
                if len(files_to_process) >= 2: break
        
        if not files_to_process:
            return jsonify({'status': 'ok', 'message': 'No new files.'})

        from src.services.processor import processor_service
        
        for file in files_to_process:
            logger.info(f"⏳ Processing: {file['name']}")
            try:
                job = Job(type="CRON_SYNC_PROCESS", status=JobStatus.PENDING,
                          input_payload={'file_id': file['id'], 'filename': file['name'], 'source': 'drive_cron'})
                db.add(job)
                
                new_insp = Inspection(drive_file_id=file['id'], drive_web_link=file.get('webViewLink'), status=InspectionStatus.PROCESSING)
                db.add(new_insp)
                db.commit()

                processor_service.process_single_file({'id': file['id'], 'name': file['name']}, job=job)
                
                job.status = JobStatus.COMPLETED
                job.finished_at = datetime.utcnow()
                db.commit()
                processed_count += 1
            except Exception as e:
                logger.error(f"❌ Error {file['name']}: {e}")
                errors.append(f"{file['name']}: {e}")
                if 'job' in locals():
                    job.status = JobStatus.FAILED; job.error_log = str(e); db.commit()

        return jsonify({'status': 'success', 'processed': processed_count, 'errors': errors})

    except Exception as e:
        logger.error(f"❌ Cron Error: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()
