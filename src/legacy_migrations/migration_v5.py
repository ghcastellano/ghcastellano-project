import logging
from sqlalchemy import create_engine, text
from src.config import config
from src.database import normalize_database_url

logger = logging.getLogger("migration_v5")

def run_migration_v5():
    """
    Migration V5:
    1. Add 'responsible_name' and 'responsible_phone' to 'establishments'.
    2. Add 'file_hash' to 'inspections' (MD5/SHA256 hex string).
    """
    database_url = normalize_database_url(config.DATABASE_URL)
    if not database_url:
        logger.error("❌ DATABASE_URL not found.")
        return

    try:
        engine = create_engine(database_url)
        with engine.connect() as conn:
            logger.info("🔄 Checking/Running Database Migration V5...")
            
            # 1. Establishment Fields
            try:
                conn.execute(text("ALTER TABLE establishments ADD COLUMN IF NOT EXISTS responsible_name VARCHAR;"))
                conn.execute(text("ALTER TABLE establishments ADD COLUMN IF NOT EXISTS responsible_phone VARCHAR;"))
                conn.commit()
                logger.info("✅ Added responsible fields to establishments.")
            except Exception as e:
                logger.error(f"⚠️ Error adding establishment fields: {e}")
                conn.rollback()

            # 2. Inspection File Hash
            try:
                conn.execute(text("ALTER TABLE inspections ADD COLUMN IF NOT EXISTS file_hash VARCHAR;"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_inspections_hash ON inspections(file_hash);"))
                conn.commit()
                logger.info("✅ Added file_hash to inspections.")
            except Exception as e:
                logger.error(f"⚠️ Error adding file_hash: {e}")
                conn.rollback()
            
            logger.info("✅ Database Migration V5 Checked/Applied.")
            
    except Exception as e:
        logger.error(f"⚠️ Migration V5 Error: {e}")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    run_migration_v5()
