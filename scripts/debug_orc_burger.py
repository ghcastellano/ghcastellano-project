import sys
import os
sys.path.append(os.getcwd())
from src.app import app
from src.database import db_session
from src.models_db import Inspection, Job, ActionPlan
from sqlalchemy import text

def inspect_data():
    with app.app_context():
        print("--- SEARCHING FOR INSPECTION ---")
        # Search for ORC BURGER
        # We can try to match by name in establishment
        # Or look for recent inspections
        
        # Try finding by name in establishment name linked to inspection
        # This is harder via ORM if we don't know the exact name, so let's list recent ones.
        
        inspections = db_session.query(Inspection).order_by(Inspection.created_at.desc()).limit(5).all()
        target_insp = None
        
        for insp in inspections:
            name = insp.establishment.name if insp.establishment else "N/A"
            print(f"Checking Insp ID: {insp.id} | Place: {name} | Created: {insp.created_at}")
            if "ORC" in name.upper() or "BURGER" in name.upper():
                target_insp = insp
                # break # Keep listing just in case
        
        if target_insp:
            print(f"\n--- TARGET FOUND: {target_insp.establishment.name} ---")
            print(f"ID: {target_insp.id}")
            print(f"Drive File ID: {target_insp.drive_file_id}")
            
            # Check JSONs
            raw = target_insp.ai_raw_response or {}
            print(f"\n[AI RAW RESPONSE KEYS]: {list(raw.keys())}")
            print(f"Summary keys present? 'summary': {'summary' in raw}, 'resumo_geral': {'resumo_geral' in raw}")
            if 'summary' in raw: print(f"Summary Start: {str(raw['summary'])[:50]}...")
            if 'resumo_geral' in raw: print(f"Resumo Geral Start: {str(raw['resumo_geral'])[:50]}...")
            
            # Check Action Plan stats
            if target_insp.action_plan:
                stats = target_insp.action_plan.stats_json or {}
                print(f"\n[ACTION PLAN STATS KEYS]: {list(stats.keys())}")
                print(f"percentage: {stats.get('percentage')}")
                print(f"aproveitamento_geral: {stats.get('aproveitamento_geral')}")
                
                # Check Areas
                areas = stats.get('areas_inspecionadas', []) or stats.get('areas', [])
                print(f"\n[AREAS FOUND]: {len(areas)}")
                if areas:
                    first = areas[0]
                    print(f"First Area Keys: {list(first.keys())}")
                    print(f"First Area Score: {first.get('score')} / {first.get('max_score')}")
                    print(f"First Area Pontuacao: {first.get('pontuacao_obtida')} / {first.get('pontuacao_maxima')}")
                    
                    # Check items in area
                    items = first.get('itens', [])
                    print(f"Items in first area: {len(items)}")
                    if items:
                        print(f"First Item: {items[0]}")
            else:
                print("No Action Plan linked.")
                
        else:
            print("Target 'ORC BURGER' not found in recent inspections.")

        print("\n--- SEARCHING FOR STUCK JOB ---")
        job = db_session.query(Job).filter(text("input_payload->>'filename' LIKE '%quest_resposta (1).pdf%'")).first()
        if job:
            print(f"Job Found: {job.id}")
            print(f"Status: {job.status}")
            print(f"Stage: {job.stage}")
            print(f"Message: {job.message}")
            print(f"Created: {job.created_at}")
        else:
            print("Job 'quest_resposta (1).pdf' not found via strict search. Trying loose...")
            jobs = db_session.query(Job).order_by(Job.created_at.desc()).limit(10).all()
            for j in jobs:
                payload = j.input_payload or {}
                fname = payload.get('filename', 'N/A')
                if 'quest' in fname.lower():
                    print(f"Potential Match: {fname} | Status: {j.status}")

if __name__ == '__main__':
    inspect_data()
