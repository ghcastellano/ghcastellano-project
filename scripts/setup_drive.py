import os
import logging
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv

# Configura logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constantes
SCOPES = ['https://www.googleapis.com/auth/drive']
CREDENTIALS_FILE = 'credentials.json'
ENV_FILE = '.env'

FOLDERS_TO_CREATE = [
    "01_ENTRADA_RELATORIOS",
    "02_PLANOS_GERADOS",
    "03_PROCESSADOS_BACKUP",
    "99_ERROS"
]

def authenticate():
    """Autentica com a API do Google Drive usando uma conta de serviço."""
    if not os.path.exists(CREDENTIALS_FILE):
        logger.error(f"Erro: {CREDENTIALS_FILE} não encontrado.")
        return None
    
    try:
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
        return creds
    except Exception as e:
        logger.error(f"Falha na autenticação: {e}")
        return None

def find_or_create_folder(service, folder_name, parent_id=None):
    """Encontra uma pasta pelo nome ou cria se não existir."""
    query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false"
    if parent_id:
        query += f" and '{parent_id}' in parents"
    
    try:
        # Verifica se a pasta existe
        results = service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get('files', [])

        if files:
            logger.info(f"Pasta '{folder_name}' já existe com ID: {files[0]['id']}")
            return files[0]['id']
        else:
            # Cria a pasta
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            if parent_id:
                file_metadata['parents'] = [parent_id]

            file = service.files().create(body=file_metadata, fields='id').execute()
            logger.info(f"Pasta '{folder_name}' criada com ID: {file.get('id')}")
            return file.get('id')

    except HttpError as error:
        logger.error(f"Ocorreu um erro com a API do Drive: {error}")
        return None

def update_env_file(folder_ids):
    """Atualiza ou cria o arquivo .env com os IDs das pastas."""
    env_lines = []
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, 'r') as f:
            env_lines = f.readlines()
    
    # Remove chaves de ID de pasta existentes para evitar duplicatas
    keys_to_remove = [f"FOLDER_ID_{name}" for name in FOLDERS_TO_CREATE]
    env_lines = [line for line in env_lines if not any(line.startswith(key) for key in keys_to_remove)]

    # Adiciona novas chaves
    if env_lines and not env_lines[-1].endswith('\n'):
        env_lines.append('\n')
        
    for name, folder_id in folder_ids.items():
        key = f"FOLDER_ID_{name}"
        env_lines.append(f'{key}="{folder_id}"\n')
    
    with open(ENV_FILE, 'w') as f:
        f.writelines(env_lines)
    logger.info(f"{ENV_FILE} atualizado com os IDs das pastas.")

def main():
    logger.info("Iniciando script de setup do Drive...")
    
    creds = authenticate()
    if not creds:
        return

    try:
        service = build('drive', 'v3', credentials=creds)
        
        # Determina pasta raiz (opcional: criar raiz de projeto se necessário,
        # mas por hora criamos na raiz da Service Account ou Shared Drive)
        # Nota: Service Accounts tem seu próprio armazenamento.
        # Se o usuário quer isso no Drive DELE, precisa compartilhar uma pasta pai com o email da SA.
        # Este script cria na raiz da SA a menos que um pai seja especificado.
        # Para este MVP, criaremos na raiz da SA.
        
        folder_ids = {}
        for folder_name in FOLDERS_TO_CREATE:
            folder_id = find_or_create_folder(service, folder_name)
            if folder_id:
                folder_ids[folder_name] = folder_id
            else:
                logger.error(f"Falha ao processar pasta {folder_name}")
        
        update_env_file(folder_ids)
        logger.info("Setup completo.")

    except Exception as e:
        logger.error(f"Erro inesperado: {e}")

if __name__ == '__main__':
    main()
