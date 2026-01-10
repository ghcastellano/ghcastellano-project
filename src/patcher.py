
import logging
from sqlalchemy import text
from src.database import engine

logger = logging.getLogger(__name__)

def run_auto_patch():
    """
    Executa patches de schema críticos diretamente via SQL raw.
    Garante que colunas essenciais existam em produção.
    """
    logger.info("🛠️ [AUTO-PATCH] Verificando integridade do schema do banco...")
    
    # Debug SA Email for User
    try:
        import google.auth
        creds, project = google.auth.default()
        if hasattr(creds, 'service_account_email'):
            logger.info(f"📧 SERVICE ACCOUNT EMAIL (SHARE DRIVE WITH THIS): {creds.service_account_email}")
        else:
            logger.info("📧 Não foi possível detectar email da Service Account (Credentials type mismatch).")
    except Exception as e:
        logger.warning(f"📧 Erro ao detectar SA Email: {e}")
    
    patches = [
        # Table: inspections
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP",
        
        # Table: establishments
        "ALTER TABLE establishments ADD COLUMN IF NOT EXISTS responsible_name VARCHAR(255)",
        "ALTER TABLE establishments ADD COLUMN IF NOT EXISTS responsible_email VARCHAR(255)",
        "ALTER TABLE establishments ADD COLUMN IF NOT EXISTS responsible_phone VARCHAR(20)",
        
        # Table: jobs (Just in case)
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS cost_tokens_input INTEGER DEFAULT 0",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS cost_tokens_output INTEGER DEFAULT 0",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS finished_at TIMESTAMP"
    ]
    
    try:
        with engine.connect() as conn:
            for sql in patches:
                try:
                    conn.execute(text(sql))
                    logger.info(f"✅ [AUTO-PATCH] Executado: {sql[:50]}...")
                except Exception as e:
                    logger.warning(f"⚠️ [AUTO-PATCH] Falha ao executar '{sql[:30]}...': {e}")
            conn.commit()
            logger.info("🏁 [AUTO-PATCH] Concluído.")
    except Exception as e:
        logger.error(f"❌ [AUTO-PATCH] Erro fatal conexão DB: {e}")

