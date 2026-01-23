import sys
import os
sys.path.append(os.getcwd())

from dotenv import load_dotenv
load_dotenv()

from src import database
from src.database import init_db
from src.models_db import Inspection, ActionPlan, ActionPlanItem

def check_estoque():
    init_db()
    db_session = database.db_session
    plans = db_session.query(ActionPlan).all()
    print(f"Total Plans: {len(plans)}")
    
    for plan in plans:
        print(f"\nPlan ID: {plan.id} (Inspection: {plan.inspection_id})")
        items = db_session.query(ActionPlanItem).filter_by(action_plan_id=plan.id).all()
        print(f"Total Items: {len(items)}")
        
        has_estoque = False
        for item in items:
            area = item.sector or item.nome_area or "N/A"
            if 'stoque' in area or 'epósito' in area:
                has_estoque = True
                print(f"  Found Item: {item.id}")
                print(f"    Area: '{area}'")
                print(f"    Desc: {item.problem_description[:30]}...")
                print(f"    Status: {item.status}")
                print(f"    Orig Status: {item.original_status}")
                print(f"    Score: {item.original_score}")
        
        if not has_estoque:
            print("  ❌ No items found for 'Estoque' or 'Depósito' in this plan.")

if __name__ == "__main__":
    check_estoque()
