import sys
import os
import structlog
from sqlalchemy import text

# Add root to sys.path to find src
sys.path.append(os.path.abspath('.'))

from src.database import init_db, db_session

logger = structlog.get_logger()

def patch_establishments_schema():
    logger.info("🔧 Iniciando Patch de Schema: Establishments...")
    
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("❌ DATABASE_URL not set in env")
        return

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # 1. Patch Establishments (Responsible Info)
        logger.info("Verifying responsible_name in establishments...")
        try:
            session.execute(text("SELECT responsible_name FROM establishments LIMIT 1"))
        except Exception:
            session.rollback()
            logger.info("Adding responsible_name/email/phone columns...")
            session.execute(text("ALTER TABLE establishments ADD COLUMN IF NOT EXISTS responsible_name VARCHAR(255)"))
            session.execute(text("ALTER TABLE establishments ADD COLUMN IF NOT EXISTS responsible_email VARCHAR(255)"))
            session.execute(text("ALTER TABLE establishments ADD COLUMN IF NOT EXISTS responsible_phone VARCHAR(20)"))
            session.commit()

        # 2. Patch Inspections (updated_at)
        logger.info("Verifying updated_at in inspections...")
        try:
            session.execute(text("SELECT updated_at FROM inspections LIMIT 1"))
        except Exception:
            session.rollback()
            logger.info("Adding updated_at column to inspections...")
            session.execute(text("ALTER TABLE inspections ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()"))
            session.commit()
            
        logger.info("✅ Todos os patches aplicados com sucesso!")
        
    except Exception as e:
        logger.error(f"❌ Erro ao aplicar patch: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    patch_establishments_schema()
