
import sys
import os
from dotenv import load_dotenv

# Load env before imports
load_dotenv()

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src import database
from src.services.drive_service import drive_service
from src.services.sync_service import perform_drive_sync
import logging

# Configure logging to stdout
logging.basicConfig(level=logging.INFO)

def run_debug_sync():
    print("🚀 Starting Debug Sync...")
    database.init_db()
    
    # 1. Check Authenticated User/Service
    try:
        about = drive_service.service.about().get(fields="user, storageQuota").execute()
        print(f"👤 Drive User: {about['user']['emailAddress']}")
    except Exception as e:
        print(f"❌ Drive Auth Error: {e}")
        return

    # 2. Run Sync
    print("\n🔄 Running perform_drive_sync...")
    result = perform_drive_sync(drive_service, limit=10, user_trigger=True)
    
    print("\n✅ Sync Result:")
    print(result)

if __name__ == "__main__":
    run_debug_sync()
