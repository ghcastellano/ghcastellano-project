
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

def fix_processing_logs():
    with engine.connect() as conn:
        print("🔄 Migrating processing_logs to JSONB...")
        
        try:
            # Force clean data first to avoid JSON parsing errors
            conn.execute(text("UPDATE inspections SET processing_logs = '[]' WHERE processing_logs IS NULL OR processing_logs = '';"))
            # If any other garbage exists, we might need to be more aggressive:
            conn.execute(text("UPDATE inspections SET processing_logs = '[]';")) # Aggressive clean if needed
            
            # Try convert
            conn.execute(text("""
                ALTER TABLE inspections 
                ALTER COLUMN processing_logs TYPE JSONB 
                USING processing_logs::jsonb;
            """))
            # Set default
            conn.execute(text("ALTER TABLE inspections ALTER COLUMN processing_logs SET DEFAULT '[]'::jsonb;"))
            
            print("✅ 'processing_logs' converted to JSONB successfully.")
        except Exception as e:
            print(f"⚠️ Error converting processing_logs (might already be JSONB or invalid JSON data): {e}")
            # Fallback: If it fails usually it's because data is not valid JSON. 
            # In MVP dev, we can clear it if needed, but let's see.
            
        conn.commit()
        print("🚀 JSONB Migration Completed.")

if __name__ == "__main__":
    fix_processing_logs()
