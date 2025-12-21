
import logging
from sqlalchemy import text

logger = logging.getLogger(__name__)

def upgrade(session_factory):
    # session_factory is likely db_session (scoped_session), calling it gets the session
    session = session_factory()
    try:
        logger.info("🚀 Running Migration v13: Jobs Enrichment (summary_text, strengths, stats)...")
        
        # Add missing columns to 'jobs' table
        session.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS summary_text TEXT;"))
        session.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS strengths_text TEXT;"))
        session.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS stats_json JSONB;"))
        
        session.commit()
        logger.info("✅ Migration v13 completed successfully.")
    except Exception as e:
        session.rollback()
        logger.error(f"❌ Migration v13 failed: {e}")
        raise e
    finally:
        # If we got a fresh session or explicitly want to close usage in this script
        # session.close() 
        # With scoped_session, close() usually just clears the transaction. remove() clears the thread.
        pass
