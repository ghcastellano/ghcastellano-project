
import sys
import os
import logging

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migration_app_config")

from sqlalchemy import text

def create_app_config_table():
    """
    Cria a tabela AppConfig usando Raw SQL para garantir que ela existe.
    """
    try:
        # Importar usando contexto da aplicação
        from src.app import app
        from src import database
        
        with app.app_context():
            logger.info("🔌 Inicializando contexto da aplicação...")
            
            # Garantir engine inicializado
            if database.engine is None:
                logger.info("Inicializando Database para Migração...")
                database.init_db()
            
            if database.engine:
                logger.info("🔨 Executando CREATE TABLE IF NOT EXISTS via Raw SQL...")
                with database.engine.connect() as conn:
                    # Criar tabela
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS app_config (
                            key VARCHAR PRIMARY KEY,
                            value VARCHAR,
                            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                        );
                    """))
                    conn.commit()
                logger.info("✅ Tabela AppConfig Verificada/Criada via Raw SQL.")
            else:
                logger.error("❌ Falha ao inicializar Database Engine.")
                raise ConnectionError("Database Engine is None")
                
    except Exception as e:
        logger.error(f"❌ Erro na Migração: {e}")
        raise e

if __name__ == "__main__":
    create_app_config_table()

