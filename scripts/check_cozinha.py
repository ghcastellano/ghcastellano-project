import sys
import os
sys.path.append(os.getcwd())

from dotenv import load_dotenv
load_dotenv()

from src import database
from src.database import init_db
from src.models_db import Inspection, ActionPlan, ActionPlanItem

def check_cozinha():
    init_db()
    db_session = database.db_session
    
    # Get the plan
    plan = db_session.query(ActionPlan).first()
    if not plan:
        print("No plan found.")
        return

    print(f"\nChecking items for Plan {plan.id}...")
    
    # Filter for Cozinha
    items = db_session.query(ActionPlanItem).filter_by(action_plan_id=plan.id).all()
    
    cozinha_items = [i for i in items if 'Cozinha' in (i.sector or "") or 'Manipulação' in (i.sector or "")]
    
    print(f"Total items in Cozinha: {len(cozinha_items)}")
    
    print(f"{'ID':<5} | {'Status':<15} | {'Orig Status':<20} | {'Score':<5} | {'Item':<30}")
    print("-" * 100)
    
    for i in cozinha_items:
        desc = i.item_verificado or ""
        print(f"{str(i.id)[:5]:<5} | {str(i.status)[:15]} | {str(i.original_status)[:20]} | {str(i.original_score):<5} | {desc[:30]}")
        
        # Simulate Filter Logic
        is_compliant = False
        st = (i.original_status or "").upper()
        if 'CONFORME' in st and 'NÃO' not in st and 'PARCIAL' not in st:
            is_compliant = True
        if st == 'COMPLIANT' or st == 'RESOLVED':
            is_compliant = True
        if i.original_score is not None and i.original_score >= 10:
            is_compliant = True
            
        if is_compliant:
            print(f"   [FILTERED] Would be hidden by filter logic. (Status: {st}, Score: {i.original_score})")

if __name__ == "__main__":
    check_cozinha()
