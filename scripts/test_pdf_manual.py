
import sys
import os
import logging
from unittest.mock import MagicMock

# Setup Path
sys.path.append(os.getcwd())

# Logger Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ManualTest")

# Load .env explicitly
from dotenv import load_dotenv
load_dotenv()

# Environment Check
if not os.getenv("OPENAI_API_KEY"):
    logger.error("❌ OPENAI_API_KEY not found! Set it in .env or environment.")
    sys.exit(1)

from src.app import app
from src.services.processor import ProcessorService
from src.models_db import Company, Job, JobStatus, Establishment
from src.database import db_session

def mock_download_file(file_id):
    local_path = "data/backup/quest_resposta (3).pdf"
    if not os.path.exists(local_path):
        logger.error(f"❌ File not found: {local_path}")
        raise FileNotFoundError(local_path)
    
    logger.info(f"📂 [MOCK-DRIVE] Serving local file: {local_path}")
    with open(local_path, "rb") as f:
        return f.read()

def run_test():
    with app.app_context():
        session = db_session()
        
        # 1. Get Valid Company (or Create)
        company = session.query(Company).first()
        if not company:
            logger.info("🆕 Creating Test Company...")
            import uuid
            company = Company(id=uuid.uuid4(), name="Empresa Teste Manual")
            session.add(company)
            session.commit()
        
        logger.info(f"🏢 Using Company: {company.name} ({company.id})")
        
        # 2. Setup Processor
        logger.info("⚙️ Initializing ProcessorService...")
        processor = ProcessorService()
        
        # 3. Patch Drive Service
        processor.drive_service = MagicMock()
        processor.drive_service.download_file.side_effect = mock_download_file
        
        # 4. Mock Job (Optional, but good for tracing)
        job = Job(
            company_id=company.id,
            type="MANUAL_TEST",
            status=JobStatus.PENDING,
            input_payload={'filename': 'quest_resposta (3).pdf'}
        )
        # We don't necessarily need to save job to DB if processor handles it gracefully, 
        # but processor logs to job.status. Let's make it a simple object.
        
        # 5. Run Processing
        file_meta = {'id': 'local_test_file', 'name': 'quest_resposta (3).pdf'}
        
        logger.info("🚀 Starting Processing (This calls Real OpenAI)...")
        try:
            result_link = processor.process_single_file(
                file_meta,
                company_id=company.id,
                establishment_id=None, # Auto-detect
                job=job
            )
            
            if result_link:
                logger.info(f"✅ SUCCESS! Output Link: {result_link}")
                logger.info(f"📊 Extraction Data (Summary): {job.output_payload.get('resumo', 'N/A') if job.output_payload else 'No Payload'}")
            else:
                logger.error("❌ Processing returned None (Failure)")
        
        except Exception as e:
            logger.exception("❌ Critical Error during Processing")
            # Print specifically if it's an OpenAI error
            if "Displaying" in str(e): # WeasyPrint error common on some envs
                logger.error("⚠️ WeasyPrint/PDF Generation Error (Check Libraries)")

if __name__ == "__main__":
    run_test()
