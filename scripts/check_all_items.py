import sys
import os
from collections import defaultdict
sys.path.append(os.getcwd())

from dotenv import load_dotenv
load_dotenv()

from src import database
from src.database import init_db
from src.models_db import Inspection, ActionPlan, ActionPlanItem

def list_all_items():
    init_db()
    db_session = database.db_session
    
    plan = db_session.query(ActionPlan).first()
    if not plan:
        print("No plan found.")
        return

    items = db_session.query(ActionPlanItem).filter_by(action_plan_id=plan.id).all()
    print(f"Total Plan Items: {len(items)}")
    
    by_sector = defaultdict(list)
    for i in items:
        # Use sector attribute properly
        sec = i.sector or "None"
        by_sector[sec].append(i)
        
    for sector, i_list in by_sector.items():
        print(f"\n📂 Sector: {sector} (Count: {len(i_list)})")
        for item in i_list:
            desc = (item.problem_description or "")
            print(f"  - [{item.status}] {str(item.original_score):<4} : {desc[:60]}...")

if __name__ == "__main__":
    list_all_items()
