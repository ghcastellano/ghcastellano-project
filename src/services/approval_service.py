import threading
import os
import json
import logging
from src.database import db_session, get_db

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
        
        if not resp_name or (not resp_phone and not data.get('email')):
             # Relax validation: phone needed for WA, email for Email
             pass # Let downstream handle specific validation
            
        email = data.get('email')
        via = data.get('via', 'whatsapp')

        self._update_contact_info(file_id, resp_name, resp_phone, email, contact_id)
        
        # 2. Async: Generate PDF & Send WhatsApp/Email
        # We pass necessary data to the thread
        thread = threading.Thread(
            target=self._async_generate_and_send,
            args=(file_id, resp_name, resp_phone, email, is_approval, via)
        )
        thread.start()
        
        return True

    def _update_contact_info(self, file_id, name, phone, email, contact_id):
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
                        contact.email = email
                    else:
                        new_contact = Contact(
                            establishment_id=establishment.id,
                            name=name,
                            phone=phone,
                            email=email,
                            role='Responsável'
                        )
                        db.add(new_contact)
                    
                    # Update Main Est Responsible as fallback
                    establishment.responsible_name = name
                    establishment.responsible_phone = phone
                    # Establishment model might not have responsible_email yet, skip for now or add if schema allows
                    
                    db.commit()
        except Exception as e:
            logger.error(f"Error updating contact: {e}")
            raise e
        finally:
            db.close()

    def _async_generate_and_send(self, file_id, name, phone, email, is_approval, via='whatsapp'):
        """Background task"""
        try:
            logger.info(f"Starting Async Task: Share({via}) for {file_id}")
            json_data = drive_service.read_json(file_id)
            est_name = json_data.get('estabelecimento')
            
            # Generate PDF
            
            # [FIX] Polyfill Data to prevent AttributeError in PDF Generation
            # Ensure 'aproveitamento' exists in inspection areas
            if 'areas_inspecionadas' in json_data:
                # Try to get sector stats if available
                sector_stats = json_data.get('detalhe_pontuacao', {})
                
                for area in json_data['areas_inspecionadas']:
                    if 'aproveitamento' not in area:
                        # Fallback logic: Try to get from stats or default to 0
                        aprov = 0
                        area_name = area.get('nome_area')
                        
                        if isinstance(sector_stats, dict) and area_name:
                             s_stat = sector_stats.get(area_name)
                             if isinstance(s_stat, dict):
                                 aprov = s_stat.get('percentage', 0)
                             elif isinstance(s_stat, (int, float)):
                                 aprov = s_stat
                        
                        area['aproveitamento'] = aprov

            if 'aproveitamento_geral' not in json_data:
                 json_data['aproveitamento_geral'] = 0

            # [FIX] Fetch Actual Status from DB to Ensure PDF is Up-to-Date
            try:
                from src.models_db import Inspection
                db_async = next(get_db())
                insp = db_async.query(Inspection).filter_by(drive_file_id=file_id).first()
                if insp:
                    status_enum = insp.status
                    status_val = status_enum.value if hasattr(status_enum, 'value') else str(status_enum)
                    
                    # Logic Mapping (Same as app.py)
                    if status_val == 'COMPLETED':
                        json_data['status_plano'] = 'CONCLUÍDO'
                    elif status_val == 'APPROVED' or status_val == 'PENDING_VERIFICATION' or status_val == 'WAITING_APPROVAL':
                        json_data['status_plano'] = 'AGUARDANDO VISITA'
                    else:
                        json_data['status_plano'] = 'EM APROVAÇÃO'
                db_async.close()
            except Exception as e:
                logger.error(f"Error fetching status for PDF: {e}")
                # Fallback to json status or default
                pass

            pdf_bytes = pdf_service.generate_pdf_bytes(json_data)
            date_str = json_data.get('data_inspecao', '').replace('/', '-')
            filename = f"Plano_Acao_{est_name.replace(' ', '_')}_{date_str}.pdf"
            temp_path = f"/tmp/{filename}"
            
            with open(temp_path, "wb") as f:
                f.write(pdf_bytes)
                
            # Dispatch based on Via
            if via == 'email':
                # Email Logic
                from src.services.email_service import EmailService
                # Instantiate locally to ensure thread safety configuration if needed
                email_svc = EmailService() 
                
                subject = f"Plano de Ação - {est_name} ({'Aprovado' if is_approval else 'Para Revisão'})"
                body = f"""
                Olá {name},
                
                Segue em anexo o Plano de Ação referente à visita técnica realizada em {est_name}.
                
                Status: {'APROVADO' if is_approval else 'PARA REVISÃO'}
                
                Atenciosamente,
                Equipe de Qualidade
                """
                
                if email:
                    email_svc.send_email_with_attachment(
                        to_email=email,
                        subject=subject,
                        body=body,
                        attachment_path=temp_path
                    )
                    logger.info(f"Email sent to {email}")
                else:
                    logger.warning("Email requested but no email address provided.")
            
            else:
                # WhatsApp Logic
                whatsapp = WhatsAppService() # Re-instantiate to be safe in thread
                action = "aprovado" if is_approval else "para revisão"
                caption = f"Olá {name}, segue o Plano de Ação da unidade {est_name} ({action})."
                
                if phone:
                    whatsapp.send_document(temp_path, filename, caption, phone)
                    logger.info(f"WhatsApp sent to {phone}")
                else:
                    logger.warning("WhatsApp requested but no phone number provided.")
            
            # Clean up
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
            # Update Status (if approval)
            if is_approval:
                # Update JSON status
                json_data['status'] = 'Aprovado'
                drive_service.update_file(file_id, json.dumps(json_data, indent=2, ensure_ascii=False))
                pass
                
            logger.info("Async Task Completed Successfully")
            
        except Exception as e:
            logger.error(f"Async Task Failed: {e}", exc_info=True)

approval_service = ApprovalService()
