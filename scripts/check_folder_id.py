
import os
import sys
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ID_TO_CHECK = "1F8NcC0aR9MQnHDCEJdbx_BuanK8rg08B"

def check_id():
    # Attempt to load credentials
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

    service = build('drive', 'v3', credentials=creds)

    try:
        print(f"Checking ID: {ID_TO_CHECK}")
        file = service.files().get(fileId=ID_TO_CHECK, fields='id, name, mimeType', supportsAllDrives=True).execute()
        print(f"✅ Found! Name: {file.get('name')}, Type: {file.get('mimeType')}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    check_id()
