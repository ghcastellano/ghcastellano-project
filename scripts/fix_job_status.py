import sys
import os
sys.path.append(os.getcwd())

from dotenv import load_dotenv
load_dotenv()

from src import database
from src.database import init_db
from src.models_db import Job, JobStatus

def fix_job_status():
    init_db()
    db_session = database.db_session
    
    # Update PENDING jobs to COMPLETED
    jobs = db_session.query(Job).filter(Job.status == JobStatus.PENDING).all()
    count = 0
    for job in jobs:
        print(f"Fixing Job {job.id}...")
        job.status = JobStatus.COMPLETED
        job.result = {"message": "Forced completion via debugger"} # Adjust field name if needed
        count += 1
    
    if count > 0:
        db_session.commit()
        print(f"✅ Fixed {count} jobs.")
    else:
        print("No PENDING jobs found.")

if __name__ == "__main__":
    fix_job_status()
