
import sys
import os

# Add src to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import get_db
from src.models_db import User, UserRole

def find_admin():
    print("Connecting to DB...")
    db_gen = get_db()
    db = next(db_gen)
    try:
        admins = db.query(User).filter(User.role == UserRole.ADMIN).all()
        if not admins:
            print("No ADM users found.")
        for admin in admins:
            print(f"FOUND ADMIN: Email: {admin.email} | Name: {admin.name}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    find_admin()
