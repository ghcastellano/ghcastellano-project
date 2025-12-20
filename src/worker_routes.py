from flask import Blueprint, request, jsonify
import logging
from src import database
from src.models_db import Job, JobStatus
from src.services.job_processor import job_processor

logger = logging.getLogger("worker")

worker_bp = Blueprint('worker', __name__)

@worker_bp.route('/process', methods=['POST'])
def process_task():
    """
    Endpoint called by Cloud Tasks (or manually for testing).
    Payload must contain 'job_id'.
    """
    data = request.get_json(silent=True)
    if not data or 'job_id' not in data:
        logger.error("❌ Worker received invalid payload (missing job_id)")
        return jsonify({"error": "Missing job_id"}), 400

    job_id = data['job_id']
    logger.info(f"📨 Worker received Task for Job {job_id}")

    try:
        # Fetch Job
        job = database.db_session.query(Job).get(job_id)
        if not job:
            logger.error(f"❌ Job {job_id} not found in DB.")
            return jsonify({"error": "Job not found"}), 404

        # Idempotency / Status Check
        if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELED]:
            logger.warning(f"⚠️ Job {job_id} already in final state: {job.status}. Skipping.")
            return jsonify({"status": "Already Processed"}), 200

        # Update to PROCESSING
        job.status = JobStatus.PROCESSING
        database.db_session.commit()

        # Execute Logic
        job_processor.process_job(job)

        return jsonify({"status": "Processed", "final_status": job.status}), 200

    except Exception as e:
        logger.error(f"❌ Worker Internal Error: {e}")
        return jsonify({"error": str(e)}), 500
