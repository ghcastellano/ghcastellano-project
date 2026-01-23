import os
import logging
from werkzeug.utils import secure_filename
from src.config import config

logger = logging.getLogger(__name__)

class StorageService:
    """
    Abstração para upload de arquivos (Local vs Google Cloud Storage).
    """
    def __init__(self, bucket_name=None):
        self.bucket_name = bucket_name or os.getenv('GCP_STORAGE_BUCKET')
        self.client = None
        self._setup_client()

    def _setup_client(self):
        try:
            if self.bucket_name:
                from google.cloud import storage
                self.client = storage.Client()
                logger.info(f"☁️ Storage Service: Configurado para GCS (Bucket: {self.bucket_name})")
            else:
                logger.warning("📂 Storage Service: Bucket não definido. Usando armazenamento LOCAL.")
        except Exception as e:
            logger.error(f"❌ Erro ao inicializar client GCS: {e}")
            self.client = None

    def upload_file(self, file_obj, destination_folder="evidence", filename=None):
        """
        Faz upload de um arquivo.
        Retorna URL pública (http...) ou local (/static...).
        """
        if not filename:
            filename = secure_filename(file_obj.filename)
        
        # 1. Google Cloud Storage
        if self.client and self.bucket_name:
            try:
                bucket = self.client.bucket(self.bucket_name)
                blob_path = f"{destination_folder}/{filename}"
                blob = bucket.blob(blob_path)
                
                # Upload from file object
                file_obj.seek(0)
                blob.upload_from_file(file_obj)
                
                # Make public (optional, or use signed url)
                # blob.make_public() 
                # return blob.public_url
                
                # Better: Return Public Link if bucket is public, or Authenticated Link
                # For this MVP, assuming public bucket or signed URLs needed?
                # Let's assume public-read for simplicity or use mediaLink
                return f"https://storage.googleapis.com/{self.bucket_name}/{blob_path}"
                
            except Exception as e:
                logger.error(f"❌ Erro no Upload GCS: {e}")
                # Fallback to local? No, raise error or fallback.
                raise e

        # 2. Local Storage (Dev / Fallback)
        else:
            try:
                static_folder = 'src/static' # Relative to root run
                if not os.path.exists(static_folder):
                    static_folder = 'static' # Flask default sometimes

                target_dir = os.path.join(static_folder, 'uploads', destination_folder)
                os.makedirs(target_dir, exist_ok=True)
                
                target_path = os.path.join(target_dir, filename)
                if hasattr(file_obj, 'save'):
                    file_obj.seek(0) # Ensure we are at start of file if it was read
                    file_obj.save(target_path)
                else:
                    # Fallback for standard Python file objects (io.BufferedReader, etc.)
                    import shutil
                    # Ensure we are at start of file if it was read
                    if hasattr(file_obj, 'seek'):
                        file_obj.seek(0)
                    
                    with open(target_path, 'wb') as dest_f:
                        shutil.copyfileobj(file_obj, dest_f)
                
                logger.info(f"✅ Arquivo salvo localmente: {target_path}")
                return f"/static/uploads/{destination_folder}/{filename}"
            except Exception as e:
                logger.error(f"❌ Erro no Upload Local: {e}")
                raise e

    def download_file(self, file_path_or_url):
        """
        Baixa arquivo do GCS ou Local.
        Se GCS, espera path relativo ao bucket ou url.
        """
        # Limpar prefixo se vier do processador
        clean_path = file_path_or_url.replace(f"https://storage.googleapis.com/{self.bucket_name}/", "")
        if clean_path.startswith("gcs:"):
            clean_path = clean_path.replace("gcs:", "")

        if self.client and self.bucket_name:
            try:
                bucket = self.client.bucket(self.bucket_name)
                blob = bucket.blob(clean_path)
                return blob.download_as_bytes()
            except Exception as e:
                logger.error(f"❌ Erro Download GCS: {e}")
                return None
        else:
            try:
                # Local: Remove /static prefix if present to find real path
                if clean_path.startswith("/static/"):
                    clean_path = clean_path.replace("/static/", "src/static/")
                elif clean_path.startswith("static/"):
                    clean_path = "src/" + clean_path
                
                # Check root relative
                if not os.path.exists(clean_path):
                     # Try looking in src/static/uploads/evidence if simple filename
                     possible = os.path.join("src/static/uploads/evidence", clean_path)
                     if os.path.exists(possible):
                         clean_path = possible

                with open(clean_path, "rb") as f:
                    return f.read()
            except Exception as e:
                logger.error(f"❌ Erro Download Local: {e}")
                return None

# Singleton
storage_service = StorageService()
