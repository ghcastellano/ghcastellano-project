
import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Adiciona o diretório raiz ao PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import text
import src.database as database

def migrate():
    print("🚀 Starting V17 Flow Migration...")
    database.init_db() # Initialize DB connection
    
    with database.engine.connect() as conn:
        trans = conn.begin()
        try:
            # 1. Update/Add Columns using raw SQL (quickest for MVP without Alembic)
            
            # ActionPlan: final_pdf_url
            print("Checking action_plans.final_pdf_url...")
            try:
                conn.execute(text("ALTER TABLE action_plans ADD COLUMN IF NOT EXISTS final_pdf_url VARCHAR;"))
                print("✅ Added final_pdf_url to action_plans")
            except Exception as e:
                print(f"⚠️ final_pdf_url might already exist: {e}")

            # ActionPlanItem: current_status
            print("Checking action_plan_items.current_status...")
            try:
                conn.execute(text("ALTER TABLE action_plan_items ADD COLUMN IF NOT EXISTS current_status VARCHAR;"))
                print("✅ Added current_status to action_plan_items")
            except Exception as e:
                print(f"⚠️ current_status might already exist: {e}")
            
            # 2. Data Migration: WAITING_APPROVAL -> PENDING_MANAGER_REVIEW
            print("Migrating Inspection Status...")
            # Note: Postgres Enum types are tricky. `WAITING_APPROVAL` might still be in the enum type definition.
            # We first update the values in the table.
            
            result = conn.execute(text("UPDATE inspections SET status = 'PENDING_MANAGER_REVIEW' WHERE status = 'WAITING_APPROVAL';"))
            print(f"✅ Updated {result.rowcount} inspections from WAITING_APPROVAL to PENDING_MANAGER_REVIEW")
            
            # Also update any PENDING_VERIFICATION to PENDING_CONSULTANT_VERIFICATION if it existed (unlikely but safe)
            # result = conn.execute(text("UPDATE inspections SET status = 'PENDING_CONSULTANT_VERIFICATION' WHERE status = 'PENDING_VERIFICATION';"))
            
            # 3. Enum Migration (This is tricky in SQLAlchemy/Postgres)
            # If we defined the Enum in python, SQLAlchemy uses it.
            # In Postgres, the type 'inspectionstatus' exists.
            # We need to ADD the new value 'PENDING_CONSULTANT_VERIFICATION' to the enum type in PG.
            
            try:
                conn.execute(text("ALTER TYPE inspectionstatus ADD VALUE IF NOT EXISTS 'PENDING_CONSULTANT_VERIFICATION';"))
                print("✅ Added 'PENDING_CONSULTANT_VERIFICATION' to inspectionstatus enum")
            except Exception as e:
                print(f"⚠️ PENDING_CONSULTANT_VERIFICATION might already exist in enum: {e}")
                
            trans.commit()
            print("🎉 Migration Completed Successfully!")
            
        except Exception as e:
            trans.rollback()
            print(f"❌ Migration Failed: {e}")
            raise e

if __name__ == "__main__":
    migrate()
