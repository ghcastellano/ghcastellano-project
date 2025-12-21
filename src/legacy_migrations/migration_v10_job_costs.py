import logging
from sqlalchemy import create_engine, text
from src.config import config
from src.database import normalize_database_url

logger = logging.getLogger("migration_v10")

def run_migration_v10():
    database_url = normalize_database_url(config.DATABASE_URL)
    if not database_url:
        logger.error("❌ DATABASE_URL not found.")
        return

    try:
        engine = create_engine(database_url)
        with engine.connect() as conn:
            logger.info("🔄 Rodando Migração V10 (Custos de Jobs)...")
            
            # Adiciona colunas de custo em USD e BRL se não existirem
            conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS cost_input_usd DOUBLE PRECISION DEFAULT 0.0;"))
            conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS cost_output_usd DOUBLE PRECISION DEFAULT 0.0;"))
            conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS cost_input_brl DOUBLE PRECISION DEFAULT 0.0;"))
            conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS cost_output_brl DOUBLE PRECISION DEFAULT 0.0;"))
            
            conn.commit()
            logger.info("✅ Migração V10 (Custos de Jobs) finalizada.")
    except Exception as e:
        logger.error(f"❌ Erro na Migração V10: {e}")
        # Em produção, não queremos que uma migração falha pare o app se for apenas coluna extra opcional
        # Mas aqui é importante.
