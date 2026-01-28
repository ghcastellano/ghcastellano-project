
import sys
import os
from sqlalchemy import text

# Add src to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import get_db

def fix_schema():
    print("🔧 Starting Schema Fix...")
    db_gen = get_db()
    db = next(db_gen)
    
    try:
        # 1. Check and Add 'processing_logs' to 'inspections'
        print("Checking 'inspections.processing_logs'...")
        try:
            db.execute(text("SELECT processing_logs FROM inspections LIMIT 1"))
            print("✅ Column 'processing_logs' already exists.")
        except Exception:
            db.rollback()
            print("⚠️ Column missing. Adding 'processing_logs'...")
            db.execute(text("ALTER TABLE inspections ADD COLUMN processing_logs JSONB DEFAULT '[]'::jsonb;"))
            db.commit()
            print("✅ Column added.")

        # 2. Check and Add 'ai_raw_response' to 'inspections'
        print("Checking 'inspections.ai_raw_response'...")
        try:
            db.execute(text("SELECT ai_raw_response FROM inspections LIMIT 1"))
            print("✅ Column 'ai_raw_response' already exists.")
        except Exception:
            db.rollback()
            print("⚠️ Column missing. Adding 'ai_raw_response'...")
            db.execute(text("ALTER TABLE inspections ADD COLUMN ai_raw_response JSONB DEFAULT '{}'::jsonb;"))
            db.commit()
            print("✅ Column added.")

        # 3. Check 'consultant_establishments' table (For "New Consultant" freezes)
        print("Checking table 'consultant_establishments'...")
        try:
            db.execute(text("SELECT 1 FROM consultant_establishments LIMIT 1"))
            print("✅ Table 'consultant_establishments' exists.")
        except Exception:
            db.rollback()
            print("⚠️ Table missing. Creating 'consultant_establishments'...")
            db.execute(text("""
                CREATE TABLE IF NOT EXISTS consultant_establishments (
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    establishment_id UUID NOT NULL REFERENCES establishments(id) ON DELETE CASCADE,
                    PRIMARY KEY (user_id, establishment_id)
                );
            """))
            db.commit()
            print("✅ Table created.")

    except Exception as e:
        print(f"❌ Critical Error during schema fix: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_schema()
