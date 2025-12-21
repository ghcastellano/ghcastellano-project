import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/drive']

def main():
    """Shows basic usage of the Drive v3 API.
    Prints the names and ids of the first 10 files the user has access to.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('client_secret.json'):
                print("❌ ERRO: O arquivo 'client_secret.json' não foi encontrado.")
                print("1. Vá em https://console.cloud.google.com/apis/credentials")
                print("2. Clique em 'Criar Credenciais' > 'ID do cliente OAuth 2.0'")
                print("3. Escolha 'Desktop App' (App para Computador)")
                print("4. Baixe o JSON, renomeie para 'client_secret.json' e coloque nesta pasta.")
                return

            flow = InstalledAppFlow.from_client_secrets_file(
                'client_secret.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            
    print("\n✅ SUCESSO! Token gerado em 'token.json'.")
    print("Conteúdo do token para salvar no Secret Manager:\n")
    print(creds.to_json())

if __name__ == '__main__':
    main()
