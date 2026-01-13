import sys
import os

# Manual .env loader (since running isolated)
# Simple parser for KEY=VALUE
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
if os.path.exists(env_path):
    print(f"Loading .env from {env_path}")
    with open(env_path) as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                k, v = line.strip().split('=', 1)
                # Strip potential quotes
                v = v.strip("'").strip('"')
                os.environ[k] = v

# Add project root to path (parent of 'scripts')
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Also add 'src' directly if needed? No, usually root is enough if we import src.database
# But let's be safe and check if we need to add '.'
# Actually, the previous logic was: os.path.dirname(os.path.dirname(...)) -> Root
# 'from src.database' works if Root is in path.

from src import database
from src.database import init_db
from src.models_db import Inspection, ActionPlan, ActionPlanItem, Job, Visit, InspectionStatus
from sqlalchemy import text

def reset_data():
    # Access db_session from the module to see the updated value after init_db()
    if not database.db_session:
        print("❌ Error: Database session not initialized.")
        return
        
    session = database.db_session()
    try:
        print("⚠️  WARNING: This will DELETE all Inspections, Action Plans, and Jobs.")
        print("    Users, Companies, and Establishments will be PRESERVED.")
        
        # 1. Delete Action Plan Items (Cascade usually handles this, but being explicit)
        deleted_items = session.query(ActionPlanItem).delete()
        print(f"✅ Deleted {deleted_items} Action Plan Items")
        
        # 2. Delete Action Plans
        deleted_plans = session.query(ActionPlan).delete()
        print(f"✅ Deleted {deleted_plans} Action Plans")
        
        # 3. Delete Inspections
        deleted_inspections = session.query(Inspection).delete()
        print(f"✅ Deleted {deleted_inspections} Inspections")
        
        # 4. Delete Jobs (Background tasks)
        deleted_jobs = session.query(Job).delete()
        print(f"✅ Deleted {deleted_jobs} Jobs")
        
        # 5. Delete Visits (If requested, optional)
        # deleted_visits = session.query(Visit).delete()
        # print(f"✅ Deleted {deleted_visits} Visits")

        session.commit()
        print("\n🎉 Database Cleanup Complete! ready for fresh tests.")
        
    except Exception as e:
        session.rollback()
        print(f"❌ Error during cleanup: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    init_db()
    reset_data()
