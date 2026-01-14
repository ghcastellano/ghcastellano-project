
import os
import sys
import logging
from sqlalchemy import text, inspect

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from dotenv import load_dotenv
load_dotenv()

from src.database import get_db, engine, init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def patch_db():
    init_db()
    from src.database import engine # re-import after init to get the populated global variable if it was None before
    
    logger.info("🔧 Starting Schema Patch: Add visit_date to visits...")
    
    try:
        inspector = inspect(engine)
        columns = [c['name'] for c in inspector.get_columns('visits')]
        
        with engine.connect() as conn:
            if 'visit_date' not in columns:
                logger.info("⚙️ Adding column 'visit_date' to 'visits' table...")
                conn.execute(text("ALTER TABLE visits ADD COLUMN visit_date TIMESTAMP WITH TIME ZONE DEFAULT NOW()"))
                logger.info("✅ Column 'visit_date' added!")
            else:
                logger.info("✅ Column 'visit_date' already exists.")

            if 'establishment_id' not in columns:
                logger.info("⚙️ Adding column 'establishment_id' to 'visits' table...")
                conn.execute(text("ALTER TABLE visits ADD COLUMN establishment_id UUID REFERENCES establishments(id)"))
                logger.info("✅ Column 'establishment_id' added!")
            else:
                logger.info("✅ Column 'establishment_id' already exists.")

            conn.commit()
            
    except Exception as e:
        logger.error(f"❌ Patch failed: {e}")
        raise

if __name__ == "__main__":
    patch_db()
