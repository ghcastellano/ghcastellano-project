
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv()

from src import database
from src.models_db import Inspection, Job, User, Establishment
from sqlalchemy.orm import joinedload

def debug_db():
    session = next(database.get_db())
    try:
        print("\n--- Users (Consultants) ---")
        consultants = session.query(User).filter_by(role='CONSULTANT').all()
        for c in consultants:
            est_names = [e.name for e in c.establishments]
            print(f"User: {c.email} (ID: {c.id}) | Company: {c.company_id} | Ests: {est_names}")

        print("\n--- Inspections (Last 10) ---")
        insps = session.query(Inspection).options(joinedload(Inspection.establishment)).order_by(Inspection.created_at.desc()).limit(100).all()
        for i in insps:
            est_name = i.establishment.name if i.establishment else "NULL"
            est_id = i.establishment.id if i.establishment else "NULL"
            print(f"Insp ID: {i.id} | Status: {i.status} | Est: {est_name} ({est_id}) | File: {i.drive_file_id}")

    finally:
        session.close()

if __name__ == "__main__":
    debug_db()
