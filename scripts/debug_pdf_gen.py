
import os
import sys
import logging
from datetime import datetime
from src.services.processor import ProcessorService
from src.models import ChecklistSanitario

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_pdf_gen():
    print("🚀 Starting PDF Gen Test...")
    
    # Mock Data Completo
    from src.models import AreaInspecao, ChecklistItem
    
    # Area 1: Cozinha
    item1 = ChecklistItem(
        item_verificado="Lixeiras com acionamento não manual",
        status="Não Conforme",
        observacao="Lixeira da pia de preparo sem tampa e com pedal quebrado.",
        fundamento_legal="RDC 216/04 Item 4.1.3",
        acao_corretiva_sugerida="Substituir lixeira por modelo com pedal funcionando.",
        prazo_sugerido="Imediato"
    )
    
    area1 = AreaInspecao(
        nome_area="Cozinha / Manipulação",
        resumo_area="Área com estrutura antiga.",
        pontuacao_obtida=8,
        pontuacao_maxima=10,
        aproveitamento=80.0,
        itens=[item1]
    )

    # Area 2: Estoque
    item2 = ChecklistItem(
        item_verificado="Organização e Limpeza",
        status="Parcialmente Conforme",
        observacao="Caixas de papelão em contato direto com o chão.",
        fundamento_legal="CVS-5/13 Art. 68",
        acao_corretiva_sugerida="Instalar pallets ou prateleiras (min 25cm do chão).",
        prazo_sugerido="7 dias"
    )

    area2 = AreaInspecao(
        nome_area="Estoque Seco",
        resumo_area="Área organizada, mas com detalhes de armazenamento.",
        pontuacao_obtida=45,
        pontuacao_maxima=50,
        aproveitamento=90.0,
        itens=[item2]
    )

    data = ChecklistSanitario(
        nome_estabelecimento="Padaria Modelo (Debug)",
        resumo_geral="Estabelecimento apresenta boas condições gerais de higiene. Pontos de atenção na estrutura da cozinha e armazenamento no estoque.",
        pontuacao_geral=88,
        pontuacao_maxima_geral=100,
        aproveitamento_geral=88.0,
        data_inspecao="10/01/2026",
        areas_inspecionadas=[area1, area2],
        pontos_fortes="Documentação em dia, equipe uniformizada."
    )
    
    try:
        processor = ProcessorService()
        filename = "debug_pdf_test.pdf"
        
        # Override folder_out to data/output just in case
        processor.folder_out = "data/output" 
        
        print(f"📄 Generating PDF: {filename}")
        link = processor.generate_pdf(data, filename)
        
        print(f"✅ Result Link: {link}")
        
        # Check if local backup worked (since we patched processor.py)
        local_path = f"data/output/Plano_Acao_{filename}"
        if os.path.exists(local_path):
             print(f"✅ Local file found: {local_path}")
        else:
             print(f"❌ Local file NOT found: {local_path}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_pdf_gen()
