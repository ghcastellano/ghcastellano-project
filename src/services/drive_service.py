import os
import io
import json
import logging
import threading
import google.auth
from src.config_helper import get_config
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload, MediaIoBaseUpload

logger = logging.getLogger(__name__)

class DriveService:
    def __init__(self, credentials_file='credentials.json'):
        # drive.file is insufficient: app needs access to pre-existing folders
        # (ROOT_FOLDER_ID created manually in Drive). drive.file only allows
        # access to files/folders created by the app itself.
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
            
            # 2. [NEW] Authenticate as User (OAuth) via Env Var - Fixes Storage Quota
            elif get_config('GCP_OAUTH_TOKEN'):
                # import json (Removed to avoid UnboundLocalError)
                import base64
                from google.oauth2.credentials import Credentials as UserCredentials
                logger.info("🔑 Autenticando usando OAuth User Token (GCP_OAUTH_TOKEN)...")

                token_str = get_config('GCP_OAUTH_TOKEN')
                # Auto-Detect Base64: If it doesn't look like JSON (starts with {), try decoding
                if token_str and not token_str.strip().startswith('{'):
                    try:
                        token_str = base64.b64decode(token_str).decode('utf-8')
                        logger.info("🔓 Token decodificado de Base64 com sucesso.")
                    except Exception as e:
                        logger.error(f"⚠️ Falha ao decodificar Base64 Token, tentando raw: {e}")
                
                try:
                    info = json.loads(token_str)
                except json.JSONDecodeError as json_error:
                    # Common User Error: Pasting Python Dict (Single Quotes) instead of JSON
                    try:
                        import ast
                        logger.warning(f"⚠️ JSON inválido (Single Quotes?), tentando ast.literal_eval... Erro original: {json_error}")
                        info = ast.literal_eval(token_str)
                    except Exception as ast_error:
                        logger.error(f"❌ Falha crítica ao parsear token OAuth: {ast_error}")
                        raise json_error
                
                self.creds = UserCredentials.from_authorized_user_info(info, self.scopes)

            # 3. Tenta carregar da Env Var GCP_SA_KEY (Prod / GitHub Actions)
            elif get_config('GCP_SA_KEY'):
                logger.info("🔑 Autenticando usando JSON em Env Var (GCP_SA_KEY)...")
                info = json.loads(get_config('GCP_SA_KEY'))
                self.creds = Credentials.from_service_account_info(info, scopes=self.scopes)
                
            # 4. Fallback para Default Credentials (Cloud Run Identity)
            else:
                logger.info("☁️ Usando Default Credentials (ADC/Cloud Run Identity)...")
                self.creds, _ = google.auth.default(scopes=self.scopes)
            
            # --- IMPERSONATION FIX FOR STORAGE QUOTA ---
            impersonate_email = get_config("GOOGLE_DRIVE_IMPERSONATE_EMAIL")
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

    def create_folder(self, folder_name, parent_id=None):
        """Cria uma pasta no Drive e retorna ID e Link."""
        if not self.service: return None, None
        
        try:
            logger.info(f"📁 Criando pasta '{folder_name}' (Parent: {parent_id})")
            
            # [IMPROVEMENT] Verificar se pasta já existe antes de criar
            if parent_id:
                existing_folders = self.list_files(parent_id, mime_type='application/vnd.google-apps.folder')
                for folder in existing_folders:
                    if folder.get('name') == folder_name:
                        logger.warning(f"⚠️ Pasta '{folder_name}' já existe no parent {parent_id}, reutilizando")
                        return folder.get('id'), folder.get('webViewLink')
            
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            if parent_id:
                file_metadata['parents'] = [parent_id]
                
            with self.lock:
                file = self.service.files().create(
                    body=file_metadata,
                    fields='id, webViewLink',
                    supportsAllDrives=True
                ).execute()
                
            logger.info(f"✅ Pasta Criada: {file.get('id')}")
            return file.get('id'), file.get('webViewLink')
            
        except Exception as e:
            logger.error(f"❌ Erro ao criar pasta {folder_name}: {e}")
            return None, None

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
        
        import time
        for attempt in range(3):
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
            except (BrokenPipeError, ConnectionResetError, OSError) as e:
                if attempt < 2:
                    logger.warning(f"Erro de conexão ao listar arquivos (tentativa {attempt+1}/3): {e}")
                    time.sleep(2 ** attempt)
                    continue
                logger.error(f"Erro ao listar arquivos após 3 tentativas: {e}")
                return []
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
        try:
            data = json.loads(content.decode('utf-8'))
            return data if data is not None else {}
        except Exception as e:
            logger.error(f"Erro ao parsear JSON {file_id}: {e}")
            return {}

    def upload_file(self, file_path, folder_id, filename=None):
        """Faz upload de um arquivo local para o Drive com Retry Logic."""
        if not self.service: raise Exception("Drive Service Unavailable")
        
        if not filename:
            filename = os.path.basename(file_path)
        
        logger.info(f"📤 Tentando upload para pasta Drive: '{folder_id}' (Arquivo: {filename})")
        file_metadata = {
            'name': filename,
            'parents': [folder_id]
        }
        
        # Retry Logic (3 Attempts)
        import time
        import random
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                # Re-create MediaFileUpload for each attempt to reset stream position
                media = MediaFileUpload(file_path, resumable=True)
                
                with self.lock:
                    file = self.service.files().create(
                        body=file_metadata,
                        media_body=media,
                        fields='id, webViewLink',
                        supportsAllDrives=True
                    ).execute()
                
                # Success
                return file.get('id'), file.get('webViewLink')

            except Exception as e:
                msg = str(e).lower()
                # Fail fast on Quota/Auth errors (don't retry as they won't change)
                if "quota" in msg or "403" in msg or "limit" in msg or "usage" in msg:
                    logger.warning(f"🛑 Aborting retries for {filename} due to detailed error: {msg}")
                    raise e

                logger.warning(f"⚠️ Upload attempt {attempt+1}/{max_retries} failed for {filename}: {str(e)}")
                if attempt == max_retries - 1:
                    logger.error(f"❌ Upload failed permanently for {filename}")
                    raise e
                
                # Exponential Backoff + Jitter
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                time.sleep(wait_time)

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

    def delete_folder(self, folder_id):
        """Deleta uma pasta (e todo seu conteúdo) do Google Drive."""
        if not self.service or not folder_id:
            return False
        try:
            logger.info(f"🗑️ Deletando pasta do Drive: {folder_id}")
            with self.lock:
                self.service.files().delete(
                    fileId=folder_id,
                    supportsAllDrives=True
                ).execute()
            logger.info(f"✅ Pasta {folder_id} deletada do Drive")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Falha ao deletar pasta {folder_id} do Drive: {e}")
            return False

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
            with self.lock:
                # Legacy method strictly for folder watch if needed
                return self.service.files().watch(
                    fileId=folder_id,
                    body=body,
                    supportsAllDrives=True
                ).execute()
        except Exception as e:
            logger.error(f"Error watching changes for folder {folder_id}: {e}")
            raise e

    def get_start_page_token(self):
        """Obtém o token inicial para monitorar mudanças globais."""
        if not self.service: return None
        try:
            with self.lock:
                response = self.service.changes().getStartPageToken(supportsAllDrives=True).execute()
            return response.get('startPageToken')
        except Exception as e:
            logger.error(f"Error getting start page token: {e}")
            return None

    def list_changes(self, page_token):
        """Lista mudanças ocorridas desde o page_token fornecido."""
        if not self.service: return [], None
        try:
            with self.lock:
                response = self.service.changes().list(
                    pageToken=page_token,
                    fields='nextPageToken, newStartPageToken, changes(fileId, file(name, parents, mimeType, webViewLink, createdTime), time, removed)',
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                    pageSize=100
                ).execute()
            return response.get('changes', []), response.get('newStartPageToken') or response.get('nextPageToken')
        except Exception as e:
            logger.error(f"Error listing changes: {e}")
            return [], None

    def watch_global_changes(self, callback_url, channel_id, token, page_token=None, expiration=None):
        """
        Monitora TODAS as mudanças no Drive (Global Webhook).
        Requires page_token to define start point (recommended).
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
            with self.lock:
                kwargs = {
                    "body": body,
                    "supportsAllDrives": True,
                    "includeItemsFromAllDrives": True
                }
                if page_token:
                    kwargs["pageToken"] = page_token
                    
                return self.service.changes().watch(**kwargs).execute()
        except Exception as e:
            logger.error(f"Error watching global changes: {e}")
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
