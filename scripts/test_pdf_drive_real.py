import sys
import os
import logging
import time
from dotenv import load_dotenv

# Setup Path
sys.path.append(os.getcwd())

# Logger Setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("RealDriveTest")

# Load .env
load_dotenv()

from src.app import app
from src.database import db_session, engine
from src.services.processor import ProcessorService
from src.models_db import Company, Job, JobStatus

def run_real_test():
    with app.app_context():
        # Setup Database Session
        session = db_session()
        
        # 1. Ensure Company Exists
        company = session.query(Company).first()
        if not company:
            logger.info("🆕 Company not found, creating test company...")
            import uuid
            company = Company(id=uuid.uuid4(), name="Empresa Teste Real Drive")
            session.add(company)
            session.commit()
        logger.info(f"🏢 Using Company: {company.name}")

        # 2. Initialize Processor (REAL)
        logger.info("⚙️ Initializing ProcessorService (REAL DRIVE)...")
        processor = ProcessorService()
        
        # 3. Check Folders
        folder_in = processor.folder_in
        
        if not folder_in:
            logger.warning("⚠️ FOLDER_ID_01_ENTRADA_RELATORIOS not set. Searching Drive for '01_Entrada_Relatorios'...")
            try:
                # Search for the folder
                query = "mimeType='application/vnd.google-apps.folder' and name contains '01_Entrada_Relatorios' and trashed=false"
                found_folders = processor.drive_service.service.files().list(q=query, fields="files(id, name)").execute().get('files', [])
                
                if found_folders:
                    folder_in = found_folders[0]['id']
                    logger.info(f"✅ Auto-detected Folder: {found_folders[0]['name']} ({folder_in})")
                    # Update processor config dynamically
                    processor.folder_in = folder_in
                else:
                    logger.error("❌ Could not find folder '01_Entrada_Relatorios' in Drive.")
                    print("\n⚠️ A pasta de entrada não foi encontrada automaticamente.")
                    return
            except Exception as e:
                logger.error(f"❌ Error searching for folder: {e}")
                return

        # Auto-detect Output Folder
        if not processor.folder_out:
            logger.warning("⚠️ FOLDER_ID_02_PLANOS_GERADOS not set. Searching Drive for '02_Planos_Gerados'...")
            try:
                query = "mimeType='application/vnd.google-apps.folder' and name contains '02_Planos_Gerados' and trashed=false"
                found_out = processor.drive_service.service.files().list(q=query, fields="files(id, name)").execute().get('files', [])
                if found_out:
                    processor.folder_out = found_out[0]['id']
                    logger.info(f"✅ Auto-detected Output Folder: {found_out[0]['name']} ({processor.folder_out})")
                else:
                    logger.warning("⚠️ Output folder not found. Files may go to Root.")
            except:
                pass

        drive_url = f"https://drive.google.com/drive/u/0/folders/{folder_in}"
        logger.info(f"📂 INPUT FOLDER URL: {drive_url}")
        print(f"\n👉 POR FAVOR, ACESSE A PASTA E FAÇA UPLOAD DE UM ARQUIVO PDF AGORA:\n   {drive_url}\n")
        
        # 4. Poll for Files
        logger.info("👀 Waiting for files in Input Folder (Polling)...")
        files = []
        max_attempts = 12 # 1 minute (5s interval)
        
        for i in range(max_attempts):
            try:
                files = processor.drive_service.list_files(folder_in)
                files = [f for f in files if f['name'].lower().endswith('.pdf')]
                
                if files:
                    logger.info(f"✅ Found {len(files)} PDF file(s)!")
                    break
                
                print(f"   ... ({i+1}/{max_attempts}) Nenhum arquivo encontrado. Aguardando...")
                time.sleep(5)
            except Exception as e:
                logger.error(f"⚠️ Error listing files: {e}")
                time.sleep(5)
        
        if not files:
            logger.warning("❌ Timeout: Nenhum arquivo encontrado após tentativa de polling.")
            return

        # 5. Process First File
        target_file = files[0]
        logger.info(f"🚀 Starting Processing for: {target_file['name']} ({target_file['id']})")
        
        # Create Job
        job = Job(
            company_id=company.id,
            type="REAL_DRIVE_TEST",
            status=JobStatus.PENDING,
            input_payload={'filename': target_file['name'], 'file_id': target_file['id']}
        )
        
        try:
            result_link = processor.process_single_file(
                target_file,
                company_id=company.id,
                establishment_id=None,
                job=job
            )
            
            if result_link:
                logger.info(f"✅ SUCCESS! Output Link: {result_link}")
                print(f"\n📄 PDF FINAL GERADO: {result_link}\n")
            elif result_link is None:
                 # Check if it was skipped due to duplicate (check logs)
                 logger.info("ℹ️ Processing completed (Check if skipped or saved locally).")
            else:
                logger.error("❌ Processing returned None")
                
        except Exception as e:
            logger.exception(f"❌ Critical Error processing {target_file['name']}")

if __name__ == "__main__":
    run_real_test()
