import os
import logging
from src.services.drive_service import drive_service

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("debug_drive")

def audit_drive():
    logger.info("🔍 Auditing Drive Access for Service Account...")
    
    if not drive_service.service:
        logger.error("❌ Drive Service not authenticated.")
        return

    # 1. Check Identity
    try:
        about = drive_service.service.about().get(fields="user").execute()
        logger.info(f"👤 Authenticated as: {about['user']['emailAddress']}")
    except Exception as e:
        logger.error(f"❌ Could not get About info: {e}")

    # 2. List all Folders visible
    logger.info("\nPpsting Folders (mimeType = application/vnd.google-apps.folder):")
    try:
        results = drive_service.service.files().list(
            q="mimeType='application/vnd.google-apps.folder' and trashed=false",
            fields="files(id, name, owners, capabilities)",
            pageSize=50,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        
        folders = results.get('files', [])
        found_ids = {}
        for f in folders:
            owner = f.get('owners', [{}])[0].get('emailAddress', 'Unknown')
            can_add = f.get('capabilities', {}).get('canAddChildren', False)
            logger.info(f"📂 Found: '{f['name']}' | ID: {f['id']} | Owner: {owner} | Writable: {can_add}")
            found_ids[f['id']] = f['name']
            
    except Exception as e:
        logger.error(f"❌ Error listing folders: {e}")

    # 3. Check Known IDs from Config
    # We load from .env manually or rely on what's available
    from dotenv import load_dotenv
    load_dotenv()
    
    target_ids = {
        "FOLDER_01": os.getenv("FOLDER_ID_01_ENTRADA_RELATORIOS"),
        "FOLDER_02": os.getenv("FOLDER_ID_02_PLANOS_GERADOS"),
        "FOLDER_03": os.getenv("FOLDER_ID_03_PROCESSADOS_BACKUP"),
        "FOLDER_99": os.getenv("FOLDER_ID_99_ERROS")
    }
    
    logger.info("\n🔍 verifying Configured IDs:")
    for key, fid in target_ids.items():
        if not fid:
            logger.warning(f"⚠️ {key} is NOT SET in env.")
            continue
            
        if fid in found_ids:
            logger.info(f"✅ {key}: Found ({found_ids[fid]})")
        else:
            logger.error(f"❌ {key}: ID {fid} NOT FOUND in accessible folders!")
            
            # Special check for the specific ID causing 404 in logs
            if fid == "1Hqq1Ld3jnPCPvbJJqBPQMqgMWNgbPOvQ":
                logger.error(f"   -> THIS is the ID causing the 404 error.")

if __name__ == "__main__":
    audit_drive()
