
import sys
import os
from dotenv import load_dotenv
from sqlalchemy import text

load_dotenv()
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src import database

def clean_jobs_table():
    db = next(database.get_db())
    try:
        print("🧹 Cleaning up 'jobs' table schema...")
        
        # Check if columns exist before dropping (Postgres safe)
        columns_to_drop = ['summary_text', 'strengths_text', 'stats_json']
        
        for col in columns_to_drop:
            print(f"   🗑️ Dropping column: {col}")
            try:
                db.execute(text(f"ALTER TABLE jobs DROP COLUMN IF EXISTS {col};"))
            except Exception as e:
                print(f"      ⚠️ Failed to drop {col}: {e}")
                
        db.commit()
        print("✅ Clean up complete! Legacy columns removed.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    clean_jobs_table()
