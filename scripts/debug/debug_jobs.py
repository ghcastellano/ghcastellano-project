import os
import sys
from sqlalchemy import create_engine, text
from src.config import DATABASE_URL  # Ensure config is loaded

def check_recent_jobs():
    if not DATABASE_URL:
        print("❌ DATABASE_URL não definida!")
        return

    print(f"🔌 Conectando ao Banco...")
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            print("🔍 Buscando últimos 10 Jobs...")
            result = conn.execute(text("SELECT id, type, status, created_at, started_at, completed_at, error_log FROM jobs ORDER BY created_at DESC LIMIT 10"))
            rows = result.fetchall()
            
            if not rows:
                print("⚠️ Nenhum job encontrado no banco.")
            
            for row in rows:
                print("-" * 60)
                print(f"ID: {row[0]}")
                print(f"Type: {row[1]}")
                print(f"Status: {row[2]}")
                print(f"Created: {row[3]}")
                print(f"Started: {row[4]}")
                print(f"Completed: {row[5]}")
                print(f"Error: {row[6]}")
                print("-" * 60)

    except Exception as e:
        print(f"❌ Erro ao conectar/consultar: {e}")

if __name__ == "__main__":
    # Ensure current directory is in path for imports
    sys.path.append(os.getcwd())
    check_recent_jobs()
