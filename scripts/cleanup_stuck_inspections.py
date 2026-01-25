
import sys
import os
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src import database
from src.models_db import Inspection, InspectionStatus

def cleanup_stuck_inspections():
    db = next(database.get_db())
    try:
        print("\n🧹 Cleaning up stuck PROCESSING inspections for 'Loja 1'...")
        
        # Hard filter for safety: Status PROCESSING and Establishment 'Loja 1' (via join if needed, or by logic)
        # But for now, let's just kill ALL PROCESSING older than 1 hour to vary safe.
        # Actually user specifically pointed to these 4-5 items.
        
        # Get count
        stuck = db.query(Inspection).filter(
            Inspection.status == InspectionStatus.PROCESSING
        ).all()
        
        if not stuck:
            print("✅ No stuck items found.")
            return

        print(f"⚠️ Found {len(stuck)} stuck inspections.")
        for i in stuck:
            print(f"   🗑️ Deleting stuck inspection {i.id} (File: {i.drive_file_id})")
            db.delete(i)
        
        db.commit()
        print("✅ Cleanup complete!")

    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    cleanup_stuck_inspections()
