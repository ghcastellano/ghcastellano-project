from sqlalchemy import text
from src.database import get_db

def run_migration_v6():
    """
    Cria a tabela 'contacts' para armazenar múltiplos responsáveis por estabelecimento.
    """
    db_gen = get_db()
    db = next(db_gen)
    
    try:
        print("Iniciando Migração V6: Criando tabela contacts...")
        
        # SQL para recriar tabela corretamente com UUIDs
        sql = text("""
        DROP TABLE IF EXISTS contacts;
        
        CREATE TABLE contacts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            establishment_id UUID NOT NULL REFERENCES establishments(id),
            name VARCHAR(255) NOT NULL,
            phone VARCHAR(50) NOT NULL,
            email VARCHAR(255),
            role VARCHAR(100),
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        """)
        
        db.execute(sql)
        db.commit()
        print("Migração V6 concluída com sucesso!")
        
    except Exception as e:
        print(f"Erro na Migração V6: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    run_migration_v6()
