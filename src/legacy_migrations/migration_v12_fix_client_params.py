from sqlalchemy import text
from src.database import db_session
import logging

logger = logging.getLogger(__name__)

def upgrade():
    """
    Migration V12: Fix IntegrityError by making client_id nullable.
    The new architecture uses establishment_id/company_id, so legacy client_id FK is optional.
    """
    try:
        logger.info("Running Migration V12: Make client_id nullable...")
        conn = db_session.connection()
        conn.execute(text("ALTER TABLE inspections ALTER COLUMN client_id DROP NOT NULL;"))
        db_session.commit()
        logger.info("Migration V12 Success!")
    except Exception as e:
        db_session.rollback()
        logger.error(f"Migration V12 Failed: {e}")
        # Don't raise, just log. It might already be nullable.
