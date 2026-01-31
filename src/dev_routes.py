
import os
import io
import json
from flask import send_file, Blueprint, render_template, jsonify, current_app
from src.services.pdf_service import pdf_service

# Blueprint for Fast-Track UI Dev (Login Bypass)
dev_bp = Blueprint('dev', __name__, url_prefix='/dev')

def load_mock_data():
    """Loads the rich inspection mock JSON."""
    try:
        mock_path = os.path.join(current_app.root_path, 'mocks', 'full_inspection_mock.json')
        with open(mock_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # --- Polyfill Rich Data (Prevent UndefinedError) ---
        if 'aproveitamento_geral' not in data:
            data['aproveitamento_geral'] = 85
            data['resumo_geral'] = "Resumo simulado: O estabelecimento apresenta boas condições gerais."
            
        if 'areas_inspecionadas' in data:
            for area in data['areas_inspecionadas']:
                area.setdefault('pontuacao_obtida', 8)
                area.setdefault('pontuacao_maxima', 10)
                area.setdefault('aproveitamento', 80)
                
                # Calculate items_nc logic
                items = area.get('itens', [])
                area['items_nc'] = sum(1 for item in items if item.get('status') != 'Conforme')
                
        return data
    except Exception as e:
        return {"error": f"Failed to load mock: {e}"}

@dev_bp.route('/')
def index():
    """Hub for all dev links."""
    return render_template('dev_index.html')

@dev_bp.route('/manager/review')
def manager_review():
    """Renders the Manager Plan Editor with mock data."""
    data = load_mock_data()
    
    # [FIX] Polyfill: Calculate items_nc for mock data (Required by template)
    if 'areas_inspecionadas' in data:
        for area in data['areas_inspecionadas']:
            items = area.get('itens', [])
            # Count items where status is NOT 'Conforme'
            area['items_nc'] = sum(1 for item in items if item.get('status') != 'Conforme')

    # Mocking necessary context objects usually passed by controllers
    mock_inspection = {
        "id": "mock-uuid-1234",
        "drive_file_id": "mock-file-123",
        "status": "PROCESSING", 
        "establishment": {"name": data.get('nome_estabelecimento')},
        "created_at": "2024-01-05T10:00:00"
    }
    return render_template('manager_plan_edit.html', 
                           inspection=mock_inspection, 
                           report_data=data,
                           is_dev_mode=True)

@dev_bp.route('/consultant/review')
def consultant_review():
    """Renders the Consultant Signature/Review page with mock data."""
    data = load_mock_data()
    
    # [FIX] Polyfill: Calculate items_nc for mock data (Required by template)
    if 'areas_inspecionadas' in data:
        for area in data['areas_inspecionadas']:
            items = area.get('itens', [])
            # Count items where status is NOT 'Conforme'
            area['items_nc'] = sum(1 for item in items if item.get('status') != 'Conforme')

    mock_inspection = {
        "id": "mock-uuid-5678",
        "drive_file_id": "mock-file-567",
        "status": "PENDING_CONSULTANT_VERIFICATION",
        "establishment": {"name": data.get('nome_estabelecimento')},
        "created_at": "2024-01-05T14:30:00"
    }
    # Using a new template or reusing one? Let's assume a new one for high fidelity.
    return render_template('review.html', 
                           inspection=mock_inspection, 
                           report_data=data, 
                           is_dev_mode=True)

@dev_bp.route('/api/mock-save', methods=['POST'])
def mock_save():
    """Simulates saving the action plan."""
    return jsonify({"success": True, "message": "MOCK SAVE: Data received successfully (No DB changes)."})

@dev_bp.route('/mock-pdf-test')
def mock_pdf_test():
    """Generates a PDF using mock data to test layout."""
    data = load_mock_data()
    
    # --- Data Enrichment for PDF Mock ---
    if 'areas_inspecionadas' in data:
        # Override date to Brazilian format string for testing
        data['data_inspecao'] = '08/10/2025'
        data['status_plano'] = 'AGUARDANDO VISITA' # Mock Status for PDF Test
        
        for area in data['areas_inspecionadas']:
            items = area.get('itens', [])
            
            # FORCE Mock Data to have Non-Conformities for PDF Test
            for i, item in enumerate(items):
                if i < 2: # First 2 items of each area
                    item['status'] = 'Não Conforme'
                    item['pontuacao'] = 0.0
                    item['pontuacao_maxima'] = 1.0
                    
                    if i % 2 == 0:
                        item['is_corrected'] = True
                        item['correction_notes'] = "Realmente a limpeza ocorreu e atualmente está tudo organizado."
                        item['evidence_image_url'] = "/static/uploads/evidence/mock_evidence.png"
                    else:
                        item['is_corrected'] = False
                        item['correction_notes'] = "Os vazamentos continuam acontecendo."
            
            # Recalculate items_nc after forcing
            area['items_nc'] = sum(1 for item in items if item.get('status') != 'Conforme')
            
    pdf_bytes = pdf_service.generate_pdf_bytes(data, template_name='pdf_template.html')
    
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=False,
        download_name='relatorio_teste.pdf'
    )
