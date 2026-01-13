import sys
import os

# Carregador Manual de .env (já que rodamos isolado)
# Parser simples para CHAVE=VALOR
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
if os.path.exists(env_path):
    print(f"Carregando .env de {env_path}")
    with open(env_path) as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                k, v = line.strip().split('=', 1)
                # Remove aspas potenciais
                v = v.strip("'").strip('"')
                os.environ[k] = v

# Adiciona raiz do projeto ao path (pai de 'scripts')
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# O resto dos imports...

from src import database
from src.database import init_db
from src.models_db import Inspection, ActionPlan, ActionPlanItem, Job, Visit, InspectionStatus
from sqlalchemy import text

def reset_data():
    # Acessa db_session do módulo para ver valor atualizado após init_db()
    if not database.db_session:
        print("❌ Erro: Sessão do banco não inicializada.")
        return
        
    session = database.db_session()
    try:
        print("⚠️  AVISO: Isso irá APAGAR todas as Inspeções, Planos de Ação e Tarefas.")
        print("    Usuários, Empresas e Estabelecimentos serão PRESERVADOS.")
        
        # 1. Deletar Itens do Plano de Ação
        deleted_items = session.query(ActionPlanItem).delete()
        print(f"✅ Deletados {deleted_items} Itens de Plano de Ação")
        
        # 2. Deletar Planos de Ação
        deleted_plans = session.query(ActionPlan).delete()
        print(f"✅ Deletados {deleted_plans} Planos de Ação")
        
        # 3. Deletar Inspeções
        deleted_inspections = session.query(Inspection).delete()
        print(f"✅ Deletadas {deleted_inspections} Inspeções")
        
        # 4. Deletar Jobs (Tarefas de Fundo)
        deleted_jobs = session.query(Job).delete()
        print(f"✅ Deletados {deleted_jobs} Jobs")
        
        # 5. Deletar Visitas (Se solicitado, opcional)
        # deleted_visits = session.query(Visit).delete()
        # print(f"✅ Deletadas {deleted_visits} Visitas")

        session.commit()
        print("\n🎉 Limpeza do Banco Completa! Pronto para novos testes.")
        
    except Exception as e:
        session.rollback()
        print(f"❌ Error during cleanup: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    init_db()
    reset_data()
