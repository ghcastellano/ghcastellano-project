import logging
from sqlalchemy import text
from src.database import get_db

logger = logging.getLogger("migration_v16")

def upgrade(db_session):
    """
    Adds 'evidence_image_url' column to 'action_plan_items' table.
    """
    try:
        # We need a connection object for raw SQL DDL
        # db_session might be a Session object.
        # Use session.execute(text(...))
        
        logger.info("Verificando se coluna 'evidence_image_url' existe em 'action_plan_items'...")
        
        # Check if column exists
        check_query = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='action_plan_items' AND column_name='evidence_image_url';
        """)
        
        result = db_session.execute(check_query).fetchone()
        
        if not result:
            logger.info("Criando coluna 'evidence_image_url'...")
            # SQLite uses ADD COLUMN, Postgres too.
            db_session.execute(text("ALTER TABLE action_plan_items ADD COLUMN evidence_image_url VARCHAR;"))
            db_session.commit()
            logger.info("✅ Coluna 'evidence_image_url' criada com sucesso.")
        else:
            logger.info("ℹ️ Coluna 'evidence_image_url' já existe.")
            
    except Exception as e:
        logger.error(f"❌ Erro na Migração V16: {e}")
        db_session.rollback()
