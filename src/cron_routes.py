
from flask import Blueprint, jsonify, request, current_app
import logging
from src.database import get_db
from src.models_db import Inspection, Job, JobStatus, InspectionStatus, AppConfig
from datetime import datetime
import os
from src.config_helper import get_config

cron_bp = Blueprint('cron', __name__)


def _check_cron_auth():
    """Shared auth check for cron endpoints."""
    is_cron = request.headers.get('X-Appengine-Cron') == 'true'
    secret = request.args.get('secret')
    valid_secret = get_config('WEBHOOK_SECRET_TOKEN')
    return is_cron or (secret and secret == valid_secret)


@cron_bp.route('/api/cron/sync_drive', methods=['GET', 'POST'])
def cron_sync_drive():
    """
    WORKERLESS SYNC: Scheduled by Cloud Scheduler (e.g., every 15 min).
    """
    logger = logging.getLogger('cron_sync')

    if not _check_cron_auth():
        return jsonify({'error': 'Unauthorized'}), 401

    drive = current_app.drive_service

    from src.services.sync_service import perform_drive_sync
    result = perform_drive_sync(drive, limit=5, user_trigger=False)

    status_code = 500 if 'error' in result and result.get('status') != 'ok' else 200
    return jsonify(result), status_code


@cron_bp.route('/api/cron/renew_webhook', methods=['GET', 'POST'])
def cron_renew_webhook():
    """
    Auto-renew Drive webhook channel.
    Schedule via Cloud Scheduler every 6 days (channels expire in ~7 days).
    Checks expiration before renewing to avoid unnecessary API calls.
    """
    logger = logging.getLogger('cron_webhook')

    if not _check_cron_auth():
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        db_session = next(get_db())

        # Check if current channel is still valid (>24h remaining)
        expiration_entry = db_session.query(AppConfig).get('drive_webhook_expiration')
        if expiration_entry and expiration_entry.value:
            try:
                exp_ms = int(expiration_entry.value)
                now_ms = int(datetime.utcnow().timestamp() * 1000)
                remaining_hours = (exp_ms - now_ms) / (1000 * 3600)
                if remaining_hours > 24:
                    logger.info(f"Webhook channel still valid ({remaining_hours:.0f}h remaining), skipping renewal")
                    db_session.close()
                    return jsonify({'status': 'ok', 'action': 'skipped', 'remaining_hours': round(remaining_hours)}), 200
            except (ValueError, TypeError):
                pass

        db_session.close()

        # Call the renew endpoint internally
        with current_app.test_request_context('/api/webhook/renew', method='POST'):
            from src.app import renew_webhook
            response = renew_webhook()
            # renew_webhook returns a tuple (response, status_code)
            if isinstance(response, tuple):
                resp_data, status_code = response
            else:
                resp_data, status_code = response, 200

            logger.info(f"Webhook auto-renewal result: {status_code}")
            return resp_data, status_code

    except Exception as e:
        logger.error(f"Cron webhook renewal failed: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
