import sys
import os
import uuid

# MONKEYPATCH JSONB and UUID for SQLite Support in Tests (MUST BE BEFORE IMPORTS)
import sqlalchemy
from sqlalchemy import JSON, String, TypeDecorator

class MockUUID(TypeDecorator):
    impl = String
    cache_ok = True
    
    def __init__(self, *args, **kwargs):
        # Consume postgres specific args
        kwargs.pop('as_uuid', None)
        super().__init__(*args, **kwargs)

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        return str(value)

try:
    from sqlalchemy.dialects import postgresql
    postgresql.JSONB = JSON
    postgresql.UUID = MockUUID
except ImportError:
    pass

from src import database, config
from src.models_db import Job, JobStatus, Company, Base

def simulate_job_flow():
    # MOCK CONFIG
    db_path = 'debug_test.db'
    if os.path.exists(db_path): os.remove(db_path)
    config.config.DATABASE_URL = f'sqlite:///{db_path}'
    
    # Initialize DB (Engine only, metadata handled below)
    from src.database import init_db
    init_db()
    
    # Create tables in memory
    print(f"Tables in metadata: {Base.metadata.tables.keys()}")
    Base.metadata.create_all(bind=database.engine)
    print("✅ Tables created in SQLite file.")
    
    session = database.db_session
    
    print("--- Checking Job Robustness & Costs ---")
    
    # 1. Create a Company
    comp = Company(id=uuid.uuid4(), name="Ambev")
    session.add(comp)
    session.commit()
    
    # 2. Simulate Job with Metrics
    job = Job(
        id=uuid.uuid4(),
        company_id=comp.id,
        type="PROCESS_REPORT",
        status=JobStatus.PROCESSING,
        input_payload={'filename': 'vitoria.pdf', 'establishment_id': None},
        cost_tokens_input=1000,
        cost_tokens_output=500,
        cost_input_usd=0.00015,
        cost_output_usd=0.00030
    )
    session.add(job)
    session.commit()
    print(f"✅ Job Created with costs. ID: {job.id}")
    
    # 3. Verify Costs in Query
    from src.db_queries import get_pending_jobs
    jobs = get_pending_jobs(allow_all=True)
    job_data = next((j for j in jobs if j['id'] == str(job.id)), None)
    
    if job_data:
        print(f"✅ Job found in query. Costs: In=${job_data.get('cost_input', 0):.6f}, Out=${job_data.get('cost_output', 0):.6f}")
    else:
        print("❌ Job NOT found in query!")

    # 4. Simulate ProcessorService Save Logic (Manual call to test Upsert)
    from src.services.processor import processor_service
    from unittest.mock import MagicMock
    
    # Mock report data (Pydantic style)
    mock_report = MagicMock()
    mock_report.estabelecimento = "Padaria Joana"
    mock_report.nao_conformidades = []
    mock_report.model_dump.return_value = {"test": 1}
    
    file_id = "drive_123"
    
    print("\n--- Testing Inspection Upsert ---")
    # First save
    processor_service._save_to_db_logic(mock_report, file_id, "test.pdf", "link1", "hash1", company_id=comp.id)
    print("✅ First Save OK")
    
    # Second save (Same File ID)
    processor_service._save_to_db_logic(mock_report, file_id, "test.pdf", "link2", "hash2", company_id=comp.id)
    print("✅ Second Save (Upsert) OK - No Unique Constraint Error")
    
    from src.models_db import Inspection
    count = session.query(Inspection).filter_by(drive_file_id=file_id).count()
    print(f"📊 Inspections for {file_id}: {count} (Expected: 1)")


if __name__ == "__main__":
    simulate_job_flow()
