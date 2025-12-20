import logging
from sqlalchemy import create_engine, text
from src.config import config
from src.database import normalize_database_url

logger = logging.getLogger("migration_v9")

def run_migration_v9():
    """
    Migração V9 (Sincronização Final):
    Garante que TODOS os modelos definidos em models_db.py tenham suas colunas correspondentes no Neon.
    Isso é uma correção de 'Drift' (desvio de schema) abrangente.
    """
    database_url = normalize_database_url(config.DATABASE_URL)
    if not database_url:
        logger.error("❌ DATABASE_URL not found.")
        return

    try:
        engine = create_engine(database_url)
        with engine.connect() as conn:
            logger.info("🔄 Running Migration V9 (Schema Synchronization)...")

            # 1. USERS Table (Ensure profile fields)
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS name VARCHAR;"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS whatsapp VARCHAR;"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;"))
            
            # 2. INSPECTIONS Table (Ensure AI fields)
            conn.execute(text("ALTER TABLE inspections ADD COLUMN IF NOT EXISTS ai_raw_response JSONB;"))
            conn.execute(text("ALTER TABLE inspections ADD COLUMN IF NOT EXISTS drive_web_link VARCHAR;"))
            
            # 3. JOBS Table (Fix Nullability Conflict)
            # Model says company_id is Optional, Migration V8 made it NOT NULL.
            # We relax it to match Model.
            try:
                conn.execute(text("ALTER TABLE jobs ALTER COLUMN company_id DROP NOT NULL;"))
            except Exception as e:
                logger.warning(f"Note: jobs.company_id nullability change skipped: {e}")

            # 4. ACTION PLANS (Ensure Tables Exist)
            # These might have been missed if V1-V3 were partial.
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS action_plans (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    inspection_id UUID NOT NULL REFERENCES inspections(id),
                    final_pdf_drive_id VARCHAR,
                    final_pdf_public_link VARCHAR,
                    approved_by_id UUID REFERENCES users(id),
                    approved_at TIMESTAMP WITH TIME ZONE
                );
            """))
            # Unique constraint on inspection_id
            try:
                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_action_plans_inspection_id ON action_plans(inspection_id);"))
            except Exception:
                pass

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS action_plan_items (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    action_plan_id UUID NOT NULL REFERENCES action_plans(id),
                    problem_description TEXT NOT NULL,
                    corrective_action TEXT NOT NULL,
                    legal_basis TEXT,
                    deadline_date DATE,
                    severity VARCHAR DEFAULT 'MEDIUM',
                    status VARCHAR DEFAULT 'OPEN',
                    manager_notes TEXT
                );
            """))

            # 5. ESTABLISHMENTS (Ensure code/drive_id)
            conn.execute(text("ALTER TABLE establishments ADD COLUMN IF NOT EXISTS code VARCHAR;"))
            conn.execute(text("ALTER TABLE establishments ADD COLUMN IF NOT EXISTS drive_folder_id VARCHAR;"))

            conn.commit()
            logger.info("✅ Migration V9 (Sync) Applied Successfully.")

    except Exception as e:
        logger.error(f"❌ Migration V9 Error: {e}")
        # Don't re-raise to avoid blocking deploy, log error
