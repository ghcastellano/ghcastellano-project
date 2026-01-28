
import sys
import os
from sqlalchemy import text

# Setup Path
sys.path.append(os.getcwd())

from src.app import app
from src.database import engine, get_db

def fix_schema():
    print("🔧 Patching DB Schema...")
    with app.app_context():
        # Engine should be init by app
        from src.database import engine
        if not engine:
            print("❌ Engine still None. Init failed.")
            return

        with engine.connect() as conn:
            # 1. responsible_email
            try:
                conn.execute(text("ALTER TABLE establishments ADD COLUMN IF NOT EXISTS responsible_email VARCHAR(255);"))
                print("✅ Added 'responsible_email'")
            except Exception as e:
                print(f"⚠️ process email: {e}")

            # 2. responsible_phone (checking if needed)
            try:
                conn.execute(text("ALTER TABLE establishments ADD COLUMN IF NOT EXISTS responsible_phone VARCHAR(50);"))
                print("✅ Added 'responsible_phone'")
            except Exception as e:
                print(f"⚠️ process phone: {e}")
            
            conn.commit()
    print("🏁 Schema Patch Complete.")

if __name__ == "__main__":
    fix_schema()
