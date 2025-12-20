import os
import logging
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from dotenv import load_dotenv

# Configura logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/drive']
CREDENTIALS_FILE = 'credentials.json'
USER_EMAIL = 'ghcastellano@gmail.com'

def authenticate():
    if not os.path.exists(CREDENTIALS_FILE):
        logger.error(f"Erro: {CREDENTIALS_FILE} não encontrado.")
        return None
    return Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)

def share_folder(service, folder_id, role='writer'):
    try:
        permission = {
            'type': 'user',
            'role': role,
            'emailAddress': USER_EMAIL
        }
        service.permissions().create(
            fileId=folder_id,
            body=permission,
            fields='id',
            emailMessage='Acesso às pastas do MVP Inspeção Sanitária Serverless'
        ).execute()
        logger.info(f"Pasta {folder_id} compartilhada com {USER_EMAIL} (role: {role})")
    except Exception as e:
        logger.error(f"Erro ao compartilhar {folder_id}: {e}")

def main():
    logger.info(f"Iniciando compartilhamento com {USER_EMAIL}...")
    creds = authenticate()
    if not creds: return

    service = build('drive', 'v3', credentials=creds)

    # Ler IDs do .env carregado
    folders = [
        os.getenv("FOLDER_ID_01_ENTRADA_RELATORIOS"),
        os.getenv("FOLDER_ID_02_PLANOS_GERADOS"),
        os.getenv("FOLDER_ID_03_PROCESSADOS_BACKUP"),
        os.getenv("FOLDER_ID_99_ERROS")
    ]

    for fid in folders:
        if fid:
            share_folder(service, fid)
        else:
            logger.warning("ID de pasta não encontrado no .env")

    logger.info("Fim do processamento.")

if __name__ == '__main__':
    main()
