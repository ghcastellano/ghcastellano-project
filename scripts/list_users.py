from src.database import get_db, init_db
from src.models_db import User

def list_users():
    init_db()
    db_gen = get_db()
    db = next(db_gen)
    users = db.query(User).all()
    for u in users:
        print(f"User: {u.email} | Role: {u.role}")

if __name__ == "__main__":
    list_users()
