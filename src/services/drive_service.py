import os
import io
import json
import logging
import threading
import google.auth
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload, MediaIoBaseUpload

logger = logging.getLogger(__name__)

class DriveService:
    def __init__(self, credentials_file='credentials.json'):
        self.scopes = ['https://www.googleapis.com/auth/drive']
        self.credentials_file = credentials_file
        self.creds = None
        self._service = None
        self.lock = threading.Lock()
        # self._authenticate() # Lazy load instead

    @property
    def service(self):
        if not self._service:
             self._authenticate()
        return self._service

    def _authenticate(self):
        try:
            # 1. Tenta carregar do arquivo local (Dev)
            if os.path.exists(self.credentials_file):
                logger.info(f"🔑 Autenticando usando arquivo: {self.credentials_file}")
                self.creds = Credentials.from_service_account_file(
                    self.credentials_file, scopes=self.scopes)
            
            # 2. Tenta carregar da Env Var GCP_SA_KEY (Prod / GitHub Actions)
            elif os.getenv('GCP_SA_KEY'):
                logger.info("🔑 Autenticando usando JSON em Env Var (GCP_SA_KEY)...")
                info = json.loads(os.getenv('GCP_SA_KEY'))
                self.creds = Credentials.from_service_account_info(info, scopes=self.scopes)
                
            # 3. Fallback para Default Credentials (Cloud Run Identity)
            else:
                logger.info("☁️ Usando Default Credentials (ADC/Cloud Run Identity)...")
                self.creds, _ = google.auth.default(scopes=self.scopes)
            
            # --- IMPERSONATION FIX FOR STORAGE QUOTA ---
            impersonate_email = os.getenv("GOOGLE_DRIVE_IMPERSONATE_EMAIL")
            if impersonate_email and hasattr(self.creds, 'with_subject'):
                logger.info(f"🕶️ Impersonating user: {impersonate_email}")
                self.creds = self.creds.with_subject(impersonate_email)
            elif impersonate_email:
                logger.warning("⚠️ Impersonation requested but credentials do not support with_subject.")
            # -------------------------------------------

            self._service = build('drive', 'v3', credentials=self.creds)
            logger.info("✅ Serviço do Drive Autenticado")
        except Exception as e:
            logger.error(f"❌ Falha ao autenticar no Drive: {e}")
            # Do not re-raise to avoid crashing the app on property access, 
            # effectively disabling Drive features.
            # raise e 
            self._service = None # Ensure it stays None so we might retry or fail gracefully

    def list_files(self, folder_id, mime_type=None, extension=None):
        """Lista arquivos numa pasta, filtrando por tipo ou extensão."""
        if not self.service: # Checks property which triggers auth
            logger.warning("Drive Service indisponível.")
            return []
            
        if not folder_id or folder_id == "None":
            return []
            
        query = f"'{folder_id}' in parents and trashed=false"
        if mime_type:
            query += f" and mimeType='{mime_type}'"
        
        try:
            with self.lock:
                results = self.service.files().list(
                    q=query,
                    fields="files(id, name, mimeType, webViewLink, createdTime, modifiedTime)",
                    orderBy="modifiedTime desc",
                    pageSize=100,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True
                ).execute()
            
            files = results.get('files', [])
            
            if extension:
                files = [f for f in files if f['name'].lower().endswith(extension.lower())]
                
            return files
        except Exception as e:
            logger.error(f"Erro ao listar arquivos: {e}")
            return []

    def download_file(self, file_id):
        """Baixa arquivo e retorna bytes."""
        if not self.service: return b""
        with self.lock:
            # Note: get_media doesn't strictly need supportsAllDrives but it's good practice for consistency
            request = self.service.files().get_media(fileId=file_id)
            file_io = io.BytesIO()
            downloader = MediaIoBaseDownload(file_io, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
        return file_io.getvalue()

    def read_json(self, file_id):
        """Lê o conteúdo de um arquivo JSON diretamente."""
        content = self.download_file(file_id)
        if not content: return {}
        return json.loads(content.decode('utf-8'))

    def upload_file(self, file_path, folder_id, filename=None):
        """Faz upload de um arquivo local para o Drive."""
        if not self.service: raise Exception("Drive Service Unavailable")
        
        if not filename:
            filename = os.path.basename(file_path)
        
        logger.info(f"📤 Tentando upload para pasta Drive: '{folder_id}' (Arquivo: {filename})")
        file_metadata = {
            'name': filename,
            'parents': [folder_id]
        }
        media = MediaFileUpload(file_path, resumable=True)
        
        with self.lock:
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink',
                supportsAllDrives=True
            ).execute()
        
        # Sharing is usually not needed in Shared Drives (permissions inherited), but kept for safe measure
        # self._share_file(file.get('id'))
        
        return file.get('id'), file.get('webViewLink')

    def update_file(self, file_id, new_content_str):
        """Atualiza o conteúdo de um arquivo existente (ex: JSON)."""
        if not self.service: return None
        media = MediaIoBaseUpload(io.BytesIO(new_content_str.encode('utf-8')), mimetype='application/json', resumable=True)
        with self.lock:
            updated = self.service.files().update(
                fileId=file_id,
                media_body=media,
                fields='id',
                supportsAllDrives=True
            ).execute()
        return updated.get('id')

    def move_file(self, file_id, target_folder_id):
        """Move arquivo de uma pasta para outra."""
        if not self.service: return
        try:
            logger.info(f"🔄 Tentando mover arquivo {file_id} para pasta {target_folder_id}")
            if not target_folder_id:
                logger.error("❌ Erro: target_folder_id está vazio!")
                return

            with self.lock:
                file = self.service.files().get(
                    fileId=file_id, 
                    fields='parents',
                    supportsAllDrives=True
                ).execute()
                previous_parents = ",".join(file.get('parents'))
                
                self.service.files().update(
                    fileId=file_id,
                    addParents=target_folder_id,
                    removeParents=previous_parents,
                    fields='id, parents',
                    supportsAllDrives=True
                ).execute()
            logger.info(f"Arquivo {file_id} movido para {target_folder_id}")
        except Exception as e:
            logger.error(f"Erro ao mover arquivo: {e}")

    def _share_file(self, file_id):
        if not self.service: return
        try:
            with self.lock:
                self.service.permissions().create(
                    fileId=file_id,
                    body={'role': 'reader', 'type': 'anyone'}
                ).execute()
        except Exception as e:
            logger.warning(f"Não foi possível compartilhar o arquivo {file_id}: {e}")

    def watch_changes(self, folder_id, callback_url, channel_id, token, expiration=None):
        """
        Registra um Webhook (Channel) para monitorar mudanças numa pasta.
        Expiration: Timestamp em millis (opcional). Default Drive é ~1 semana.
        """
        if not self.service: return None
        body = {
            "id": channel_id,
            "type": "web_hook",
            "address": callback_url,
            "token": token
        }
        if expiration:
            body["expiration"] = expiration

        try:
            # The watch method is typically on the files collection, not a specific fileId for folder changes.
            # However, the instruction uses fileId=folder_id, which implies watching changes *to* the folder itself,
            # or changes *within* the folder if the API supports it this way.
            # For watching changes *within* a folder, one would typically use the Changes API.
            # Assuming the instruction intends to watch the folder as a file resource.
            with self.lock:
                return self.service.files().watch(
                    fileId=folder_id,
                    body=body,
                    supportsAllDrives=True # Added for consistency with other methods
                ).execute()
        except Exception as e:
            logger.error(f"Error watching changes for folder {folder_id}: {e}")
            raise e

    def stop_watch(self, channel_id, resource_id):
        """Para de receber notificações."""
        if not self.service: return
        try:
            with self.lock:
                self.service.channels().stop(
                    body={
                        "id": channel_id,
                        "resourceId": resource_id
                    }
                ).execute()
            logger.info(f"Stopped watch for channel {channel_id} with resource {resource_id}")
        except Exception as e:
            logger.error(f"Error stopping watch for channel {channel_id}: {e}")

# Singleton Instance
drive_service = DriveService()
