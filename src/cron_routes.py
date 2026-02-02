
from flask import Blueprint, jsonify, request, current_app
import logging
from src.database import get_db
from src.models_db import Inspection, Job, JobStatus, InspectionStatus
from datetime import datetime
import os
from src.config_helper import get_config

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
    valid_secret = get_config('WEBHOOK_SECRET_TOKEN')
    
    if not is_cron and (not secret or secret != valid_secret):
        return jsonify({'error': 'Unauthorized'}), 401

    drive = current_app.drive_service
    
    from src.services.sync_service import perform_drive_sync
    result = perform_drive_sync(drive, limit=5, user_trigger=False)
    
    status_code = 500 if 'error' in result and result.get('status') != 'ok' else 200
    return jsonify(result), status_code
