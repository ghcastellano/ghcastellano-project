
import sys
import os
from dotenv import load_dotenv

# Load env before imports
load_dotenv()

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src import database
from src.services.drive_service import drive_service
from src.services.sync_service import process_global_changes
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

    # 2. Run Sync (webhook-based Changes API)
    print("\n🔄 Running process_global_changes...")
    result = process_global_changes(drive_service)

    print("\n✅ Sync Result:")
    print(result)

if __name__ == "__main__":
    run_debug_sync()
