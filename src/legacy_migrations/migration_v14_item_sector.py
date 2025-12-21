"""
Migration v14: Add Sector to Action Plan Items
Adds 'sector' column to action_plan_items to allow grouping significantly improving UI.
"""
import logging
from sqlalchemy import text

logger = logging.getLogger(__name__)

def upgrade(session_factory):
    session = session_factory()
    try:
        logger.info("🚀 Running Migration v14: Add Sector to Action Plan Items...")
        
        # Add 'sector' column
        session.execute(text("ALTER TABLE action_plan_items ADD COLUMN IF NOT EXISTS sector TEXT;"))
        
        session.commit()
        logger.info("✅ Migration v14 completed successfully.")
    except Exception as e:
        session.rollback()
        logger.error(f"❌ Migration v14 failed: {e}")
        raise e
    finally:
        session.close()
