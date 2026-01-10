
import sys
import os
from sqlalchemy import text

sys.path.append(os.getcwd())
from src.app import app
from src.database import engine

def verify():
    with app.app_context():
        with engine.connect() as conn:
            print(f"🔌 Connected to: {engine.url.database} @ {engine.url.host}")
            
            result = conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'establishments';"))
            cols = [row[0] for row in result.fetchall()]
            
            print(f"📊 Columns in 'establishments': {cols}")
            
            if 'responsible_email' in cols:
                print("✅ 'responsible_email' FOUND in Information Schema")
            else:
                print("❌ 'responsible_email' MISSING in Information Schema")
                
        # ORM Check
        from src.models_db import Establishment
        from sqlalchemy.inspection import inspect
        inst = inspect(Establishment)
        attr_names = [c_attr.key for c_attr in inst.mapper.column_attrs]
        print(f"📊 ORM Model attrs: {attr_names}")
        if 'responsible_email' in attr_names:
             print("✅ 'responsible_email' FOUND in ORM Model")
        else:
             print("❌ 'responsible_email' MISSING in ORM Model (Restart App to clear cache?)")

if __name__ == "__main__":
    verify()
