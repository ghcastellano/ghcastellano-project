import sys
import os
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
load_dotenv()

from src.database import get_db, init_db
from src.models_db import User

def reset_password(email, new_password):
    init_db()
    db = next(get_db())
    try:
        user = db.query(User).filter_by(email=email).first()
        if not user:
            print(f"❌ Usuário {email} não encontrado.")
            return

        print(f"🔐 Resetando senha para {user.name} ({user.email})...")
        user.password_hash = generate_password_hash(new_password)
        db.commit()
        print(f"✅ Senha alterada com sucesso para: {new_password}")
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python scripts/reset_password.py <email> [senha]")
        sys.exit(1)
        
    email = sys.argv[1]
    password = sys.argv[2] if len(sys.argv) > 2 else "123456"
    
    reset_password(email, password)
