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
                file_obj.seek(0)
                file_obj.save(target_path)
                
                # Return relative URL
                return f"/static/uploads/{destination_folder}/{filename}"
            except Exception as e:
                logger.error(f"❌ Erro no Upload Local: {e}")
                raise e

# Singleton
storage_service = StorageService()
