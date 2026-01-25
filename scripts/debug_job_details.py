
import sys
import os
from dotenv import load_dotenv
from sqlalchemy import text

load_dotenv()
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src import database
from src.models_db import Job, JobStatus, Inspection

def check_job_for_file(file_id):
    db = next(database.get_db())
    try:
        print(f"🔍 Checking Job for File ID: {file_id}")
        
        # Find Inspection
        insp = db.query(Inspection).filter(Inspection.drive_file_id == file_id).first()
        if insp:
            print(f"📄 Inspection Found: {insp.id}")
            print(f"   Status: {insp.status}")
            print(f"   AI Response: {insp.ai_raw_response}")
        else:
            print("❌ Inspection NOT found.")
            
        # Find Job via Payload
        # We search inside JSONB. 
        # Note: input_payload->>'file_id' = file_id
        jobs = db.query(Job).filter(Job.input_payload['file_id'].astext == file_id).all()
        
        if not jobs:
            print("❌ No Jobs found for this file.")
        
        for job in jobs:
            print("-" * 30)
            print(f"⚙️ Job ID: {job.id}")
            print(f"   Status: {job.status}")
            print(f"   Error Log: {job.error_log}")
            print(f"   Result Payload: {job.result_payload}")
            print(f"   Input Payload: {job.input_payload}")

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    # File ID from previous debug output
    check_job_for_file('1i5SRRUywoyRzrMTDukTd4ROgk1PeiHII')
