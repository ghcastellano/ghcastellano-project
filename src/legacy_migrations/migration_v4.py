import logging
from sqlalchemy import create_engine, text
from src.config import config
from src.database import normalize_database_url

logger = logging.getLogger("migration_v4")

def run_migration_v4():
    """
    Migration V4:
    1. Create 'consultant_establishments' table.
    2. Make 'establishments.company_id' nullable (Decoupling).
    3. Migrate data from 'users.establishment_id' to M2M table.
    4. Drop 'users.establishment_id' column (Cleanup).
    """
    database_url = normalize_database_url(config.DATABASE_URL)
    if not database_url:
        logger.error("❌ DATABASE_URL not found.")
        return

    try:
        engine = create_engine(database_url)
        with engine.connect() as conn:
            logger.info("🔄 Checking/Running Database Migration V4 (M2M Consultant-Establishment)...")
            
            # 1. Create Association Table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS consultant_establishments (
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    establishment_id UUID NOT NULL REFERENCES establishments(id) ON DELETE CASCADE,
                    PRIMARY KEY (user_id, establishment_id)
                );
            """))
            conn.commit()
            
            # 2. Decouple Company from Establishment (company_id Nullable)
            try:
                conn.execute(text("ALTER TABLE establishments ALTER COLUMN company_id DROP NOT NULL;"))
                conn.commit()
            except Exception as e:
                logger.warning(f"Note: Could not drop not null from est.company_id (might be ok): {e}")

            # 3. Data Migration (1:1 -> M2M)
            # Find users with establishment_id set
            try:
                # Check if column exists first to avoid crash if re-running after drop
                check_col = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='users' AND column_name='establishment_id';"))
                if check_col.fetchone():
                    logger.info("Migrating existing User->Est assignments to M2M...")
                    conn.execute(text("""
                        INSERT INTO consultant_establishments (user_id, establishment_id)
                        SELECT id, establishment_id FROM users 
                        WHERE establishment_id IS NOT NULL
                        ON CONFLICT DO NOTHING;
                    """))
                    conn.commit()
                    logger.info("✅ Data migration to M2M completed.")
                    
                    # 4. Drop old column 
                    # conn.execute(text("ALTER TABLE users DROP COLUMN establishment_id;"))
                    # conn.commit()
                    # logger.info("✅ Dropped users.establishment_id column.")
                else:
                    logger.info("ℹ️ Column users.establishment_id already dropped or not found.")
                    
            except Exception as e:
                logger.error(f"⚠️ Error migrating user data: {e}")
                conn.rollback()
            
            logger.info("✅ Database Migration V4 Checked/Applied.")
            
    except Exception as e:
        logger.error(f"⚠️ Migration V4 Error: {e}")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    run_migration_v4()
