import os
import io
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Configuração Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DriveCheck")

SCOPES = ['https://www.googleapis.com/auth/drive']
SERVICE_ACCOUNT_FILE = 'credentials.json'

IDS_TO_CHECK = [
    "1nHUNMLNdETy1Wkhu1i5ZSD6fh72fqbTW",
    "1kgNrQxQNAp5h_rG3xYzD-a5v38zYvfUw",
    "1KHlP7dbeyX8_hUF5Y8mooSu7jnB4ZZzK",
    "1nBBlpVmTSPdpMZGZA1HjrRmi-_W30qoM"
]

def authenticate():
    logger.info("Autenticando...")
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    return build('drive', 'v3', credentials=creds)

def check_folder_names(service):
    print("\n--- RESOLVENDO NOMES DE PASTAS ---")
    mapa = {}
    for fid in IDS_TO_CHECK:
        try:
            f = service.files().get(fileId=fid, fields='id, name', supportsAllDrives=True).execute()
            name = f['name']
            print(f"ID: {fid} => Nome: {name}")
            
            lower = name.lower()
            if 'entrada' in lower or 'input' in lower: mapa['ENTRADA'] = fid
            elif 'plano' in lower or 'saída' in lower or 'saida' in lower or 'output' in lower: mapa['SAIDA'] = fid
            elif 'backup' in lower or 'processado' in lower: mapa['BACKUP'] = fid
            elif 'erro' in lower: mapa['ERRO'] = fid
            
        except Exception as e:
            print(f"ID: {fid} => ERRO: {e}")
            
    return mapa

if __name__ == '__main__':
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        logger.error("credentials.json não encontrado!")
        exit(1)
        
    try:
        service = authenticate()
        folder_map = check_folder_names(service)
        
        print("\n--- MAPA SUGERIDO ---")
        for k,v in folder_map.items():
            print(f"{k} = {v}")
            
    except Exception as e:
        logger.error(f"Erro Fatal: {e}")
