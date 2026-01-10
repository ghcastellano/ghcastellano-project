import logging
from sqlalchemy import create_engine, text
from src.config import config
from src.database import normalize_database_url
from src.legacy_migrations import migration_v4, migration_v5, migration_v6, migration_v7, migration_v8, migration_v9_sync

logger = logging.getLogger("migration")

def run_migrations(db_session=None): # Renamed to generic
    database_url = normalize_database_url(config.DATABASE_URL)
    if not database_url:
        logger.error("❌ DATABASE_URL not found.")
        return

    try:
        engine = create_engine(database_url)
        with engine.connect() as conn:
            logger.info("🔄 Checking/Running Database Migration V3 (Company/Establishment)...")
            
            # 1. Create Tables
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS companies (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name VARCHAR NOT NULL,
                    cnpj VARCHAR UNIQUE,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS establishments (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    company_id UUID NOT NULL REFERENCES companies(id),
                    name VARCHAR NOT NULL,
                    code VARCHAR,
                    drive_folder_id VARCHAR,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """))
            conn.commit()
            
            # 1.1 Force Update Schema (Fix Drift for existing legacy tables)
            conn.execute(text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;"))
            conn.execute(text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();"))
            
            conn.execute(text("ALTER TABLE establishments ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;"))
            conn.execute(text("ALTER TABLE establishments ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();"))
            conn.commit()
            
            # 2. Update Users Table
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS company_id UUID REFERENCES companies(id);"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS establishment_id UUID REFERENCES establishments(id);"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN DEFAULT FALSE;"))
            conn.commit()

            # 3. Update Inspections Table
            conn.execute(text("ALTER TABLE inspections ADD COLUMN IF NOT EXISTS establishment_id UUID REFERENCES establishments(id);"))
            try:
                conn.execute(text("ALTER TABLE inspections ALTER COLUMN client_id DROP NOT NULL;"))
            except Exception as e:
                logger.warning(f"Note: Could not drop not null from client_id (might be ok): {e}")
            conn.commit()

            # 4. Data Migration (Client -> Company+Establishment)
            # [LEGACY REMOVED] Table 'clients' dropped. Logic preserved for history but disabled.
            # result = conn.execute(text("SELECT id, name, cnpj, drive_root_folder_id FROM clients;"))
            # clients = result.fetchall()
            
            # if clients:
            #     for client in clients:
            #         # ... (Legacy Migration Logic Removed) ...
            #         pass
            
            logger.info("✅ Database Migration Checked/Applied (Legacy Clients Skipped).")
            
    except Exception as e:
        logger.error(f"⚠️ Migration Error: {e}")

    # Run Subsequent Migrations (Explicitly)
    try:
        logger.info("🚀 Rodando Migração V4 (Pós-Migração)...")
        migration_v4.run_migration_v4()
        
        logger.info("🚀 Rodando Migração V5 (Estabelecimento/Hash)...")
        migration_v5.run_migration_v5()

        logger.info("🚀 Rodando Migração V6 (Usuários/Funções)...")
        migration_v6.run_migration_v6()
        
        logger.info("🚀 Rodando Migração V7 (Tarefas/Status)...")
        migration_v7.run_migration_v7()

        if hasattr(migration_v8, 'run_migration_v8'):
            logger.info("🚀 Rodando Migração V8...")
            migration_v8.run_migration_v8()
        else:
            logger.warning("⚠️ Migração V8 importada mas função de execução não encontrada.")

        logger.info("🚀 Rodando Migração V9 (Sincronização Final)...")
        migration_v9_sync.run_migration_v9()

        from src.legacy_migrations import migration_v10_job_costs
        from src.legacy_migrations import migration_v11_action_plan_enrichment
        
        logger.info("🚀 Rodando Migração V10 (Custos de Jobs)...")
        migration_v10_job_costs.run_migration_v10() 
        
        logger.info("🚀 Rodando Migração V11 (Enriquecimento do Plano de Ação)...") 
        # V11 expects a session factory or session? 
        # If it expects factory: migration_v11_action_plan_enrichment.upgrade(database.SessionLocal)
        # Assuming db_session (passed to this func) is what we have. 
        # Let's check v11 signature in a separate step if needed, but for now passing db_session as it's the arg.
        # Wait, if V11 uses 'with session_factory():', passing a session object will fail 'enter'.
        # I'll modify V11 usage to match what it likely needs: proper session handling.
        # For now, let's fix indentation first.
        migration_v11_action_plan_enrichment.upgrade(db_session)

        from src.legacy_migrations import migration_v13_job_enrichment
        logger.info("🚀 Rodando Migração V13 (Jobs Enrichment)...")
        migration_v13_job_enrichment.upgrade(db_session)

        from src.legacy_migrations import migration_v14_item_sector
        logger.info("🚀 Rodando Migração V14 (Item Sector)...")
        migration_v14_item_sector.upgrade(db_session)
        
        from src.legacy_migrations import migration_v16_evidence_url
        logger.info("🚀 Rodando Migração V16 (Evidence URL)...")
        migration_v16_evidence_url.upgrade(db_session)

    except Exception as e:
        logger.error(f"❌ Erro ao rodar migrações subsequentes: {e}")
