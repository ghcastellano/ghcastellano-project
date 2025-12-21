"""
Migration v11: Action Plan Enrichment (POC Rich Data)
Adds columns for summary, strengths, and stats to action_plans, 
and ai_suggested_deadline to action_plan_items.
"""
import logging
from sqlalchemy import text

logger = logging.getLogger(__name__)

def upgrade(session_factory):
    session = session_factory()
    try:
        logger.info("🚀 Running Migration v11: Action Plan Enrichment...")
        
        # 1. Enrich Action Plans
        session.execute(text("ALTER TABLE action_plans ADD COLUMN IF NOT EXISTS summary_text TEXT;"))
        session.execute(text("ALTER TABLE action_plans ADD COLUMN IF NOT EXISTS strengths_text TEXT;"))
        session.execute(text("ALTER TABLE action_plans ADD COLUMN IF NOT EXISTS stats_json JSONB;"))
        
        # 2. Enrich Action Plan Items
        session.execute(text("ALTER TABLE action_plan_items ADD COLUMN IF NOT EXISTS ai_suggested_deadline VARCHAR;"))
        
        session.commit()
        logger.info("✅ Migration v11 completed successfully.")
    except Exception as e:
        session.rollback()
        logger.error(f"❌ Migration v11 failed: {e}")
        raise e
    finally:
        session.close()
