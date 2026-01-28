import sys
import os
sys.path.append(os.getcwd())
from src.app import app
from src.database import db_session
from src.models_db import Inspection, Job, ActionPlan, ActionPlanItem
from sqlalchemy import text

def clear_all_data():
    with app.app_context():
        print("--- CLEARING DATABASE ---")
        try:
            # Delete in order of dependencies (Child -> Parent)
            
            # 1. Action Plan Items
            print("Deleting Action Plan Items...")
            db_session.query(ActionPlanItem).delete()
            
            # 2. Action Plans
            print("Deleting Action Plans...")
            db_session.query(ActionPlan).delete()
            
            # 3. Inspections
            print("Deleting Inspections...")
            db_session.query(Inspection).delete()
            
            # 4. Jobs (Processing Logs)
            print("Deleting Jobs...")
            db_session.query(Job).delete()
            
            # Visits table removed from models 
            
            db_session.commit()
            print("✅ All inspection data cleared successfully.")
            
        except Exception as e:
            db_session.rollback()
            print(f"❌ Error clearing data: {e}")

if __name__ == '__main__':
    clear_all_data()
