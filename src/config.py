import os

class Config:
    # Security
    SECRET_KEY = os.getenv("SECRET_KEY", "dev_secret_key_change_in_production")
    
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL")
    
    # Google Cloud
    GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
    GCP_LOCATION = os.getenv("GCP_LOCATION")
    
    # Drive Folders
    FOLDER_ID_01_ENTRADA_RELATORIOS = os.getenv('FOLDER_ID_01_ENTRADA_RELATORIOS', '1nHUNMLNdETy1Wkhu1i5ZSD6fh72fqbTW')
    FOLDER_ID_02_PLANOS_GERADOS = os.getenv('FOLDER_ID_02_PLANOS_GERADOS', '1nBBlpVmTSPdpMZGZA1HjrRmi-_W30qoM')
    FOLDER_ID_03_PROCESSADOS_BACKUP = os.getenv('FOLDER_ID_03_PROCESSADOS_BACKUP', '1kgNrQxQNAp5h_rG3xYzD-a5v38zYvfUw')
    FOLDER_ID_99_ERROS = os.getenv('FOLDER_ID_99_ERROS', '1KHlP7dbeyX8_hUF5Y8mooSu7jnB4ZZzK')
    
    # WhatsApp
    WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
    # Default ID provided by user, but overridable by Env Var
    WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID", "1330168895511682") 
    WHATSAPP_DEST_PHONE = os.getenv("WHATSAPP_DESTINATION_PHONE")
    
    # OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

config = Config()
