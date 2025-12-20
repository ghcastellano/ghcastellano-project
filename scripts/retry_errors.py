import os
import logging
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

FOLDER_IN = os.getenv("FOLDER_ID_01_ENTRADA_RELATORIOS")
FOLDER_ERROR = os.getenv("FOLDER_ID_99_ERROS")
CREDENTIALS_FILE = 'credentials.json'

def main():
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE)
    service = build('drive', 'v3', credentials=creds)

    query = f"'{FOLDER_ERROR}' in parents and trashed=false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get('files', [])
    
    if not files:
        logger.info("Nenhum arquivo na pasta de ERRO.")
        return

    for file in files:
        logger.info(f"Movendo {file['name']} de volta para ENTRADA...")
        service.files().update(
            fileId=file['id'],
            addParents=FOLDER_IN,
            removeParents=FOLDER_ERROR
        ).execute()

if __name__ == '__main__':
    main()
