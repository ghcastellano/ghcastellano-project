
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
logger = logging.getLogger("migration_order")

def add_order_column():
    """
    Adds 'order_index' column to action_plan_items table if it doesn't exist.
    """
    logger.info("🚀 Iniciando Migração: Adicionar coluna order_index...")
    
    db_session = next(database.get_db())
    try:
        # Check if column exists
        check_query = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='action_plan_items' AND column_name='order_index';
        """)
        result = db_session.execute(check_query).fetchone()
        
        if result:
            logger.info("✅ Coluna 'order_index' já existe. Pulando.")
        else:
            logger.info("⚠️ Coluna 'order_index' ausente. Adicionando...")
            alter_query = text("ALTER TABLE action_plan_items ADD COLUMN order_index INTEGER;")
            db_session.execute(alter_query)
            db_session.commit()
            logger.info("✅ Coluna 'order_index' adicionada com sucesso!")
            
    except Exception as e:
        logger.error(f"❌ Migração Falhou: {e}")
        db_session.rollback()
    finally:
        db_session.close()

if __name__ == "__main__":
    add_order_column()
