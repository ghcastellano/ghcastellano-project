
import logging
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB

logger = logging.getLogger(__name__)

def upgrade(session_factory):
    session = session_factory()
    try:
        logger.info("🚀 Running Migration v15: Traceability (processing_logs)...")
        
        # Add 'processing_logs' column to 'inspections' table
        # Using JSONB for efficient querying and storage of log arrays
        session.execute(text("ALTER TABLE inspections ADD COLUMN IF NOT EXISTS processing_logs JSONB;"))
        
        session.commit()
        logger.info("✅ Migration v15 completed successfully.")
    except Exception as e:
        session.rollback()
        logger.error(f"❌ Migration v15 failed: {e}")
        raise e
    finally:
        pass
