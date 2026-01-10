
import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load env
load_dotenv()

# Setup
db_url = os.getenv("DATABASE_URL")
if not db_url:
    print("❌ DATABASE_URL not found")
    sys.exit(1)

if "neondb" in db_url and "sslmode" not in db_url:
    db_url += "?sslmode=require"

engine = create_engine(db_url)

def clear_test_data():
    target_hash = "6392878f080738a101caf6061a63b760" # Hash from logs
    
    with engine.connect() as conn:
        print(f"🔄 Clearing test data for hash: {target_hash}")
        
        # We need to delete ActionPlans first due to FK, then Inspection
        # Find Inspection ID first
        result = conn.execute(text("SELECT id FROM inspections WHERE file_hash = :hash"), {"hash": target_hash}).fetchone()
        
        if result:
            insp_id = result[0]
            print(f"Found Inspection ID: {insp_id}")
            
            # Delete Action Plan Items
            conn.execute(text("DELETE FROM action_plan_items WHERE action_plan_id IN (SELECT id FROM action_plans WHERE inspection_id = :id)"), {"id": insp_id})
            
            # Delete Action Plans
            conn.execute(text("DELETE FROM action_plans WHERE inspection_id = :id"), {"id": insp_id})
            
            # Delete Inspection
            conn.execute(text("DELETE FROM inspections WHERE id = :id"), {"id": insp_id})
            
            print("✅ Test data cleared.")
        else:
            print("⚠️ No inspection found with that hash.")
            
        conn.commit()

if __name__ == "__main__":
    clear_test_data()
