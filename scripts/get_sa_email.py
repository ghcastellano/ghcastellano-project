
import os
import google.auth

def get_sa_email():
    try:
        credentials, project = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
        
        if hasattr(credentials, 'service_account_email'):
            print("\n✅ Service Account Email Localizado:")
            print(f"👉 {credentials.service_account_email}")
            print("\n📋 Copie o email acima e COMPARTILHE a pasta do Google Drive com ele (Editor).")
        else:
            print("⚠️ Credenciais encontradas, mas não parecem ser de Service Account.")
            print(f"Tipo: {type(credentials)}")
            # Tenta ler do JSON se for file based
            if os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
                import json
                try:
                    with open(os.getenv('GOOGLE_APPLICATION_CREDENTIALS'), 'r') as f:
                        data = json.load(f)
                        print(f"👉 {data.get('client_email', 'Não encontrado no JSON')}")
                except:
                    pass

    except Exception as e:
        print(f"❌ Erro ao obter credenciais: {e}")

if __name__ == "__main__":
    get_sa_email()
