import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

try:
    from services.email_service import EmailService
    print("✅ EmailService importado com sucesso.")
except ImportError as e:
    print(f"❌ Erro ao importar EmailService: {e}")
    sys.exit(1)

try:
    from models_db import Job
    print("✅ Job model importado com sucesso.")
except ImportError as e:
    print(f"❌ Erro ao importar Job model: {e}")
    sys.exit(1)

def test_job_cost():
    print("\n--- Testando Job Cost Attributes ---")
    j = Job()
    try:
        j.cost_input_usd = 0.1
        j.cost_output_usd = 0.2
        print(f"✅ Job Cost set successfully: In={j.cost_input_usd}, Out={j.cost_output_usd}")
        
        # Verify no 'cost_usd' exists (should be protected or non-existent)
        if hasattr(j, 'cost_usd'):
            print("⚠️ Aviso: 'cost_usd' ainda existe no modelo. Verifique se é intencional.")
        else:
            print("✅ 'cost_usd' removido corretamente do modelo.")
            
    except Exception as e:
        print(f"❌ Erro ao definir custos no Job: {e}")
        sys.exit(1)

def test_email_sig():
    print("\n--- Testando EmailService Signature ---")
    es = EmailService('mock')
    try:
        # Signature: send_email(self, to_email, subject, html_body, text_body)
        es.send_email("test@test.com", "Subject", "<p>Body</p>", "Text Body")
        print("✅ EmailService.send_email chamado com sucesso (argumentos corretos).")
    except TypeError as e:
        print(f"❌ Erro de assinatura no EmailService: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Erro geral no EmailService: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_job_cost()
    test_email_sig()
    print("\n🎉 Todos os testes de regressão locais passaram!")
