
import logging
import os
import sys
from sqlalchemy import text
from dotenv import load_dotenv

# Setup path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load Env
load_dotenv()

from src.database import get_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def patch_company_folder():
    db = next(get_db())
    try:
        logger.info("🛠️ Applying Schema Patch for Company Drive Folder...")
        
        # Check and Add drive_folder_id to companies
        db.execute(text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS drive_folder_id VARCHAR"))
        
        db.commit()
        logger.info("✅ Patch Applied Successfully.")
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Patch Failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    patch_company_folder()
