
import sys
import os

# Add src to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import get_db
from src.models_db import User, UserRole, Inspection
from werkzeug.security import generate_password_hash
from sqlalchemy import desc

from sqlalchemy.orm import defer

def admin_ops():
    print("Connecting to DB...")
    db_gen = get_db()
    db = next(db_gen)
    try:
        # 1. Reset/Create Admin
        email = 'admin@admin.com'
        password = 'admin123'
        
        user = db.query(User).filter_by(email=email).first()
        if user:
            print(f"Update existing admin: {email}")        
            user.password_hash = generate_password_hash(password, method='pbkdf2:sha256')
            user.role = UserRole.ADMIN
            user.is_active = True # Force Active
            
            # Remove from establishments to avoid conflicts if previously a consultant
            if user.establishments:
                user.establishments = []
                
        else:
            print(f"Creating NEW admin: {email}")
            user = User(
                name='Super Admin',
                email=email,
                password_hash=generate_password_hash(password, method='pbkdf2:sha256'),
                role=UserRole.ADMIN,
                is_active=True,
                must_change_password=False
            )
            db.add(user)
        
        db.commit()
        db.refresh(user)
        print(f"✅ Admin credentials set: {email} / {password}")
        print(f"Refreshed User: ID={user.id}, Role={user.role}, Active={user.is_active}")
        
        # Verify Password
        from werkzeug.security import check_password_hash
        is_valid = check_password_hash(user.password_hash, password)
        print(f"🔐 Local Password Verification: {'PASSED' if is_valid else 'FAILED'}")
        print(f"# Hash: {user.password_hash}")

        # 2. Investigate Inspections
        print("\n--- Recent Inspections (Last 10) ---")
        # Defer loading of processing_logs as it might be missing
        inspections = db.query(Inspection).options(defer(Inspection.processing_logs)).order_by(desc(Inspection.created_at)).limit(10).all()
        
        if not inspections:
            print("No inspections found.")
        
        for i in inspections:
            est_name = i.establishment.name if i.establishment else "Unknown"
            print(f"ID: {i.id} | Date: {i.created_at} | Status: {i.status.value} | Est: {est_name} | FileID: {i.drive_file_id}")
            
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    admin_ops()
