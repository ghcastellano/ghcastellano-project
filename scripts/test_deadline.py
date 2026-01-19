
import sys
import os
import uuid
import json
from datetime import date

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


from dotenv import load_dotenv
load_dotenv()

from src.app import app
from src import database

from src.models_db import ActionPlanItem, ActionPlan, ActionPlanItemStatus

def test_deadline_persistence():
    """
    Simula o payload de salvamento do plano para verificar se o prazo é persistido.
    """
    with app.app_context():
        session = next(database.get_db())
        
        # 1. Setup: Criar Item de Teste se não existir
        # Precisamos de um ActionPlan e um Item real no banco
        # Vamos buscar um existente ou criar mock
        print("🔍 Buscando ActionPlan existente...")
        plan = session.query(ActionPlan).first()
        if not plan:
            print("⚠️ Nenhum Plano encontrado. Teste abortado. Crie um End-to-End primeiro.")
            return

        # Adicionar Item de Teste
        item_uuid = uuid.uuid4()
        new_item = ActionPlanItem(
            id=item_uuid,
            action_plan_id=plan.id,
            problem_description="Teste Prazo",
            corrective_action="Verificar DB",
            legal_basis="N/A",
            status=ActionPlanItemStatus.OPEN,
            deadline_date=None # Começa vazio
        )
        session.add(new_item)
        session.commit()
        print(f"✅ Item de teste criado: {item_uuid}")

        # 2. Simular Request de Update
        # Payload com deadline
        payload = {
            "items": [
                {
                    "id": str(item_uuid),
                    "deadline": "2026-12-31" # Formato ISO
                }
            ]
        }
        
        # Como o endpoint 'save_plan' é protegido e complexo, vamos testar a LÓGICA do endpoint isolada
        # (copiando do manager_routes.py para validar o parse)
        
        print("🧪 Testando lógica de Parse...")
        target_item = session.query(ActionPlanItem).get(item_uuid)
        item_data = payload['items'][0]
        
        if 'deadline' in item_data:
            from datetime import datetime
            try:
                dt = datetime.strptime(item_data['deadline'], '%Y-%m-%d').date()
                target_item.deadline_date = dt
                print(f"✅ Parse Sucesso: {dt}")
            except Exception as e:
                print(f"❌ Parse Falhou: {e}")

        session.commit()
        
        # 3. Verificar Persistência
        session.refresh(target_item)
        if target_item.deadline_date == date(2026, 12, 31):
            print("🎉 SUCESSO: Prazo salvo no banco corretamente.")
        else:
            print(f"❌ FALHA: Prazo no banco é {target_item.deadline_date}, esperado 2026-12-31")

        # Cleanup
        session.delete(target_item)
        session.commit()

if __name__ == "__main__":
    test_deadline_persistence()
