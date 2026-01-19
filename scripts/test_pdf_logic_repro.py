
import sys
import os
import uuid
from datetime import datetime, date

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.models_db import ActionPlanItem, ActionPlanItemStatus

# Mock classes to simulate SQLAlchemy objects without DB connection (for fast unit testing logic)
class MockEstablishment:
    name = "Test Establishment"

class MockInspection:
    establishment = MockEstablishment()
    created_at = datetime.now()
    drive_file_id = "mock_file_id"
    ai_raw_response = {"summary": "Mock Summary", "score": 100, "max_score": 100, "percentage": 100}

class MockActionPlan:
    summary_text = "Mock Plan Summary"
    strengths_text = "Strong points"
    stats_json = {"score": 95, "max_score": 100, "percentage": 95}
    items = []

def test_pdf_data_mapping():
    print("Testing PDF Data Mapping...")
    
    # Create Mock Data
    plan = MockActionPlan()
    item = ActionPlanItem(
        id=uuid.uuid4(),
        problem_description="Problem Description", # This is the DB column
        corrective_action="Fix it",
        legal_basis="Law 123", # DB column is legal_basis
        deadline_date=date.today(),
        status=ActionPlanItemStatus.OPEN,
        sector="Kitchen"
    )
    # The route iterates plan.items
    # In a real DB query, we get instances of ActionPlanItem.
    
    # Let's simulate the mapping loop from app.py
    try:
        data_item = {
            'item_verificado': item.item_verificado if hasattr(item, 'item_verificado') else "MISSING", 
             # The route expects item.item_verificado to exist (Attribute access)
        }
        print(f"Mapped item_verificado: {data_item['item_verificado']}")
    except AttributeError as e:
        print(f"❌ AttributeError accessing item_verificado: {e}")

    try:
        val = item.fundamento_legal if hasattr(item, 'fundamento_legal') else "MISSING"
        print(f"Mapped fundamento_legal: {val}")
    except AttributeError as e:
        print(f"❌ AttributeError accessing fundamento_legal: {e}")
        
    # Check what the actual columns are
    print(f"Actual problem_description: {item.problem_description}")
    print(f"Actual legal_basis: {item.legal_basis}")

if __name__ == "__main__":
    test_pdf_data_mapping()
