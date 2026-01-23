import sys
import os
sys.path.append(os.getcwd())

from dotenv import load_dotenv
load_dotenv()

from src import database
from src.database import init_db
from src.models_db import Inspection, Job

def diagnose_raw_and_status():
    init_db()
    db_session = database.db_session
    
    # 1. Check Inspection Raw Data
    inspection = db_session.query(Inspection).first()
    if inspection:
        print(f"\n🔍 Inspection ID: {inspection.id}")
        print(f"Status: {inspection.status}")
        
        raw = inspection.ai_raw_response or {}
        areas = raw.get('areas_inspecionadas', [])
        print(f"Raw Areas found in JSON ({len(areas)}):")
        found_estoque = False
        for area in areas:
            name = area.get('nome_area') or area.get('name')
            print(f" - {name} (Items: {len(area.get('itens', []))})")
            if 'stoque' in str(name):
                found_estoque = True
                # Print explicit items for Estoque
                for item in area.get('itens', []):
                    print(f"   > Item: {item.get('item_verificado')[:40]}... (Status: {item.get('status')})")

        if not found_estoque:
            print("❌ 'Estoque' NOT FOUND in ai_raw_response JSON.")
        else:
            print("✅ 'Estoque' FOUND in ai_raw_response JSON.")

    else:
        print("❌ No Inspection found.")

    # 2. Check Jobs
    print("\n🔍 Checking Jobs:")
    jobs = db_session.query(Job).all()
    for job in jobs:
        print(f"Job ID: {job.id} | Status: {job.status} | Type: {job.type}")
        if job.result and 'error' in str(job.result).lower():
            print(f"  ⚠️ Error in result: {job.result}")

if __name__ == "__main__":
    diagnose_raw_and_status()
