import os
import json
import logging
from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2
import datetime

logger = logging.getLogger("cloud_tasks")

class CloudTasksService:
    def __init__(self):
        self.project = os.getenv("GCP_PROJECT_ID")
        self.location = os.getenv("GCP_LOCATION", "us-central1")
        self.queue = os.getenv("CLOUD_TASKS_QUEUE", "mvp-tasks")
        self.public_url = os.getenv("APP_PUBLIC_URL")
        self.client = None

    def _get_client(self):
        if not self.client:
            self.client = tasks_v2.CloudTasksClient()
        return self.client

    def create_http_task(self, payload: dict, in_seconds: int = None):
        """
        Creates a task for the Cloud Run Worker endpoint.
        Target URL: {APP_PUBLIC_URL}/worker/process
        """
        if not self.project or not self.public_url:
            logger.warning("Cloud Tasks skipped: GCP_PROJECT_ID or APP_PUBLIC_URL not set.")
            return None

        client = self._get_client()
        parent = client.queue_path(self.project, self.location, self.queue)
        
        url = f"{self.public_url}/worker/process"
        
        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": url,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(payload).encode(),
                "oidc_token": {
                    "service_account_email": os.getenv("GCP_SA_EMAIL")
                }
            }
        }

        if in_seconds:
            d = datetime.datetime.utcnow() + datetime.timedelta(seconds=in_seconds)
            timestamp = timestamp_pb2.Timestamp()
            timestamp.FromDatetime(d)
            task["schedule_time"] = timestamp

        try:
            response = client.create_task(request={"parent": parent, "task": task})
            logger.info(f"🚀 Task created: {response.name}")
            return response.name
        except Exception as e:
            logger.error(f"❌ Failed to create Cloud Task: {e}")
            raise e

cloud_tasks_service = CloudTasksService()
