import os
import sys
import logging
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Carrega variáveis de ambiente ANTES de importar src.database
load_dotenv()

# Add repo root to path (permite `import src.*`)
sys.path.append(os.getcwd())

from src.config import config
from src.database import normalize_database_url

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migration_v3")

def run_migration_v3():
    database_url = normalize_database_url(config.DATABASE_URL)
    if not database_url:
        logger.error("❌ DATABASE_URL not found.")
        return

    engine = create_engine(database_url)
    
    with engine.connect() as conn:
        logger.info("🔄 Starting Migration V3 (Company/Establishment)...")
        
        # 1. Create Tables: companies, establishments
        try:
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
            logger.info("✅ Tables 'companies' and 'establishments' created.")
        except Exception as e:
            logger.error(f"⚠️ Error creating tables: {e}")
            conn.rollback()
            
        # 2. Update Users Table
        try:
            # Add columns
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS company_id UUID REFERENCES companies(id);"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS establishment_id UUID REFERENCES establishments(id);"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN DEFAULT FALSE;"))
            conn.commit()
            logger.info("✅ Users table updated columns.")
        except Exception as e:
            logger.error(f"⚠️ Error updating users table: {e}")
            conn.rollback()

        # 3. Update Inspections Table
        try:
            conn.execute(text("ALTER TABLE inspections ADD COLUMN IF NOT EXISTS establishment_id UUID REFERENCES establishments(id);"))
            # Make client_id optional if it was not null (ALTER COLUMN ... DROP NOT NULL) - Postgres specific
            try:
                conn.execute(text("ALTER TABLE inspections ALTER COLUMN client_id DROP NOT NULL;"))
            except:
                pass # Might already be nullable
            conn.commit()
            logger.info("✅ Inspections table updated.")
        except Exception as e:
            logger.error(f"⚠️ Error updating inspections table: {e}")
            conn.rollback()

        # 4. Data Migration (Client -> Company+Establishment)
        # Assuming 1 Client = 1 Company + 1 Establishment for now
        try:
            # Check if any clients exist
            result = conn.execute(text("SELECT id, name, cnpj, drive_root_folder_id FROM clients;"))
            clients = result.fetchall()
            
            if clients:
                logger.info(f"🔄 Migrating {len(clients)} clients to Company/Establishment structure...")
                
                for client in clients:
                    c_id, c_name, c_cnpj, c_drive = client
                    
                    # Create Company if not exists (dedup by CNPJ or Name)
                    # For simplicity, we create one Company per Client
                    # Insert Company and return ID
                    res_comp = conn.execute(text("""
                        INSERT INTO companies (name, cnpj) 
                        VALUES (:name, :cnpj)
                        ON CONFLICT (cnpj) DO NOTHING
                        RETURNING id;
                    """), {"name": c_name, "cnpj": c_cnpj})
                    
                    # If ON CONFLICT happened, we need to select the ID
                    company_id_row = res_comp.fetchone()
                    if company_id_row:
                        company_id = company_id_row[0]
                    else:
                         # Fetch existing
                        res_exist = conn.execute(text("SELECT id FROM companies WHERE cnpj = :cnpj"), {"cnpj": c_cnpj})
                        company_id = res_exist.fetchone()[0]

                    # Create Establishment
                    # Use same name and drive folder
                    res_est = conn.execute(text("""
                        INSERT INTO establishments (company_id, name, drive_folder_id)
                        VALUES (:cid, :name, :drive_id)
                        RETURNING id;
                    """), {"cid": company_id, "name": c_name, "drive_id": c_drive})
                    
                    est_id = res_est.fetchone()[0]
                    
                    # Update Inspections linked to this Client to point to new Establishment
                    conn.execute(text("""
                        UPDATE inspections SET establishment_id = :eid WHERE client_id = :cid;
                    """), {"eid": est_id, "cid": c_id})
                    
                    # Update Visits linked to this Client? (Visit has client_id too)
                    # We didn't change Visit model yet in DB (only python), but let's assume Visit needs update if we want consistency.
                    # For now only Inspection is critical.
                    
                    logger.info(f"   -> Migrated Client '{c_name}' to Company IDs {company_id} / Est {est_id}")
                
                conn.commit()
                logger.info("✅ Data migration completed.")
            else:
                logger.info("ℹ️ No clients to migrate.")
                
        except Exception as e:
            logger.error(f"⚠️ Error during data migration: {e}")
            conn.rollback()

    logger.info("🏁 Migration V3 Completed")

if __name__ == "__main__":
    run_migration_v3()
