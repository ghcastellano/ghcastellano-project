import threading
import os
import json
import logging
from src.database import db_session

# ...

from src.models_db import Establishment, Contact, ActionPlan, InspectionStatus
from src.services.drive_service import drive_service
from src.services.pdf_service import pdf_service
from src.whatsapp import WhatsAppService
from src.config import config

logger = logging.getLogger(__name__)

class ApprovalService:
    def process_approval_or_share(self, file_id, data, is_approval=False):
        """
        Orchestrates the approval or sharing process.
        Running heavy tasks (PDF Gen, WhatsApp) in a background thread.
        """
        # 1. Synchronous: Update Contact/DB Data (Fail fast if invalid)
        resp_name = data.get('resp_name')
        resp_phone = data.get('resp_phone')
        contact_id = data.get('contact_id')
        
        if not resp_name or not resp_phone:
            raise ValueError("Nome e Telefone são obrigatórios")
            
        self._update_contact_info(file_id, resp_name, resp_phone, contact_id)
        
        # 2. Async: Generate PDF & Send WhatsApp
        # We pass necessary data to the thread
        thread = threading.Thread(
            target=self._async_generate_and_send,
            args=(file_id, resp_name, resp_phone, is_approval)
        )
        thread.start()
        
        return True

    def _update_contact_info(self, file_id, name, phone, contact_id):
        # ... Logic extracted from app.py ...
        db = next(get_db())
        try:
            json_data = drive_service.read_json(file_id)
            est_name = json_data.get('estabelecimento')
            
            if est_name:
                establishment = db.query(Establishment).filter_by(name=est_name).first()
                if establishment:
                    contact = None
                    if contact_id:
                        contact = db.query(Contact).get(contact_id)
                    
                    if contact:
                        contact.name = name
                        contact.phone = phone
                    else:
                        new_contact = Contact(
                            establishment_id=establishment.id,
                            name=name,
                            phone=phone,
                            role='Responsável'
                        )
                        db.add(new_contact)
                    
                    establishment.responsible_name = name
                    establishment.responsible_phone = phone
                    db.commit()
        except Exception as e:
            logger.error(f"Error updating contact: {e}")
            raise e
        finally:
            db.close()

    def _async_generate_and_send(self, file_id, name, phone, is_approval):
        """Background task"""
        try:
            logger.info(f"Starting Async Task: Share/Approve for {file_id}")
            json_data = drive_service.read_json(file_id)
            est_name = json_data.get('estabelecimento')
            
            # Generate PDF
            pdf_bytes = pdf_service.generate_pdf_bytes(json_data)
            filename = f"Plano_Acao_{est_name.replace(' ', '_')}_{json_data.get('data_inspecao', '').replace('/', '-')}.pdf"
            temp_path = f"/tmp/{filename}"
            
            with open(temp_path, "wb") as f:
                f.write(pdf_bytes)
                
            # Send WhatsApp
            whatsapp = WhatsAppService() # Re-instantiate to be safe in thread
            action = "aprovado" if is_approval else "para revisão"
            caption = f"Olá {name}, segue o Plano de Ação da unidade {est_name} ({action})."
            
            whatsapp.send_document(temp_path, filename, caption, phone)
            
            # Clean up
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
            # Update Status (if approval)
            if is_approval:
                # Update JSON status
                json_data['status'] = 'Aprovado'
                drive_service.update_file(file_id, json.dumps(json_data, indent=2, ensure_ascii=False))
                
                # Update DB (Best effort without explicit ID link)
                # Future: Link Inspection <-> Drive ID properly
                pass
                
            logger.info("Async Task Completed Successfully")
            
        except Exception as e:
            logger.error(f"Async Task Failed: {e}")

approval_service = ApprovalService()
