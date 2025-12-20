from google.oauth2 import service_account
from googleapiclient.discovery import build

import sys

PARENT_ID = sys.argv[1] if len(sys.argv) > 1 else "1BoNT8RbK-MRFqNJzbQRUQqq50o8LIxMa"
CREDS_FILE = "credentials.json"
FOLDERS_TO_CREATE = ["01_Entrada", "02_Saida", "03_Backup", "99_Erros"]

def setup_folders():
    creds = service_account.Credentials.from_service_account_file(CREDS_FILE)
    service = build('drive', 'v3', credentials=creds)

    created_ids = {}

    for name in FOLDERS_TO_CREATE:
        file_metadata = {
            'name': name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [PARENT_ID]
        }
        # Added supportsAllDrives=True which is required for files on Shared Drives
        file = service.files().create(
            body=file_metadata, 
            fields='id',
            supportsAllDrives=True
        ).execute()
        
        print(f"Created folder '{name}' with ID: {file.get('id')}")
        created_ids[name] = file.get('id')

    # Print .env format
    print("\n--- .env CONTENT ---")
    print(f"FOLDER_ID_01_ENTRADA_RELATORIOS={created_ids['01_Entrada']}")
    print(f"FOLDER_ID_02_PLANOS_GERADOS={created_ids['02_Saida']}")
    print(f"FOLDER_ID_03_PROCESSADOS_BACKUP={created_ids['03_Backup']}")
    print(f"FOLDER_ID_99_ERROS={created_ids['99_Erros']}")

if __name__ == "__main__":
    setup_folders()
