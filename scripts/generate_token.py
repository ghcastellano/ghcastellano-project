
import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# Escopos necessários
SCOPES = ['https://www.googleapis.com/auth/drive']

def generate_token():
    """
    Inicia o fluxo OAuth 2.0 local para gerar um token de usuário.
    Salva o resultado em 'user_token.json' que pode ser usado na ENV VAR GCP_OAUTH_TOKEN.
    """
    creds = None
    
    # Verifica se já existe um client_secrets.json (baixado do console)
    if not os.path.exists('client_secrets.json'):
        # Fallback: Tenta usar credentials.json se for do tipo 'installed' ou similar,
        # mas geralmente precisa do client_secret específico de OAuth Web/Desktop.
        # Se não tiver, avisa o usuário.
        if os.path.exists('credentials.json'):
            print("⚠️ 'client_secrets.json' não encontrado, tentando usar 'credentials.json'...")
            client_config = 'credentials.json'
        else:
            print("❌ Erro: Arquivo 'client_secrets.json' não encontrado.")
            print("1. Vá em https://console.cloud.google.com/apis/credentials")
            print("2. Clique em 'Criar Credenciais' -> 'ID do cliente OAuth 2.0' (Desktop App)")
            print("3. Baixe o JSON e salve como 'client_secrets.json' nesta pasta.")
            return

    else:
        client_config = 'client_secrets.json'

    try:
        flow = InstalledAppFlow.from_client_secrets_file(client_config, SCOPES)
        creds = flow.run_local_server(port=0)
    except Exception as e:
        print(f"Erro no fluxo de autenticação: {e}")
        return

    # Salva o token completo
    token_data = {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scopes': creds.scopes
    }

    # Output Compacto para ENV VAR
    json_output = json.dumps(token_data)
    
    filename = 'user_credentials.json'
    with open(filename, 'w') as f:
        f.write(json_output)

    print(f"\n✅ Token gerado com sucesso em '{filename}'")
    print("\n--- PASSO FINAL: ---")
    print("Copie o conteúdo deste arquivo e crie uma Variável de Ambiente/Secret no Cloud Run:")
    print(f"Nome: GCP_OAUTH_TOKEN")
    print(f"Valor: (Conteúdo do arquivo {filename})")
    print("--------------------\n")

if __name__ == '__main__':
    generate_token()
