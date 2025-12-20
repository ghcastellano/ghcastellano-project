import os
import httpx
import logging

logger = logging.getLogger(__name__)

class WhatsAppService:
    def __init__(self):
        self.token = os.getenv("WHATSAPP_TOKEN")
        self.phone_id = os.getenv("WHATSAPP_PHONE_ID")
        self.dest_phone = os.getenv("WHATSAPP_DESTINATION_PHONE") # Fallback
        self.base_url = f"https://graph.facebook.com/v17.0/{self.phone_id}"
        self.headers = {
            "Authorization": f"Bearer {self.token}"
        }

    def send_document(self, file_path, filename=None, caption=None, dest_phone=None):
        if not self.token or not self.phone_id:
            logger.warning("WhatsApp credentials missing. Skipping.")
            return

        target_phone = dest_phone or self.dest_phone
        if not target_phone:
            logger.warning("No destination phone provided.")
            return

        if not filename:
            filename = os.path.basename(file_path)

        # 1. Upload Media
        media_id = self._upload_media(file_path, filename)
        if not media_id:
            return

        # 2. Send Message
        self._send_media_message(media_id, filename, caption, target_phone)

    def _upload_media(self, file_path, filename):
        url = f"{self.base_url}/media"
        # httpx requires files to be passed appropriately
        try:
            with open(file_path, 'rb') as f:
                # 'file' field, (filename, file_object, mime_type)
                files = {'file': (filename, f, 'application/pdf')}
                data = {'messaging_product': 'whatsapp'}
                response = httpx.post(url, headers=self.headers, files=files, data=data, timeout=60)
            
            response.raise_for_status()
            return response.json().get('id')
        except Exception as e:
            logger.error(f"WhatsApp Upload Failed: {e}")
            return None

    def _send_media_message(self, media_id, filename, caption, dest_phone):
        url = f"{self.base_url}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": dest_phone,
            "type": "document",
            "document": {
                "id": media_id,
                "caption": caption or filename,
                "filename": filename
            }
        }
        headers = self.headers.copy() # httpx handles content-type for json
        try:
            response = httpx.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            logger.info(f"WhatsApp Document Sent: {filename}")
        except Exception as e:
            logger.error(f"WhatsApp Send Failed: {e}")
