
import sys
import os
import logging
from sqlalchemy import text

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv()

from src import database

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migration_deadline_text")

def add_deadline_text_column():
    """
    Adds 'deadline_text' column to action_plan_items table if it doesn't exist.
    """
    logger.info("🚀 Iniciando Migração: Adicionar coluna deadline_text...")
    
    # Get a fresh session
    db_gen = database.get_db()
    db_session = next(db_gen)
    
    try:
        # Check if column exists
        check_query = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='action_plan_items' AND column_name='deadline_text';
        """)
        result = db_session.execute(check_query).fetchone()
        
        if result:
            logger.info("✅ Coluna 'deadline_text' já existe. Pulando.")
        else:
            logger.info("⚠️ Coluna 'deadline_text' ausente. Adicionando...")
            # We use String (Text) to allow flexibility
            alter_query = text("ALTER TABLE action_plan_items ADD COLUMN deadline_text TEXT;")
            db_session.execute(alter_query)
            db_session.commit()
            logger.info("✅ Coluna 'deadline_text' adicionada com sucesso!")
            
    except Exception as e:
        logger.error(f"❌ Migração Falhou: {e}")
        db_session.rollback()
    finally:
        db_session.close()

if __name__ == "__main__":
    add_deadline_text_column()
