
import os
import sys
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FOLDER_ID = "1F8NcC0aR9MQnHDCEJdbx_BuanK8rg08B"
TARGET_EMAIL = "1013946239177-compute@developer.gserviceaccount.com"

def share_folder():
    creds_file = 'credentials.json'
    creds = None
    
    if os.path.exists(creds_file):
        creds = Credentials.from_service_account_file(creds_file, scopes=['https://www.googleapis.com/auth/drive'])
    elif os.getenv('GCP_SA_KEY'):
        import json
        info = json.loads(os.getenv('GCP_SA_KEY'))
        creds = Credentials.from_service_account_info(info, scopes=['https://www.googleapis.com/auth/drive'])
    else:
        print("No credentials found.")
        return

    print(f"🤖 Authorizing as: {creds.service_account_email}")
    service = build('drive', 'v3', credentials=creds)

    try:
        # Create Permission
        permission = {
            'type': 'user',
            'role': 'writer',
            'emailAddress': TARGET_EMAIL
        }
        
        print(f"📤 Sharing folder {FOLDER_ID} with {TARGET_EMAIL}...")
        
        service.permissions().create(
            fileId=FOLDER_ID,
            body=permission,
            # emailMessage="Access granted for Cloud Run", # Removed to fix 403
            sendNotificationEmail=False,
            supportsAllDrives=True
        ).execute()
        
        print("✅ Successfully shared!")
            
    except Exception as e:
        print(f"❌ Error sharing: {e}")

if __name__ == "__main__":
    share_folder()
