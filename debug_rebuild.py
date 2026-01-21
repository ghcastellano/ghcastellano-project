from src.services.pdf_service import PDFService
from unittest.mock import MagicMock

# Mock PDF Service Logic (Copy-Paste for isolation)
class MockPDFService:
    def enrich_data(self, data: dict):
        if not data: return
        if 'areas_inspecionadas' not in data: data['areas_inspecionadas'] = []
        
        # Ensure top level keys
        if 'aproveitamento_geral' not in data: data['aproveitamento_geral'] = 0
        
        total_obtido = 0
        total_maximo = 0
        
        for area in data['areas_inspecionadas']:
            area_obtido = 0
            area_maximo = 0
            itens = area.get('itens', [])
            
            for item in itens:
                # Status translation logic from service
                status = item.get('status', 'OPEN')
                if status == 'OPEN':
                    item['status'] = 'Não Conforme'
                elif status == 'COMPLIANT':
                     item['status'] = 'Conforme'
                
                try:
                    score = float(item.get('pontuacao', 0))
                    max_score = float(area.get('pontuacao_maxima_item', 10))
                    
                    if item.get('status') == 'Conforme' and score == 0:
                        score = max_score
                        item['pontuacao'] = score
                        
                    area_obtido += score
                    area_maximo += max_score
                except:
                    continue
            
            area['pontuacao_obtida'] = round(area_obtido, 1)
            area['pontuacao_maxima'] = round(area_maximo, 1)
            if area_maximo > 0:
                area['aproveitamento'] = round((area_obtido / area_maximo) * 100, 1)
            else:
                area['aproveitamento'] = 0
                
            total_obtido += area_obtido
            total_maximo += area_maximo
            
        if total_maximo > 0:
            data['aproveitamento_geral'] = round((total_obtido / total_maximo) * 100, 2)

# Simulate Manager Route Logic
def simulate_manager_logic():
    # 1. Mock DB Items (Coming from Database)
    # Scenario: Item is Partial in DB but might have score 0 if migration failed
    # But user says JSON has Partial.
    
    mock_db_item_partial = MagicMock()
    mock_db_item_partial.id = "uuid-1"
    mock_db_item_partial.nome_area = "Cozinha"
    mock_db_item_partial.item_verificado = "Item X"
    mock_db_item_partial.status_inicial = "Parcialmente Conforme" # Text from DB
    mock_db_item_partial.original_score = 0.0 # Problem: Saved as 0 in DB?
    mock_db_item_partial.problem_description = "Problema"
    mock_db_item_partial.fundamento_legal = "Lei"
    mock_db_item_partial.corrective_action = "Ação"
    mock_db_item_partial.deadline_date = None
    mock_db_item_partial.deadline_text = None
    mock_db_item_partial.ai_suggested_deadline = "Hoje"
    mock_db_item_partial.order_index = 1

    db_items = [mock_db_item_partial]
    
    # 2. Rebuild Areas Dictionary (Logic from manager_routes.py)
    rebuilt_areas = {}
    
    # Mock Score Recovery Map (from JSON)
    # Suppose JSON had the correct score
    score_map = {
        "Item X": 5.0 
    }
    
    for item in db_items:
        area_name = item.nome_area or "Geral"
        if area_name not in rebuilt_areas:
            rebuilt_areas[area_name] = {
                'nome_area': area_name,
                'items_nc': 0, 
                'pontuacao_obtida': 0, # Initial 0
                'pontuacao_maxima': 0, 
                'aproveitamento': 0,
                'itens': []
            }
            
        key = (item.item_verificado or "").strip()[:50]
        recovered_score = score_map.get(key, 0)
        
        # LOGIC UNDER TEST: Priority of Original Score vs Recovered
        pontuacao = item.original_score if item.original_score is not None else recovered_score
        
        template_item = {
            'id': str(item.id),
            'item_verificado': item.item_verificado,
            'status': item.status_inicial or 'Não Conforme',
            'pontuacao': pontuacao
        }
        rebuilt_areas[area_name]['itens'].append(template_item)
        
    report_data = {
        'areas_inspecionadas': list(rebuilt_areas.values())
    }
    
    print("--- Before Enrich ---")
    print(report_data['areas_inspecionadas'][0]['pontuacao_obtida'])
    print(report_data['areas_inspecionadas'][0]['itens'][0])
    
    # 3. Apply Enrich Data
    pdf_service = MockPDFService()
    pdf_service.enrich_data(report_data)
    
    print("\n--- After Enrich ---")
    print(report_data['areas_inspecionadas'][0]['pontuacao_obtida'])
    print(report_data['areas_inspecionadas'][0]['itens'][0])

simulate_manager_logic()
