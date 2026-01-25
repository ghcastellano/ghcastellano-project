
import sys
import os
from dotenv import load_dotenv
import json

load_dotenv()
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src import database
from src.models_db import Inspection

def check_logs(insp_id):
    db = next(database.get_db())
    try:
        i = db.query(Inspection).get(insp_id)
        if i:
             print(json.dumps(i.processing_logs, indent=2, default=str))
        else:
             print("Not found")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_logs('3112572d-c164-4eeb-b511-f6b9967f2d15')
