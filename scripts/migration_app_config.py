
import logging
import src.database as db
from src.models_db import Base, AppConfig

# Configure logging
logger = logging.getLogger("mvp-app")

from sqlalchemy import text

def create_app_config_table():
    """
    Creates the AppConfig table using Raw SQL to ensure it exists.
    """
    try:
        # Ensure Database Connection
        if db.engine is None:
            logger.info("Initializing Database for Migration...")
            db.init_db()
        
        if db.engine:
            logger.info("Running Raw SQL CREATE TABLE IF NOT EXISTS...")
            with db.engine.connect() as conn:
                # Create table
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS app_config (
                        key VARCHAR PRIMARY KEY,
                        value VARCHAR,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                """))
                conn.commit()
            logger.info("✅ Table AppConfig Verified/Created via Raw SQL.")
        else:
            logger.error("❌ Failed to initialize Database Engine.")
            raise ConnectionError("Database Engine is None")
            
    except Exception as e:
        logger.error(f"❌ Migration Error: {e}")
        raise e

if __name__ == "__main__":
    create_app_config_table()
