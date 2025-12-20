from sqlalchemy import text
from src.database import get_db

def run_migration_v7():
    """
    Cria a tabela de associação M2M 'consultant_establishments' se não existir.
    """
    db_gen = get_db()
    db = next(db_gen)
    
    try:
        print("Iniciando Migração V7: Verificando tabela consultant_establishments...")
        
        # Verificar se tabela existe
        check_sql = text("SELECT to_regclass('public.consultant_establishments');")
        result = db.execute(check_sql).scalar()
        
        if result is None:
            print("Tabela 'consultant_establishments' não existe. Criando...")
            create_sql = text("""
            CREATE TABLE consultant_establishments (
                user_id UUID NOT NULL REFERENCES users(id),
                establishment_id UUID NOT NULL REFERENCES establishments(id),
                PRIMARY KEY (user_id, establishment_id)
            );
            """)
            db.execute(create_sql)
            db.commit()
            print("Migração V7 concluída: Tabela criada.")
        else:
            print("Migração V7: Tabela já existe.")
            
    except Exception as e:
        print(f"Erro na Migração V7: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    run_migration_v7()
