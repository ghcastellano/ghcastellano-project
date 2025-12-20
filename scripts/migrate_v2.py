import os
import sys
from dotenv import load_dotenv
from sqlalchemy import text

# Load env vars FIRST
load_dotenv()

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Import the module itself, not attributes
import src.database

def run_migration():
    # Force set DATABASE_URL in the module to be sure
    if not src.database.DATABASE_URL:
        src.database.DATABASE_URL = os.getenv("DATABASE_URL")
    
    # Init DB
    src.database.init_db()
    
    engine = src.database.engine
    
    if not engine:
        print("❌ Could not connect to DB (Engine is None)")
        return

    with engine.connect() as conn:
        print("🔄 Starting Migration V2...")
        
        # 1. Add password_hash and name to users
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash VARCHAR;"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS name VARCHAR;"))
            conn.commit() # Commit immediatelly
            print("✅ Users table updated")
        except Exception as e:
            print(f"⚠️ Error updating users: {e}")
            conn.rollback()

        # 2. Add manager_notes to action_plan_items
        try:
            conn.execute(text("ALTER TABLE action_plan_items ADD COLUMN IF NOT EXISTS manager_notes TEXT;"))
            conn.commit()
            print("✅ Action Plans Items updated")
        except Exception as e:
            print(f"⚠️ Error updating items: {e}")
            conn.rollback()

        # 3. Update ENUM types (Postgres specific)
        # This is tricky because we can't reliably check if 'PENDING_MANAGER_REVIEW' exists easily without querying pg_enum
        # We'll try to add it. If it fails (duplicate), we ignore.
        
        enums_to_add = [
            ("inspectionstatus", "PENDING_MANAGER_REVIEW"),
            ("inspectionstatus", "PENDING_VERIFICATION"),
            ("inspectionstatus", "COMPLETED"),
        ]
        
        # For Enums, we shouldn't fail the whole migration if one fails
        for enum_name, value in enums_to_add:
            try:
                 # Postgres 12+ supports IF NOT EXISTS for ADD VALUE but older ones don't. Supabase is usually new.
                 # "ALTER TYPE ... ADD VALUE IF NOT EXISTS ..."
                 conn.execute(text(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{value}';"))
                 conn.commit()
                 print(f"✅ Added {value} to {enum_name}")
            except Exception as e:
                # Fallback for older Postgres or if type doesn't exist
                try:
                    conn.rollback()
                    conn.execute(text(f"ALTER TYPE {enum_name} ADD VALUE '{value}';"))
                    conn.commit()
                except Exception as e2:
                     print(f"ℹ️ Could not add {value} to {enum_name} (likely exists or not enum): {e2}")
                     conn.rollback()

        print("🏁 Migration Completed")

if __name__ == "__main__":
    run_migration()
