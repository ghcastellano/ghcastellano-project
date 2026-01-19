
import sys
import os
import inspect

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.models_db import ActionPlanItem

def verify_fields():
    print("🔍 Inspecting ActionPlanItem fields...")
    # Check SQLAlchemy Mapped columns
    if hasattr(ActionPlanItem, 'created_at'):
        print("✅ 'created_at' found in ActionPlanItem.")
    else:
        print("❌ 'created_at' NOT found in ActionPlanItem.")
        
    # List all helpers
    print("Fields:", [key for key in ActionPlanItem.__dict__.keys() if not key.startswith('_')])

if __name__ == "__main__":
    verify_fields()
