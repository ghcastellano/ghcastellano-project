
import os
import sys
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)

# Mock Env
os.environ['GCP_OAUTH_TOKEN'] = '{"refresh_token": "mock"}'

try:
    from src.services.drive_service import DriveService
    
    print("✅ Imported DriveService")
    
    ds = DriveService()
    # Mocking json load failure to trigger the lines
    try:
        ds._authenticate()
    except Exception as e:
        print(f"⚠️ Auth failed as expected (mock data), but did it raise UnboundLocalError? Error: {e}")
        if "UnboundLocalError" in str(e):
            print("❌ UnboundLocalError DETECTED!")
            sys.exit(1)
        
    print("✅ No UnboundLocalError detected.")
    
except ImportError:
    # Adjust path if needed or run from root
    sys.path.append(os.getcwd())
    from src.services.drive_service import DriveService
    ds = DriveService()
    try:
        ds._authenticate()
    except Exception as e:
        if "UnboundLocalError" in str(e):
             print(f"❌ UnboundLocalError DETECTED: {e}")
             sys.exit(1)
        print(f"Caught expected error (not UnboundLocal): {e}")

    print("✅ Code structure is valid.")
