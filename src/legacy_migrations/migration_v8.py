from sqlalchemy import text
from src.database import get_db

def run_migration_v8():
    db = next(get_db())
    conn = db.connection()
    try:
        # Create Type Enum for JobStatus manually if Postgres < 12 or if SQLalchemy doesn't auto-create in raw sql mode efficiently
        # But we are using raw sql for simplicity in these scripts
        
        # Check if table exists
        result = conn.execute(text("SELECT to_regclass('public.jobs')"))
        if result.scalar():
            print("⚠️ Table 'jobs' already exists. Skipping creation.")
            return

        print("🔄 Creating 'jobs' table...")
        conn.execute(text("""
            CREATE TABLE jobs (
                id UUID PRIMARY KEY,
                company_id UUID NOT NULL REFERENCES companies(id),
                type VARCHAR NOT NULL,
                status VARCHAR NOT NULL DEFAULT 'PENDING',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc', now()),
                finished_at TIMESTAMP WITH TIME ZONE,
                cost_tokens_input INTEGER DEFAULT 0,
                cost_tokens_output INTEGER DEFAULT 0,
                execution_time_seconds FLOAT DEFAULT 0.0,
                api_calls_count INTEGER DEFAULT 0,
                attempts INTEGER DEFAULT 0,
                input_payload JSONB,
                result_payload JSONB,
                error_log TEXT
            );
        """))
        
        # Indexes
        print("🔄 Creating indexes for 'jobs'...")
        conn.execute(text("CREATE INDEX idx_jobs_company_id ON jobs (company_id);"))
        conn.execute(text("CREATE INDEX idx_jobs_status ON jobs (status);"))
        
        db.commit()
        print("✅ Migration V8 (Jobs Table) applied successfully.")
        
    except Exception as e:
        print(f"❌ Error applying Migration V8: {e}")
        db.rollback()
    finally:
        # get_db is a generator, next() gets the session. It usually doesn't close on yield if scoped.
        # But we can explicitly close/commit here.
        db.close()
