import sys
import os
from sqlalchemy import text

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src import database

def run_migration():
    print("🚀 Starting Database Schema Cleanup...")
    session = database.db_session()
    try:
        # 1. Drop Visit Table (and dependent constraints if any, though Cascade is safer)
        print("🗑️  Dropping table 'visits'...")
        session.execute(text("DROP TABLE IF EXISTS visits CASCADE;"))
        
        # 2. Drop visit_id from inspections
        print("🔧 Dropping column 'visit_id' from 'inspections'...")
        session.execute(text("ALTER TABLE inspections DROP COLUMN IF EXISTS visit_id;"))
        
        # 3. Drop legacy establishment_id from users (if it exists)
        print("🔧 Dropping legacy column 'establishment_id' from 'users'...")
        session.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS establishment_id;"))
        
        # 4. Drop VisitStatus Enum type if it exists (Postgres uses types for Enums)
        print("🗑️  Dropping type 'visitstatus'...")
        session.execute(text("DROP TYPE IF EXISTS visitstatus;"))

        session.commit()
        print("✅ Migration applied successfully!")
        
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    run_migration()
