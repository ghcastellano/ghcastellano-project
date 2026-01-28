import os
# Since .env is gone, I set DB URL manually for this script based on logs
os.environ["DATABASE_URL"] = "postgresql://neondb_owner:npg_VHxOI2vsD3YP@ep-steep-surf-a4igari9-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require"

import src.database
from src.database import init_db
from src.models_db import Establishment

def fix_folders():
    init_db()
    session = src.database.db_session
    
    try:
        establishments = session.query(Establishment).all()
        print(f"Found {len(establishments)} establishments.")
        
        count = 0
        for est in establishments:
            # We want to force usage of the main FOLDER_IN (Shared Drive)
            # So we clear any specific folder ID that might be legacy/personal drive
            if est.drive_folder_id:
                print(f"Clearing legacy folder ID for {est.name}: {est.drive_folder_id}")
                est.drive_folder_id = None
                count += 1
        
        if count > 0:
            session.commit()
            print(f"✅ Successfully cleared folder IDs for {count} establishments.")
        else:
            print("No establishments needed updates.")
            
    except Exception as e:
        session.rollback()
        print(f"❌ Error updating database: {e}")
    finally:
        session.remove()

if __name__ == "__main__":
    fix_folders()
