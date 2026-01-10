
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

def fix_schema():
    with engine.connect() as conn:
        print("🔄 Fixing Schema Columns...")
        
        # 1. Add updated_at if missing
        try:
            conn.execute(text("ALTER TABLE inspections ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();"))
            print("✅ 'updated_at' column checked/added.")
        except Exception as e:
            print(f"⚠️ Error adding updated_at: {e}")

        # 2. Add file_hash if missing
        try:
            conn.execute(text("ALTER TABLE inspections ADD COLUMN IF NOT EXISTS file_hash VARCHAR;"))
            # Index
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_inspections_file_hash ON inspections (file_hash);"))
            print("✅ 'file_hash' column checked/added.")
        except Exception as e:
            print(f"⚠️ Error adding file_hash: {e}")
            
        conn.commit()
        print("🚀 Schema Patch Completed.")

if __name__ == "__main__":
    fix_schema()
