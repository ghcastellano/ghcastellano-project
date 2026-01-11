
import os
import json
import logging
from google.oauth2.credentials import Credentials as UserCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FOLDER_ID = "1F8NcC0aR9MQnHDCEJdbx_BuanK8rg08B"
TOKEN_FILE = "user_credentials.json"
TEST_FILE = "test_upload_quota.pdf"

def verify_upload():
    if not os.path.exists(TOKEN_FILE):
        print(f"❌ {TOKEN_FILE} not found.")
        return

    print("🔑 Loading User Credentials...")
    with open(TOKEN_FILE, 'r') as f:
        info = json.load(f)
    
    # Simulate App Logic
    creds = UserCredentials.from_authorized_user_info(info, ['https://www.googleapis.com/auth/drive'])
    service = build('drive', 'v3', credentials=creds)

    # Create Dummy PDF File
    with open(TEST_FILE, "wb") as f:
        f.write(b"%PDF-1.4\n%EOF") # Minimal PDF header

    try:
        print(f"📤 Attempting upload to folder {FOLDER_ID} as User...")
        
        file_metadata = {
            'name': 'Teste_Upload_Quota_Antigravity.pdf',
            'parents': [FOLDER_ID]
        }
        media = MediaFileUpload(TEST_FILE, mimetype='application/pdf', resumable=True)

        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink, owners',
            supportsAllDrives=True
        ).execute()

        print(f"✅ Upload Success! File ID: {file.get('id')}")
        print(f"🔗 Link: {file.get('webViewLink')}")
        owners = file.get('owners', [])
        if owners:
            print(f"👤 File Owner: {owners[0].get('emailAddress')}")
        
        # Cleanup
        # print("🧹 Deleting test file from Drive...")
        # service.files().delete(fileId=file.get('id'), supportsAllDrives=True).execute()
        print("🎉 File kept in Drive for verification.")
        
    except Exception as e:
        print(f"❌ Upload Failed: {e}")
    finally:
        if os.path.exists(TEST_FILE):
            os.remove(TEST_FILE)

if __name__ == "__main__":
    verify_upload()
