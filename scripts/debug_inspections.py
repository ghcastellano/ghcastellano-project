
import sys
import os
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src import database
from src.models_db import Inspection, InspectionStatus, Establishment, Company

def list_recent_inspections():
    db = next(database.get_db())
    try:
        print("\n🔍 Listing Inspections for 'Loja 1':")
        # Find establishment 'Loja 1'
        est = db.query(Establishment).filter(Establishment.name == 'Loja 1').first()
        if not est:
            print("❌ Establishment 'Loja 1' not found!")
        else:
            print(f"🏠 Establishment: {est.name} (ID: {est.id}, Company ID: {est.company_id})")
            
            # List Inspections
            inspections = db.query(Inspection).filter(Inspection.establishment_id == est.id).all()
            if not inspections:
                print("   No inspections found for this establishment.")
            for insp in inspections:
                print(f"   📄 ID: {insp.id}")
                print(f"      Status: {insp.status}")
                print(f"      Created At: {insp.created_at}")
                print(f"      File ID: {insp.drive_file_id}")
                print(f"      AI Title: {insp.ai_raw_response.get('titulo') if insp.ai_raw_response else 'N/A'}")
                print("-" * 30)

        print("\n🔍 Listing All Recent Inspections (Last 5):")
        recent = db.query(Inspection).order_by(Inspection.created_at.desc()).limit(5).all()
        for insp in recent:
            est_name = insp.establishment.name if insp.establishment else "None"
            print(f"📄 ID: {insp.id}, Status: {insp.status}, Est: {est_name}, Time: {insp.created_at}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    list_recent_inspections()
