
import sys
import os
from sqlalchemy import text

sys.path.append(os.getcwd())
from src.app import app
from src.database import engine

def cleanup_db():
    print("🗑️ Starting Legacy Clients Table Cleanup...")
    with app.app_context():
        with engine.connect() as conn:
            # 1. Drop FK Constraint if exists (Inspections)
            try:
                # Find constraint name first if needed, but CASCADE might handle it.
                # Attempting direct column drop which should fail if FK exists unless Cascade
                conn.execute(text("ALTER TABLE inspections DROP COLUMN IF EXISTS client_id CASCADE;"))
                print("✅ Dropped 'client_id' from 'inspections'")
            except Exception as e:
                print(f"⚠️ Error dropping 'client_id' from 'inspections': {e}")

            # 2. Drop FK Constraint if exists (Visits)
            try:
                conn.execute(text("ALTER TABLE visits DROP COLUMN IF EXISTS client_id CASCADE;"))
                print("✅ Dropped 'client_id' from 'visits'")
            except Exception as e:
                print(f"⚠️ Error dropping 'client_id' from 'visits': {e}")

            # 3. Drop Table Clients
            try:
                conn.execute(text("DROP TABLE IF EXISTS clients CASCADE;"))
                print("✅ Dropped table 'clients'")
            except Exception as e:
                print(f"⚠️ Error dropping table 'clients': {e}")
            
            conn.commit()
    print("🏁 Cleanup Complete.")

if __name__ == "__main__":
    cleanup_db()
