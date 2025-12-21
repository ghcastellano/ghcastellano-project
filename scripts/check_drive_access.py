from google.oauth2 import service_account
from googleapiclient.discovery import build
import os

import sys

# ID provided by user
FOLDER_ID = sys.argv[1] if len(sys.argv) > 1 else "1BoNT8RbK-MRFqNJzbQRUQqq50o8LIxMa"
CREDS_FILE = "credentials.json"

def check_access():
    try:
        creds = service_account.Credentials.from_service_account_file(CREDS_FILE)
        service = build('drive', 'v3', credentials=creds)

        print(f"Checking access to folder: {FOLDER_ID}")
        
        # Try to get folder metadata
        folder = service.files().get(
            fileId=FOLDER_ID, 
            fields="id, name, capabilities, driveId",
            supportsAllDrives=True
        ).execute()
        print(f"Folder found: {folder.get('name')} (ID: {folder.get('id')})")
        print(f"Drive ID: {folder.get('driveId')}")
        print(f"Capabilities: {folder.get('capabilities', {})}")
        
        # Try to list children
        results = service.files().list(
            q=f"'{FOLDER_ID}' in parents and trashed=false",
            fields="files(id, name, mimeType)",
            pageSize=10,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        
        files = results.get('files', [])
        print(f"\nFiles in folder ({len(files)}):")
        for f in files:
            print(f"- {f['name']} ({f['mimeType']}) - ID: {f['id']}")
            
        # Check write permission
        can_edit = folder.get('capabilities', {}).get('canAddChildren', False)
        print(f"\nCan write to folder? {'YES' if can_edit else 'NO'}")
        
        if can_edit:
            print("\n🧪 Attempting actual upload to verify Quota/Shared Drive status...")
            from googleapiclient.http import MediaIoBaseUpload
            import io
            
            metadata = {
                'name': 'test_quota_check.txt',
                'parents': [FOLDER_ID]
            }
            media = MediaIoBaseUpload(io.BytesIO(b"Checking quota"), mimetype='text/plain')
            
            try:
                new_file = service.files().create(
                    body=metadata,
                    media_body=media,
                    fields='id',
                    supportsAllDrives=True
                ).execute()
                print(f"✅ Upload SUCCESS! File ID: {new_file.get('id')}")
                # cleanup
                service.files().delete(fileId=new_file.get('id'), supportsAllDrives=True).execute()
                print("🗑️ Cleaned up test file.")
            except Exception as e:
                print(f"❌ Upload FAILED: {e}")

    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    check_access()
