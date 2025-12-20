from src.database import get_db, init_db
from src.models_db import User, UserRole
from werkzeug.security import generate_password_hash
import sys

def create_admin(email, passwordvar, name="Administrador"):
    """
    Cria um usuário ADMIN.
    """
    db_gen = get_db()
    db = next(db_gen)
    
    try:
        # Check if exists
        existing = db.query(User).filter_by(email=email).first()
        if existing:
            print(f"Usuário {email} já existe.")
            # Update role if needed?
            if existing.role != UserRole.ADMIN:
                print("Atualizando para ADMIN...")
                existing.role = UserRole.ADMIN
                db.commit()
            return

        print(f"Criando Admin: {email}...")
        hashed = generate_password_hash(passwordvar)
        
        user = User(
            email=email,
            password_hash=hashed,
            name=name,
            role=UserRole.ADMIN,
            is_active=True,
            must_change_password=False
        )
        
        db.add(user)
        db.commit()
        print(f"Admin criado com sucesso! Login: {email}")
        
    except Exception as e:
        print(f"Erro: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
    if len(sys.argv) < 3:
        print("Uso: python scripts/create_admin.py <email> <senha> [nome]")
        # Fallback interactive or default
        email = input("Email do Admin: ")
        password = input("Senha do Admin: ")
        create_admin(email, password)
    else:
        create_admin(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "Admin")
