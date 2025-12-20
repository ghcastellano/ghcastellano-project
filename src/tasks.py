
import os
import json
import logging
from google.cloud import tasks_v2
from datetime import datetime
import uuid

logger = logging.getLogger("tasks")

class TaskManager:
    def __init__(self):
        self.project = os.getenv("GCP_PROJECT_ID")
        self.location = os.getenv("GCP_LOCATION")
        self.queue = os.getenv("GCP_TASK_QUEUE", "mvp-worker-queue")
        
        # Initialize Client only if GCP vars are present to allow local dev mocking
        if self.project and self.location:
            try:
                self.client = tasks_v2.CloudTasksClient()
                self.parent = self.client.queue_path(self.project, self.location, self.queue)
                logger.info(f"✅ Cloud Tasks Initialized: {self.parent}")
            except Exception as e:
                logger.error(f"⚠️ Failed to init Cloud Tasks: {e}")
                self.client = None
        else:
            self.client = None
            logger.warning("⚠️ GCP_PROJECT_ID or GCP_LOCATION missing. TaskManager in Mock Mode.")

    def enqueue_job(self, job_id: str, payload: dict, url_path: str = "/worker/process"):
        """
        Enqueues a task to the Cloud Tasks queue.
        Target: The service's own URL (Worker handler).
        """
        if not self.client:
            logger.info(f"🔒 [MOCK] Enqueue Job {job_id} to {url_path}: {payload}")
            return True

        task = {
            "http_request": {  # Specify the type of request.
                "http_method": tasks_v2.HttpMethod.POST,
                "url": f"{os.getenv('APP_PUBLIC_URL')}{url_path}",  # Absolute URL required
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"job_id": str(job_id), **payload}).encode(),
            }
        }
        
        # Add OIDC token if Service-to-Service auth is needed (Recommended)
        # For MVP we might rely on allow-unauthenticated or internal checking
        # task["http_request"]["oidc_token"] = {"service_account_email": os.getenv("SERVICE_ACCOUNT_EMAIL")}

        try:
            response = self.client.create_task(request={"parent": self.parent, "task": task})
            logger.info(f"🚀 Task enqueued: {response.name}")
            return True
        except Exception as e:
            logger.error(f"❌ Error enqueueing task: {e}")
            return False

task_manager = TaskManager()
