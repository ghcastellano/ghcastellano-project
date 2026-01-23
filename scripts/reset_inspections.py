import sys
import os
sys.path.append(os.getcwd())

from dotenv import load_dotenv
load_dotenv()

from src import database
from src.database import init_db
from src.models_db import Job, Inspection, ActionPlan, ActionPlanItem

def reset_data():
    if input("⚠️ TEM CERTEZA que deseja apagar TODAS as inspeções e planos? (S/N): ").upper() != 'S':
        print("Operação cancelada.")
        return

    init_db()
    db = database.db_session
    
    print("🗑️ Apagando Itens do Plano de Ação...")
    db.query(ActionPlanItem).delete()
    
    print("🗑️ Apagando Planos de Ação...")
    db.query(ActionPlan).delete()
    
    print("🗑️ Apagando Inspeções...")
    db.query(Inspection).delete()
    
    print("🗑️ Apagando Jobs de Processamento...")
    db.query(Job).delete()
    
    db.commit()
    print("✅ Dados limpos com sucesso!")

if __name__ == "__main__":
    reset_data()
