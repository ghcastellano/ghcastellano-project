
import os
import sys
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TARGET_EMAIL = "1013946239177-compute@developer.gserviceaccount.com"
FOLDER_NAMES = ["02_PLANOS_GERADOS", "03_PROCESSADOS_BACKUP", "99_ERROS"]

def share_folders():
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

    permission = {
        'type': 'user',
        'role': 'writer',
        'emailAddress': TARGET_EMAIL
    }

    for name in FOLDER_NAMES:
        try:
            print(f"🔍 Searching for {name}...")
            # Query by name (and trashed=false)
            query = f"name = '{name}' and trashed = false"
            results = service.files().list(q=query, fields="files(id, name)", supportsAllDrives=True).execute()
            files = results.get('files', [])
            
            if not files:
                print(f"⚠️ Folder {name} NOT FOUND.")
                continue
                
            for f in files:
                folder_id = f['id']
                print(f"   Found {name} (ID: {folder_id}). Sharing...")
                try:
                    service.permissions().create(
                        fileId=folder_id,
                        body=permission,
                        sendNotificationEmail=False,
                        supportsAllDrives=True
                    ).execute()
                    print(f"   ✅ Shared {name} ({folder_id})")
                except Exception as e:
                    if "already exists" in str(e) or "quota" in str(e): # Permission existing is not an error usually, api returns it
                         print(f"   ℹ️ Sharing note: {e}")
                    else:
                         print(f"   ❌ Failed to share: {e}")

        except Exception as e:
            print(f"❌ Error processing {name}: {e}")

if __name__ == "__main__":
    share_folders()
