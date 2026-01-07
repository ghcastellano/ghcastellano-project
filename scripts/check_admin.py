
from src.app import app
from src import database
from src.models_db import User, UserRole
from werkzeug.security import generate_password_hash

with app.app_context():
    database.init_db()
    session = database.db_session()
    
    admin = session.query(User).filter_by(role=UserRole.ADMIN).first()
    if admin:
        print(f"✅ Admin user exists: {admin.email}")
    else:
        print("⚠️ Admin user NOT found. Creating...")
        new_admin = User(
            email="admin@mvp.com",
            role=UserRole.ADMIN,
            name="Admin System",
            password_hash=generate_password_hash("admin123"),
            is_active=True
        )
        session.add(new_admin)
        session.commit()
        print(f"✅ Admin user created: admin@mvp.com / admin123")
