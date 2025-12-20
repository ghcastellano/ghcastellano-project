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
    FOLDER_ID_01_ENTRADA_RELATORIOS = os.getenv('FOLDER_ID_01_ENTRADA_RELATORIOS')
    FOLDER_ID_02_PLANOS_GERADOS = os.getenv('FOLDER_ID_02_PLANOS_GERADOS')
    FOLDER_ID_03_PROCESSADOS_BACKUP = os.getenv('FOLDER_ID_03_PROCESSADOS_BACKUP')
    FOLDER_ID_99_ERROS = os.getenv('FOLDER_ID_99_ERROS')
    
    # WhatsApp
    WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
    # Default ID provided by user, but overridable by Env Var
    WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID") 
    WHATSAPP_DEST_PHONE = os.getenv("WHATSAPP_DESTINATION_PHONE")
    
    # OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

config = Config()
