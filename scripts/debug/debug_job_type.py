
import sys
import os
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src import database
from src.models_db import Job

def check_job_type(job_id):
    db = next(database.get_db())
    try:
        j = db.query(Job).get(job_id)
        if j:
            print(f"ID: {j.id}")
            print(f"Type: '{j.type}'")
            print(f"Status: '{j.status}'")
        else:
            print("Job Not Found")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_job_type('ba06ed16-726e-4dae-9695-475aa887490f')
