import sys
import os
from sqlalchemy import create_engine, text

# Force usage of local .env to check if it matches prod expectation
from dotenv import load_dotenv
load_dotenv()

def verify_prod_columns():
    db_url = os.getenv("DATABASE_URL")
    print(f"🔌 Connecting to: {db_url.split('@')[0].split(':')[0]}... (masked)")
    
    engine = create_engine(db_url)
    
    with engine.connect() as conn:
        print("\n🔍 Checking 'establishments' columns:")
        result = conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'establishments'"))
        cols = {row[0]: row[1] for row in result}
        print(cols)
        
        missing = []
        for req in ['responsible_name', 'responsible_email', 'responsible_phone']:
            if req not in cols:
                missing.append(req)
                print(f"❌ MISSING: {req}")
            else:
                print(f"✅ FOUND: {req}")

        print("\n🔍 Checking 'inspections' columns:")
        result_insp = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'inspections'"))
        cols_insp = [row[0] for row in result_insp]
        if 'updated_at' in cols_insp:
            print("✅ FOUND: updated_at")
        else:
            print("❌ MISSING: updated_at")

if __name__ == "__main__":
    verify_prod_columns()
