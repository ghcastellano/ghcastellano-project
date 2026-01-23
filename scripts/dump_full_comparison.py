import sys
import os
import json
sys.path.append(os.getcwd())

from dotenv import load_dotenv
load_dotenv()

from src import database
from src.database import init_db
from src.models_db import Inspection, ActionPlan, ActionPlanItem

def compare():
    init_db()
    db = database.db_session
    
    insp = db.query(Inspection).first()
    plan = db.query(ActionPlan).first()
    
    if not insp or not plan:
        print("Missing data.")
        return
        
    print(f"Inspection ID: {insp.id}")
    print(f"ActionPlan ID: {plan.id} (Linked to Insp: {plan.inspection_id})")
    print(f"Match: {insp.id == plan.inspection_id}\n")
    
    # Raw Data
    raw = insp.ai_raw_response or {}
    print("--- RAW JSON DATA ---")
    raw_areas = raw.get('areas_inspecionadas', [])
    for area in raw_areas:
        name = area.get('nome_area')
        items = area.get('itens', [])
        print(f"Area: {name} (Count: {len(items)})")
        if 'Cozinha' in name or 'Estoque' in name:
            for item in items:
                print(f"  RAW > {item.get('item_verificado')[:40]}... (Pontuacao: {item.get('pontuacao')})")

    # DB Items
    print("\n--- DB ACTION ITEMS ---")
    db_items = db.query(ActionPlanItem).filter_by(action_plan_id=plan.id).all()
    
    # Group by Sector
    from collections import defaultdict
    by_sec = defaultdict(list)
    for i in db_items:
        by_sec[i.sector].append(i)
        
    for sec, ilist in by_sec.items():
        if 'Cozinha' in sec or 'Estoque' in sec:
            print(f"Sector: {sec} (Count: {len(ilist)})")
            for i in ilist:
                print(f"  DB  > {i.problem_description[:40]}... (Score: {i.original_score})")

if __name__ == "__main__":
    compare()
