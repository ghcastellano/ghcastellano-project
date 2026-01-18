import sys
import os
sys.path.append(os.getcwd())
from src.app import app
from src.database import db_session
from src.models_db import Job, JobStatus
from sqlalchemy import text

def fail_stuck_job():
    with app.app_context():
        # Find the stuck job
        job = db_session.query(Job).filter(text("input_payload->>'filename' LIKE '%quest_resposta (1).pdf%'")).first()
        
        if job:
            print(f"Marking Job {job.id} as FAILED...")
            job.status = JobStatus.FAILED
            job.message = "Processamento travado (timeout manual). Por favor envie novamente."
            db_session.commit()
            print("Job marked as FAILED.")
        else:
            print("Job not found.")

if __name__ == '__main__':
    fail_stuck_job()
