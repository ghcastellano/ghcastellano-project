from src.app import app
from src.database import db_session
from src.models_db import Inspection, ActionPlan, ActionPlanItem, Job
from sqlalchemy import text

def wipe_data():
    with app.app_context():
        # Order matters due to foreign keys
        print("🗑️  Apagando Itens do Plano de Ação...")
        db_session.execute(text("DELETE FROM action_plan_items;"))
        
        print("🗑️  Apagando Planos de Ação...")
        db_session.execute(text("DELETE FROM action_plans;"))
        
        print("🗑️  Apagando Inspeções...")
        db_session.execute(text("DELETE FROM inspections;"))
        
        print("🗑️  Apagando Jobs (Processamento)...")
        db_session.execute(text("DELETE FROM jobs;"))
        
        db_session.commit()
        print("✅ Banco de dados limpo com sucesso! (Tabelas de Relatórios/Jobs)")

if __name__ == "__main__":
    wipe_data()
