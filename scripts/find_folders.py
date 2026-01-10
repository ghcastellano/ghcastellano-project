import sys
import os

# Add src to path
sys.path.append(os.path.abspath('.'))

from src.services.drive_service import DriveService

def find_folders():
    print("🔍 Diagnosticando pastas do Drive...")
    drive = DriveService()
    
    folders_to_find = [
        "01_ENTRADA_RELATORIOS",
        "02_PLANOS_GERADOS", 
        "03_PROCESSADOS_BACKUP",
        "99_ERROS"
    ]
    
    found_ids = {}
    
    for folder_name in folders_to_find:
        print(f"   > Procurando '{folder_name}'...")
        # Search by name and mimeType folder
        # Note: This simple search might return multiple if duplicates exist
        query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false"
        results = drive.service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get('files', [])
        
        if not files:
            print(f"❌ '{folder_name}' NÃO ENCONTRADA.")
        else:
            for f in files:
                print(f"✅ ENCONTRADA: {f['name']} -> ID: {f['id']}")
                found_ids[folder_name] = f['id']
                
                # List content sample
                print(f"      Conteúdo (Amostra):")
                content = drive.list_files(f['id'])[:3]
                if not content:
                    print("         (Vazio)")
                else:
                    for c in content:
                        print(f"         - {c['name']} (ID: {c['id']})")

    print("\n\n--- ENV VARS SUGGESTION ---")
    for name, fid in found_ids.items():
        print(f"export FOLDER_ID_{name}={fid}")

if __name__ == "__main__":
    find_folders()
