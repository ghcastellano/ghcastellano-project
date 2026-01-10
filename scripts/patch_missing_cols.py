
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

def fix_missing_cols():
    with engine.connect() as conn:
        print("🔄 Patching Schema for missing columns...")
        
        try:
            # Add evidence_image_url to action_plan_items
            conn.execute(text("ALTER TABLE action_plan_items ADD COLUMN IF NOT EXISTS evidence_image_url VARCHAR;"))
            print("✅ 'evidence_image_url' column checked/added.")
        except Exception as e:
            print(f"⚠️ Error adding evidence_image_url: {e}")
            
        conn.commit()
        print("🚀 Schema Patch Completed.")

if __name__ == "__main__":
    fix_missing_cols()
