from src.config import config
from src.models_db import User

# Fix config manually before init_db reads it
if config.DATABASE_URL and "DATABASE_URL=" in config.DATABASE_URL:
    print("⚠️ Detected corrupted DATABASE_URL. Fixing...")
    config.DATABASE_URL = config.DATABASE_URL.split("DATABASE_URL=")[0]

from src.database import init_db, get_db

def list_users():
    init_db()
    db_gen = get_db()
    db = next(db_gen)
    users = db.query(User).all()
    print("-" * 30)
    for u in users:
        print(f"User: {u.email} | Role: {u.role}")
    print("-" * 30)

if __name__ == "__main__":
    list_users()
