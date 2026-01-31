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

            # [FIX] Reconstruct Data from DB (Source of Truth)
            # Instead of using stale Drive data, we rebuild structure from ActionPlan
            try:
                from src.models_db import Inspection, ActionPlan, ActionPlanItem, ActionPlanItemStatus
                db_async = next(get_db())
                
                insp = db_async.query(Inspection).filter_by(drive_file_id=file_id).first()
                if not insp or not insp.action_plan:
                    logger.warning(f"Inspection/Plan not found for {file_id}, using stale Drive data.")
                    # Fallback to existing json_data if DB lookup fails
                else:
                    plan = insp.action_plan
                    
                    # 1. Base Structure from Stale JSON (for static fields like header)
                    # We still keep basic info like 'estabelecimento', 'data_inspecao' from original JSON
                    # as they might not be fully in DB or formatted differently
                    
                    # 2. Rebuild Areas & Scores
                    # Load original stats to get max scores and base
                    stats = plan.stats_json or {}
                    sector_stats = stats.get('by_sector', {})
                    
                    # Group DB Items by Sector
                    db_items_by_sector = {}
                    for item in plan.items:
                        sec = item.sector or "Geral"
                        if sec not in db_items_by_sector: db_items_by_sector[sec] = []
                        db_items_by_sector[sec].append(item)
                    
                    new_areas_list = []
                    total_score_obtained = stats.get('score', 0) # Start with base (NCs = 0)
                    total_max_score = stats.get('max_score', 100)
                    
                    # Correction Bonus Calculation
                    # If an item is RESOLVED, we add its lost points back?
                    # Assumption: 'pontuacao' in original JSON was the weight.
                    # If item was NC, it contributed 0. If Resolved, it contributes Weight.
                    # We need the weight. 'original_score' in DB is assumed to be Weight/Penalty.
                    
                    correction_bonus_global = 0
                    
                    # Iterate over ALL sectors known (from stats or items)
                    all_sectors = set(list(sector_stats.keys()) + list(db_items_by_sector.keys()))
                    
                    for sec in all_sectors:
                        orig_sec_stat = sector_stats.get(sec, {'score': 0, 'max_score': 0})
                        sec_max = orig_sec_stat.get('max_score', 0)
                        sec_current_score = orig_sec_stat.get('score', 0)
                        
                        items_list = db_items_by_sector.get(sec, [])
                        
                        processed_items = []
                        for item in items_list:
                            # Correction Logic
                            is_corrected = item.status == ActionPlanItemStatus.RESOLVED
                            weight = item.original_score or 0
                            
                            # [REVERTED] User asked NOT to update score, keep original inspection score.
                            # if is_corrected:
                            #    sec_current_score += weight
                            #    correction_bonus_global += weight
                            
                            # Build Item Dict for Template
                            processed_items.append({
                                'item_verificado': item.problem_description,
                                'status': 'Conforme' if is_corrected else (item.original_status or 'Não Conforme'),
                                'is_corrected': is_corrected,
                                'status_real': 'RESOLVED' if is_corrected else 'OPEN', # For template logic
                                'original_status_label': item.original_status or 'Não Conforme',
                                'old_score_display': 0.0, # Assumes 0 for NC
                                'manager_notes': item.manager_notes,
                                'correction_notes': item.manager_notes, # Map to correction notes
                                'evidence_image_url': item.evidence_image_url,
                                'pontuacao': weight
                            })
                        
                        # Cap score at max
                        if sec_current_score > sec_max and sec_max > 0:
                            sec_current_score = sec_max
                        
                        # Calculate Percentage
                        pct = (sec_current_score / sec_max * 100) if sec_max > 0 else 0
                        
                        new_areas_list.append({
                            'nome_area': sec,
                            'pontuacao_obtida': round(sec_current_score, 2),
                            'pontuacao_maxima': round(sec_max, 2),
                            'aproveitamento': round(pct, 2),
                            'itens': processed_items
                        })
                        
                    # Update Global Stats
                    # [REVERTED] No bonus added
                    final_global_score = total_score_obtained # + correction_bonus_global
                    if final_global_score > total_max_score: final_global_score = total_max_score
                    
                    global_pct = (final_global_score / total_max_score * 100) if total_max_score > 0 else 0
                    
                    # Update json_data with Rebuilt Data
                    json_data['areas_inspecionadas'] = new_areas_list
                    json_data['aproveitamento_geral'] = round(global_pct, 2)
                    json_data['pontuacao_global'] = round(final_global_score, 2)
                    
                    # Update Status String
                    status_enum = insp.status
                    status_val = status_enum.value if hasattr(status_enum, 'value') else str(status_enum)
                    if status_val == 'COMPLETED':
                        json_data['status_plano'] = 'CONCLUÍDO'
                    elif status_val in ['APPROVED', 'PENDING_CONSULTANT_VERIFICATION', 'PENDING_MANAGER_REVIEW']:
                        json_data['status_plano'] = 'AGUARDANDO VISITA'
                    else:
                        json_data['status_plano'] = 'EM APROVAÇÃO'

                db_async.close()
            except Exception as e:
                logger.error(f"Error rebuilding PDF data from DB: {e}", exc_info=True)
                # Fallback to original JSON data flow (already loaded)
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
