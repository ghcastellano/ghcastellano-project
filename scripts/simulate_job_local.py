import sys
import os
import uuid
import logging
from datetime import datetime, date
from unittest.mock import MagicMock, patch

# Adjust path to include src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock structlog to handle kwargs
class MockLogger:
    def info(self, msg, **kwargs):
        print(f"[LOG:INFO] {msg} {kwargs}")
    def error(self, msg, **kwargs):
        print(f"[LOG:ERROR] {msg} {kwargs}")
    def warning(self, msg, **kwargs):
        print(f"[LOG:WARN] {msg} {kwargs}")
    def debug(self, msg, **kwargs):
        print(f"[LOG:DEBUG] {msg} {kwargs}")
    def bind(self, **kwargs):
        return self

sys.modules['structlog'] = MagicMock()
sys.modules['structlog'].get_logger.return_value = MockLogger()

# Mock pypdf and weasyprint (to avoid dependency issues in restricted env)
sys.modules['pypdf'] = MagicMock()
sys.modules['weasyprint'] = MagicMock()

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("simulation")

# Import App Modules
from src.models_db import Job, JobStatus, UserRole
from src import database
from src.services.job_processor import job_processor
from src.services.processor import processor_service, ProcessorService

def run_simulation():
    print("🚀 Starting Job Processing Simulation...")

    # 1. Setup Mock Data
    file_id = "test-file-id"
    filename = "Relatorio_Teste.pdf"
    
    # Mock Drive Service
    processor_service.drive_service = MagicMock()
    processor_service.drive_service.download_file.return_value = b"Fake PDF Content"
    processor_service.drive_service.upload_file.return_value = ("new-id", "http://fake-link.com")
    
    # Mock pypdf behavior specifically for the extraction call
    # from unittest.mock import MagicMock # Removed redundant import
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "RELATORIO VISTORIA TESTE CONTEUDO"
    
    mock_reader = MagicMock()
    mock_reader.pages = [mock_page]
    
    # We need to patch the pypdf module instance that processor imported, 
    # OR since we mocked sys.modules['pypdf'], we just configure that mock.
    sys.modules['pypdf'].PdfReader.return_value = mock_reader

    # Mock OpenAI
    mock_openai_response = MagicMock()
    # Mocking the parsed object structure
    # Expected: RelatorioInspecao(estabelecimento=..., nao_conformidades=[...])
    
    # Create valid mock Pydantic model structure
    from pydantic import BaseModel
    from typing import List, Optional
    
    class AcaoCorretiva(BaseModel):
        descricao: str
        prioridade: str
        prazo_sugerido: str
        
    class NaoConformidade(BaseModel):
        item: str
        descricao: str
        legislacao_relacionada: Optional[str] = None
        acoes_corretivas: List[AcaoCorretiva]
        status_item: str
        
    class RelatorioInspecao(BaseModel):
        estabelecimento: str
        data_inspecao: str
        pontuacao_geral: int
        nao_conformidades: List[NaoConformidade]
        resumo_geral: str
        
    mock_data = RelatorioInspecao(
        estabelecimento="Padaria Tio Joao",
        data_inspecao="20/12/2025",
        pontuacao_geral=85,
        resumo_geral="Bom estado geral, apenas ajustes menores.",
        nao_conformidades=[
            NaoConformidade(
                item="Higiene Pessoal",
                descricao="Funcionário sem touca.",
                legislacao_relacionada="RDC 216",
                status_item="Não Conforme",
                acoes_corretivas=[
                    AcaoCorretiva(descricao="Usar touca.", prioridade="Alta", prazo_sugerido="Imediato")
                ]
            )
        ]
    )
    
    processor_service.client = MagicMock()
    processor_service.client.beta.chat.completions.parse.return_value.choices = [
        MagicMock(message=MagicMock(parsed=mock_data))
    ]
    # Mock usage
    processor_service.client.beta.chat.completions.parse.return_value.usage = MagicMock(
        prompt_tokens=100, completion_tokens=50, total_tokens=150
    )

    # 2. Setup Database (In-Memory or Local? We use the configured one but verify session)
    # We must ensure we have a valid session context
    # If using local sqlite from config, this handles it.
    
    session = database.db_session
    
    # Create Dummy context (Company)
    # We won't create a real Company in DB to strictly avoid side effects on prod DB if url is set.
    # BUT we want to test DB save.
    # We can mock the session ADD/COMMIT to see if they are called.
    
    # If we want to simulate REAL saving, we need a test DB.
    # Given the constraint, Mocking the session commands is safer to prove logic passes.
    
    original_session = database.db_session
    mock_session = MagicMock()
    database.db_session = MagicMock(return_value=mock_session) # When called as constructor
    # Also patch the global session proxy if used directly
    
    # However, src.services.processor line 231 uses `session = database.db_session()`
    
    print("🧪 Simulating Job...")
    
    # Create Job Object (in memory)
    job = Job(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        type="PROCESS_REPORT",
        status=JobStatus.PENDING,
        input_payload={'file_id': file_id, 'filename': filename},
        created_at=datetime.utcnow()
    )
    
    try:
        # EXECUTE
        job_processor.process_job(job)
        
        # VERIFY
        print("\n✅ Verification Results:")
        
        # 1. Check Job Status
        if job.status == JobStatus.COMPLETED:
            print("   [PASS] Job Status set to COMPLETED")
        else:
            print(f"   [FAIL] Job Status is {job.status}. Error: {job.error_log}")
            
        # 2. Check DB Interaction
        # We expect session.add to be called for Inspection, ActionPlan, ActionPlanItem
        # Check call args
        calls = mock_session.add.call_args_list
        print(f"   [INFO] DB Add calls: {len(calls)}")
        
        inspection_saved = False
        plan_saved = False
        items_saved = 0
        
        from src.models_db import Inspection, ActionPlan, ActionPlanItem
        
        for call in calls:
            obj = call[0][0] # First arg
            if isinstance(obj, Inspection):
                inspection_saved = True
                print("   [PASS] Inspection object created")
            elif isinstance(obj, ActionPlan):
                plan_saved = True
                print("   [PASS] ActionPlan object created")
            elif isinstance(obj, ActionPlanItem):
                items_saved += 1
                
        if items_saved == 1:
            print("   [PASS] 1 ActionPlanItem created")
        else:
            print(f"   [FAIL] Expected 1 item, got {items_saved}")
            
        if inspection_saved and plan_saved and items_saved > 0:
            print("\n🎉 SUCCESS: Simulation passed locally! Logic is sound.")
        else:
            print("\n⚠️ PARTIAL SUCCESS: Check logs above.")

    except Exception as e:
        print(f"\n❌ FATAL ERROR in Simulation: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_simulation()
