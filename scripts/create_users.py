import os
import sys
from dotenv import load_dotenv

# Load env vars FIRST
load_dotenv()

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import src.database
if not src.database.DATABASE_URL:
    src.database.DATABASE_URL = os.getenv("DATABASE_URL")
src.database.init_db()

from src.database import SessionLocal
from src.models_db import User, UserRole
from werkzeug.security import generate_password_hash

def create_user(email, password, name, role_str):
    try:
        role = UserRole(role_str)
    except ValueError:
        print(f"❌ Invalid role: {role_str}")
        return

    db = SessionLocal()
    try:
        # Check if exists
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            print(f"⚠️ User {email} already exists. Updating...")
            existing.password_hash = generate_password_hash(password)
            existing.role = role
            existing.name = name
        else:
            new_user = User(
                email=email,
                password_hash=generate_password_hash(password),
                role=role,
                name=name
            )
            db.add(new_user)
        
        db.commit()
        print(f"✅ User {email} ({role.value}) created/updated successfully!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    # Seed default users
    create_user("gestor@teste.com", "123456", "Gestor Admin", "MANAGER")
    create_user("consultor@teste.com", "123456", "Consultor Campo", "CONSULTANT")
