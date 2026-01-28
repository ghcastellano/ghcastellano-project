
import sys
import os
from sqlalchemy import text
from dotenv import load_dotenv

sys.path.append(os.getcwd())
load_dotenv()

from src.app import app
from src.database import engine

def debug_connection():
    print(f"🔧 ENV DATABASE_URL: {os.getenv('DATABASE_URL')}")
    with app.app_context():
        print(f"🔌 SQLAlchemy Engine URL: {engine.url}")
        
        with engine.connect() as conn:
            # Check DB Name
            db_name = conn.execute(text("SELECT current_database();")).scalar()
            print(f"🗄️ Current Database: {db_name}")
            
            # Check if column exists
            result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'establishments' AND column_name = 'responsible_email';"))
            col = result.scalar()
            
            if col:
                print("✅ Column 'responsible_email' exists in this active connection.")
            else:
                print("❌ Column 'responsible_email' DOES NOT EXIST in this active connection.")
                
                # Attempt force add again in this specific connection context
                print("⚠️ Attempting emergency ADD COLUMN...")
                try:
                    conn.execute(text("ALTER TABLE establishments ADD COLUMN IF NOT EXISTS responsible_email VARCHAR(255);"))
                    conn.execute(text("ALTER TABLE establishments ADD COLUMN IF NOT EXISTS responsible_phone VARCHAR(50);"))
                    conn.commit()
                    print("✅ Emergency ADD executed.")
                except Exception as e:
                    print(f"❌ Emergency ADD failed: {e}")

if __name__ == "__main__":
    debug_connection()
