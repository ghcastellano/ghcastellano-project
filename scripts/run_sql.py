import sys
import os
from sqlalchemy import text

# Add src to path
sys.path.append(os.path.abspath('.'))
from src.database import SessionLocal, init_db

def run_sql():
    sql = sys.stdin.read().strip()
    if not sql:
        return

    # Initialize DB connection first
    init_db()
    
    # SessionLocal is now populated in src.database module, but we imported the 'None' reference earlier?
    # Actually, importing SessionLocal from src.database might still hold None if it's not a proxy.
    # Let's re-import or use get_db generator.
    # Better: Use the engine or get_db.
    
    from src.database import db_session
    if not db_session:
        print("Failed to init db_session")
        return
        
    db = db_session()
    try:
        result = db.execute(text(sql))
        db.commit()
        try:
            if result.returns_rows:
                for row in result:
                    print(row)
            else:
                print("Query executed (rows affected: unknown).")
        except Exception:
            print("Query executed.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    run_sql()
