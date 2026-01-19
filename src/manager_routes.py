from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from src.database import get_db
from src.models_db import User, UserRole, Establishment, Inspection, ActionPlan, ActionPlanItem, ActionPlanItemStatus, SeverityLevel, InspectionStatus, Company
from flask import current_app, jsonify
from datetime import datetime
from sqlalchemy.orm import joinedload, defer
from sqlalchemy.exc import IntegrityError
from src.services.email_service import EmailService # Mock verify first
from werkzeug.security import generate_password_hash
from flask import session
import uuid
import random
import string

manager_bp = Blueprint('manager', __name__)

def generate_temp_password(length=8):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

@manager_bp.route('/dashboard/manager')
@login_required
def dashboard_manager():
    # Role Check
    if current_user.role != UserRole.MANAGER:
        flash('Acesso negado', 'error')
        return redirect(url_for('root'))
        
    # Setup for Manager Dashboard
    establishment_id = request.args.get('establishment_id')
    
    db = next(get_db())
    try:
        # Carrega dados necessários para dropdowns e listas
        # Garante que a relação da empresa seja carregada
        establishments = []
        # Recarrega current_user para garantir sessão anexada se necessário (opcional)
        
        company = db.query(Company).get(current_user.company_id) if current_user.company_id else None
        all_establishments = [] # Inicializa por segurança
        if company:
            # Ordena Estabelecimentos por Nome
            all_establishments = sorted(company.establishments, key=lambda x: x.name)
            establishments = all_establishments # Padrão: todos
            
        consultants = db.query(User).filter(
            User.role == UserRole.CONSULTANT,
            User.company_id == current_user.company_id
        ).order_by(User.name.asc()).all()
        
        # Filtra Lógica de Persistência
        if establishment_id is not None:
            if establishment_id:
                session['selected_est_id'] = establishment_id
            else:
                # Usuário selecionou "Todas as Lojas" (valor vazio) -> Limpa Sessão
                session.pop('selected_est_id', None)
                establishment_id = None
        elif 'selected_est_id' in session:
            establishment_id = session['selected_est_id']
            
        # Aplica Filtro se selecionado
        if establishment_id:
             # Valida se ID pertence à empresa
             target = next((e for e in all_establishments if str(e.id) == establishment_id), None)
             if target:
                 establishments = [target]
                 # Filtra consultores vinculados a esta loja
                 consultants = [c for c in consultants if target in c.establishments]
        
        return render_template('dashboard_manager_v2.html', 
                               user_role='MANAGER',
                               establishments=establishments,     # For Tables
                               all_establishments=all_establishments, # For Dropdowns
                               consultants=consultants,
                               selected_est_id=establishment_id)
    finally:
        db.close()
@manager_bp.route('/api/tracker/<uuid:inspection_id>')
@login_required
def tracker_details(inspection_id):
    if current_user.role != UserRole.MANAGER:
        return jsonify({'error': 'Unauthorized'}), 403
        
    db = next(get_db())
    try:
        insp = db.query(Inspection).options(joinedload(Inspection.processing_logs)).get(inspection_id)
        if not insp:
            return jsonify({'error': 'Not found'}), 404
            
        # Security Check: Must belong to manager's company
        # Navigate through establishment -> company
        if not insp.establishment or insp.establishment.company_id != current_user.company_id:
             return jsonify({'error': 'Unauthorized access to this inspection'}), 403

        # Analyze Logs / Status
        logs = insp.processing_logs or []
        status = insp.status.value
        
        # Determine Progress Steps
        steps = {
            'upload': {'status': 'completed', 'label': 'Upload Recebido'},
            'ai_process': {'status': 'pending', 'label': 'Processamento IA'},
            'db_save': {'status': 'pending', 'label': 'Estruturação de Dados'},
            'plan_gen': {'status': 'pending', 'label': 'Geração do Plano'},
            'analysis': {'status': 'pending', 'label': 'Análise do Gestor'}
        }
        
        # Logic to mark steps based on logs or final status
        has_logs = len(logs) > 0
        
        # 1. Upload
        # Always true if we are here via file_id
        
        # 2. AI Processing
        # If logs show "Processing started" or any "AI" stage
        if has_logs or status != 'PROCESSING':
             steps['ai_process']['status'] = 'completed'
             
        # 3. DB Structure
        # If we have ActionPlan attached or logs indicate 'DB_SAVE'
        if insp.action_plan or (has_logs and any('saved' in l.get('message', '').lower() for l in logs)):
             steps['ai_process']['status'] = 'completed' # Reinforce
             steps['db_save']['status'] = 'completed'
             
        # 4. Plan Gen
        # If ActionPlan exists and has items
        if insp.action_plan:
             steps['db_save']['status'] = 'completed'
             steps['plan_gen']['status'] = 'completed'
             
        # 5. Analysis
        if status in ['PENDING', 'APPROVED', 'REJECTED']:
             steps['plan_gen']['status'] = 'completed'
             steps['analysis']['status'] = 'current' if status == 'PENDING' else 'completed'
             if status == 'APPROVED': steps['analysis']['label'] = 'Aprovado'
             
        # Error handling
        if 'ERROR' in status or 'FAILED' in status:
            # Find where it failed
            failed_step = 'ai_process' # Default
            if steps['db_save']['status'] == 'completed': failed_step = 'plan_gen'
            # Mark as error
            steps[failed_step]['status'] = 'error'
            
        return jsonify({
            'id': str(insp.id),
            'filename': insp.processed_filename or "Arquivo",
            'status': status,
            'steps': steps,
            'logs': [l.get('message') for l in logs[-5:]] # Last 5 logs
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@manager_bp.route('/manager/consultant/new', methods=['POST'])
@login_required
def create_consultant():
    if current_user.role != UserRole.MANAGER:
        flash('Acesso negado', 'error')
        return redirect(url_for('root'))
        
    name = request.form.get('name')
    email = request.form.get('email')
    establishment_ids = request.form.getlist('establishment_ids') # GET LIST
    
    if not name or not email or not establishment_ids:
        if request.accept_mimetypes.accept_json:
             return jsonify({'error': 'Preencha todos os campos e selecione lojas.'}), 400
        flash('Preencha todos os campos e selecione ao menos um estabelecimento', 'error')
        return redirect(url_for('manager.dashboard_manager'))
        
    db = next(get_db())
    try:
        # Verifica permissões e estabelecimentos existentes
        establishments_to_assign = []
        for est_id in establishment_ids:
            try:
                est = db.query(Establishment).get(uuid.UUID(est_id))
                if est:
                    establishments_to_assign.append(est)
            except:
                pass
        
        if not establishments_to_assign:
            if request.accept_mimetypes.accept_json:
                 return jsonify({'error': 'Nenhuma loja válida selecionada.'}), 400
            flash('Nenhum estabelecimento válido selecionado.', 'error')
            return redirect(url_for('manager.dashboard_manager'))

        # Verifica se usuário existe
        if db.query(User).filter_by(email=email).first():
            if request.accept_mimetypes.accept_json:
                 return jsonify({'error': 'Email já cadastrado.'}), 400
            flash('Email já cadastrado.', 'error')
            return redirect(url_for('manager.dashboard_manager'))
            
        temp_pass = generate_temp_password()
        hashed = generate_password_hash(temp_pass)
        
        user = User(
            name=name,
            email=email,
            password_hash=hashed,
            role=UserRole.CONSULTANT,
            company_id=current_user.company_id, 
            must_change_password=True
        )
        
        # Atribuição M2M (Muitos para Muitos)
        user.establishments = establishments_to_assign
        
        db.add(user)
        db.commit()
        
        msg = f'Consultor criado com {len(establishments_to_assign)} estabelecimentos! Senha: {temp_pass}'
        
        if request.accept_mimetypes.accept_json:
             return jsonify({
                 'success': True,
                 'message': msg,
                 'consultant': {
                     'id': str(user.id),
                     'name': user.name,
                     'email': user.email,
                     'establishment_ids': [str(e.id) for e in user.establishments]
                 }
             }), 201
        
        flash(msg, 'success')
        
    except IntegrityError:
        db.rollback()
        if request.accept_mimetypes.accept_json:
             return jsonify({'error': 'Email já cadastrado.'}), 409
        flash('Email já cadastrado.', 'error')
    except Exception as e:
        db.rollback()
        if request.accept_mimetypes.accept_json:
             return jsonify({'error': str(e)}), 500
        flash(f'Erro: {e}', 'error')
    finally:
        db.close()
        
    return redirect(url_for('manager.dashboard_manager'))

@manager_bp.route('/manager/consultant/<uuid:user_id>/update', methods=['POST'])
@login_required
def update_consultant(user_id):
    if current_user.role != UserRole.MANAGER:
        return jsonify({'error': 'Acesso negado'}), 403
        
    name = request.form.get('name')
    email = request.form.get('email')
    password = request.form.get('password')
    establishment_ids = request.form.getlist('establishment_ids')
    
    if not name or not email:
        return jsonify({'error': 'Nome e Email são obrigatórios.'}), 400
        
    db = next(get_db())
    try:
        user = db.query(User).get(user_id)
        if not user or user.role != UserRole.CONSULTANT:
             return jsonify({'error': 'Consultor não encontrado.'}), 404
             
        # Verifica posse (Consultor deve pertencer à empresa do Gestor)
        if user.company_id != current_user.company_id:
             return jsonify({'error': 'Acesso negado a este consultor.'}), 403
             
        user.name = name
        user.email = email
        
        if password and len(password.strip()) > 0:
            user.password_hash = generate_password_hash(password)
            
        # Update Establishments
        if establishment_ids:
            new_establishments = []
            for est_id in establishment_ids:
                est = db.query(Establishment).get(uuid.UUID(est_id))
                if est and est.company_id == current_user.company_id:
                    new_establishments.append(est)
            user.establishments = new_establishments
            
        db.commit()

        
        # Prepare response data
        consultant_data = {
            'id': str(user.id),
            'name': user.name,
            'email': user.email,
            'establishment_ids': [str(e.id) for e in user.establishments]
        }
        
        return jsonify({'success': True, 'message': 'Consultor atualizado!', 'consultant': consultant_data}), 200
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()

@manager_bp.route('/manager/consultant/<uuid:user_id>/delete', methods=['POST'])
@login_required
def delete_consultant(user_id):
    if current_user.role != UserRole.MANAGER:
        return jsonify({'error': 'Acesso negado'}), 403
        
    db = next(get_db())
    try:
        user = db.query(User).get(user_id)
        if not user or user.role != UserRole.CONSULTANT:
            return jsonify({'error': 'Consultor não encontrado'}), 404
        if user.company_id != current_user.company_id:
            return jsonify({'error': 'Acesso negado'}), 403
            
        db.delete(user)
        db.commit()
        return jsonify({'success': True, 'message': 'Consultor removido!'}), 200
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()

@manager_bp.route('/manager/establishment/new', methods=['POST'])
@login_required
def create_establishment():
    if current_user.role != UserRole.MANAGER:
        flash('Acesso negado', 'error')
        return redirect(url_for('root'))
        
    name = request.form.get('name')
    code = request.form.get('code')
    
    if not name:
        if request.accept_mimetypes.accept_json:
             return jsonify({'error': 'Nome é obrigatório.'}), 400
        flash('Nome do estabelecimento é obrigatório.', 'error')
        return redirect(url_for('manager.dashboard_manager'))
        
    if not current_user.company_id:
        if request.accept_mimetypes.accept_json:
             return jsonify({'error': 'Gestor sem empresa vinculada.'}), 400
        flash('Erro: Gestor não está vinculado a uma empresa.', 'error')
        return redirect(url_for('manager.dashboard_manager'))
        
    db = next(get_db())
    try:
        est = Establishment(
            name=name,
            code=code,
            company_id=current_user.company_id, # Link auto to manager's company
            drive_folder_id="", # Optional init
            responsible_name=request.form.get('responsible_name'),
            responsible_email=request.form.get('responsible_email'), # NEW FIELD
            responsible_phone=request.form.get('responsible_phone')
        )
        
        # [NEW] Drive Folder - Level 2: Establishment
        try:
             # Find Company Folder ID
             company = db.query(Company).get(current_user.company_id)
             if company and company.drive_folder_id:
                 from src.app import drive_service
                 if drive_service.service:
                     f_id, f_link = drive_service.create_folder(folder_name=name, parent_id=company.drive_folder_id)
                     if f_id:
                         est.drive_folder_id = f_id
             else:
                 current_app.logger.warning(f"⚠️ Company {company.name} has no Drive Folder ID. Skipping Est folder.")
                 
        except Exception as drive_err:
             current_app.logger.error(f"Failed to create Drive folder for Establishment: {drive_err}")

        db.add(est)
        db.commit()
        
        msg = f'Estabelecimento {name} criado com sucesso!'
        
        if request.accept_mimetypes.accept_json:
             return jsonify({
                 'success': True,
                 'message': msg,
                 'establishment': {
                     'id': str(est.id),
                     'name': est.name,
                     'code': est.code,
                     'responsible_name': est.responsible_name,
                     'responsible_email': est.responsible_email,
                     'responsible_phone': est.responsible_phone
                 }
             }), 201
             
        flash(msg, 'success')
    except Exception as e:
        db.rollback()
        if request.accept_mimetypes.accept_json:
             return jsonify({'error': str(e)}), 500
        flash(f'Erro ao criar estabelecimento: {e}', 'error')
    finally:
        db.close()
        
    return redirect(url_for('manager.dashboard_manager'))

@manager_bp.route('/manager/establishment/<uuid:est_id>/update', methods=['POST'])
@login_required
def update_establishment(est_id):
    if current_user.role != UserRole.MANAGER:
        return jsonify({'error': 'Acesso negado'}), 403
        
    name = request.form.get('name')
    code = request.form.get('code')
    
    if not name:
        return jsonify({'error': 'Nome é obrigatório.'}), 400
        
    db = next(get_db())
    try:
        est = db.query(Establishment).get(est_id)
        if not est:
             return jsonify({'error': 'Estabelecimento não encontrado.'}), 404
             
        # Check ownership
        if est.company_id != current_user.company_id:
             return jsonify({'error': 'Acesso negado a este estabelecimento.'}), 403
             
        est.name = name
        est.code = code
        est.responsible_name = request.form.get('responsible_name')
        est.responsible_email = request.form.get('responsible_email') # NEW FIELD
        est.responsible_phone = request.form.get('responsible_phone')
        db.commit()
        
        est_data = {
            'id': str(est.id),
            'name': est.name,
            'code': est.code,
            'responsible_name': est.responsible_name,
            'responsible_email': est.responsible_email,
            'responsible_phone': est.responsible_phone
        }
        return jsonify({'success': True, 'message': 'Estabelecimento atualizado!', 'establishment': est_data}), 200
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()

@manager_bp.route('/manager/establishment/<uuid:est_id>/delete', methods=['POST'])
@login_required
def delete_establishment(est_id):
    if current_user.role != UserRole.MANAGER:
        return jsonify({'error': 'Acesso negado'}), 403
        
    db = next(get_db())
    try:
        est = db.query(Establishment).get(est_id)
        if not est:
            return jsonify({'error': 'Estabelecimento não encontrado'}), 404
        if est.company_id != current_user.company_id:
            return jsonify({'error': 'Acesso negado'}), 403
            
        db.delete(est)
        db.commit()
        return jsonify({'success': True, 'message': 'Estabelecimento removido!'}), 200
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()

@manager_bp.route('/manager/plan/<file_id>', methods=['GET'])
@login_required
def edit_plan(file_id):
    # [CHANGED] Allow Consultants to View/Edit Plan
    if current_user.role not in [UserRole.MANAGER, UserRole.ADMIN, UserRole.CONSULTANT]:
        flash('Acesso não autorizado.', 'error')
        return redirect(url_for('dashboard.dashboard_manager'))
    
    db = next(get_db())
    try:
        # 1. Tenta encontrar Inspeção no BD (Defere colunas pesadas/ausentes)
        inspection = db.query(Inspection).options(defer(Inspection.processing_logs)).filter_by(drive_file_id=file_id).first()
        
        # 2. Migration Logic (On-the-Fly)
        if not inspection or not inspection.action_plan:
            print(f"⚠️ [MIGRATION] Plan not found for {file_id}. Attempting import from Drive...")
            drive = current_app.drive_service
            if not drive:
                flash('Erro de conexão com Drive', 'error')
                return redirect(url_for('manager.dashboard_manager'))
            
            try:
                # Read legacy JSON
                data = drive.read_json(file_id)
                if data is None: data = {} # Defensive fix for 'None' attribute error
                
                # Create/Get Inspection if missing
                if not inspection:
                    # Link to Establishment if possible
                    est_name = data.get('estabelecimento')
                    est = db.query(Establishment).filter_by(name=est_name).first()
                    
                    inspection = Inspection(
                        drive_file_id=file_id,
                        status=InspectionStatus.PENDING_MANAGER_REVIEW,
                        # client_id removed
                        establishment_id=est.id if est else None,
                        ai_raw_response=data
                    )
                    db.add(inspection)
                    db.flush() # get ID
                
                # Create Action Plan
                plan = ActionPlan(
                    inspection_id=inspection.id,
                )
                db.add(plan)
                db.flush()
                
                # Parse Items from JSON
                items_data = data.get('nao_conformidades', [])
                for item in items_data:
                    # Map priority string to Enum
                    sev_str = item.get('gravidade', 'MEDIUM').upper()
                    try:
                        severity = SeverityLevel[sev_str]
                    except:
                        severity = SeverityLevel.MEDIUM
                        
                    db_item = ActionPlanItem(
                        action_plan_id=plan.id,
                        problem_description=item.get('problema', 'N/A'),
                        corrective_action=item.get('acao_corretiva', 'N/A'),
                        legal_basis=item.get('base_legal'),
                        severity=severity,
                        status=ActionPlanItemStatus.OPEN
                    )
                    db.add(db_item)
                
                db.commit()
                flash('Relatório importado com sucesso para edição.', 'success')
                
            except Exception as e:
                db.rollback()
                print(f"Migration Failed: {e}")
                flash(f'Erro ao importar relatório antigo: {e}', 'error')
                return redirect(url_for('manager.dashboard_manager'))
                
        # Reload to ensure relationships
        db.refresh(inspection)

        # Prepare report_data for template (Stats & NCs structure)
        # 1. Use existing stats_json if available (Source of Truth for Structure/Scores)
            # [FIX] Merge Logic: Start with AI Raw (Base) + Overlay ActionPlan stats (Edits)
        ai_raw = inspection.ai_raw_response or {}
        report_data = ai_raw.copy()
        
        if inspection.action_plan and inspection.action_plan.stats_json:
            # Update with saved stats (preserves edits)
            report_data.update(inspection.action_plan.stats_json)

        # [Normalization] Ensure keys match Template expectations (Legacy Support)
        if 'aproveitamento_geral' not in report_data:
            report_data['aproveitamento_geral'] = report_data.get('percentage', 0)
        
        # [FIX] Resumo Priority: DB Edit > AI Raw
        if inspection.action_plan and inspection.action_plan.summary_text:
             report_data['resumo_geral'] = inspection.action_plan.summary_text
        elif not report_data.get('resumo_geral') and not report_data.get('summary'):
             report_data['resumo_geral'] = ai_raw.get('summary') or ai_raw.get('summary_text') or "Resumo não disponível."
            
        if 'nome_estabelecimento' not in report_data:
             report_data['nome_estabelecimento'] = report_data.get('company_name') or inspection.establishment.name if inspection.establishment else "Estabelecimento"

        if 'data_inspecao' not in report_data:
             report_data['data_inspecao'] = report_data.get('inspection_date') or inspection.created_at.strftime('%d/%m/%Y')

        # Map 'areas' to 'areas_inspecionadas' if needed
        if 'areas_inspecionadas' not in report_data and 'areas' in report_data:
             report_data['areas_inspecionadas'] = report_data['areas']
        
        # [FIX] Area Score Backfill: If saved stats has 0s, try to recover from AI Raw
        # Build map of raw areas for quick lookup
        raw_areas_map = {}
        if 'areas_inspecionadas' in ai_raw:
            for a in ai_raw['areas_inspecionadas']:
                # Normalize key by name
                k = a.get('nome_area') or a.get('name')
                if k: raw_areas_map[k] = a
        elif 'areas' in ai_raw:
            for a in ai_raw['areas']:
                k = a.get('name')
                if k: raw_areas_map[k] = a
                
        if 'areas_inspecionadas' in report_data:
            for area in report_data['areas_inspecionadas']:
                # Normalize Area Keys first
                if 'nome_area' not in area: area['nome_area'] = area.get('name', 'Área Desconhecida')
                
                # Backfill scores if missing/zero
                current_score = area.get('pontuacao_obtida') or area.get('score') or 0
                current_max = area.get('pontuacao_maxima') or area.get('max_score') or 0
                
                # Look for match in raw
                raw_match = raw_areas_map.get(area['nome_area'])
                if raw_match and (current_score == 0 and current_max == 0):
                    # Recover scores
                    area['pontuacao_obtida'] = raw_match.get('pontuacao_obtida') or raw_match.get('score', 0)
                    area['pontuacao_maxima'] = raw_match.get('pontuacao_maxima') or raw_match.get('max_score', 0)
                    area['aproveitamento'] = raw_match.get('aproveitamento') or raw_match.get('percentage', 0)

                # Ensure final keys exist
                if 'pontuacao_obtida' not in area: area['pontuacao_obtida'] = area.get('score', 0)
                if 'pontuacao_maxima' not in area: area['pontuacao_maxima'] = area.get('max_score', 0)
                if 'aproveitamento' not in area: area['aproveitamento'] = area.get('percentage', 0)


        # 3. [CRITICAL FIX] Always rebuild 'itens' from Database to reflect Edits
        # While preserving Area Scores from JSON
        if inspection.action_plan.items:
            # 3a. Create Lookup for Scores from Original JSON (to recover lost scores)
            # We map "Problem Description" -> Score
            score_map = {}
            if 'areas_inspecionadas' in report_data:
                for area in report_data['areas_inspecionadas']:
                    for item in area.get('itens', []):
                         # Normalize key: substring or full match
                         key = (item.get('observacao') or item.get('problema') or "").strip()[:50]
                         score_map[key] = item.get('pontuacao', 0)

            # 3b. Group DB Items by Sector
            rebuilt_areas = {}
            # Initialize with existing areas to keep scores/names
            if 'areas_inspecionadas' in report_data:
                for area in report_data['areas_inspecionadas']:
                    rebuilt_areas[area['nome_area']] = area
                    area['itens'] = [] # Clear JSON items, we will fill with DB items

            db_items = sorted(inspection.action_items, key=lambda i: i.created_at or i.id) # [FIX] Stable Sort
            # Note: action_items is a property returning list, so we sort it here.
            
            for item in db_items:
                area_name = item.nome_area or "Geral"
                
                # If area not in JSON (e.g. added later), create it
                if area_name not in rebuilt_areas:
                    rebuilt_areas[area_name] = {
                        'nome_area': area_name,
                        'items_nc': 0,
                        'pontuacao_obtida': 0,
                        'pontuacao_maxima': 0,
                        'aproveitamento': 0,
                        'itens': []
                    }
                
                # Recover Score
                # Try validation using problem_description
                key = (item.item_verificado or "").strip()[:50]
                recovered_score = score_map.get(key, 0)
                
                template_item = {
                    'id': str(item.id),
                    'item_verificado': item.item_verificado,
                    'status': 'Não Conforme', 
                    'observacao': item.problem_description,
                    'fundamento_legal': item.fundamento_legal,
                    'acao_corretiva_sugerida': item.acao_corretiva,
                    'prazo_sugerido': item.prazo_sugerido,
                    'pontuacao': recovered_score # Injected from JSON map
                }
                rebuilt_areas[area_name]['itens'].append(template_item)
            
            # 3c. Update report_data with rebuilt areas
            report_data['areas_inspecionadas'] = list(rebuilt_areas.values())

        # 3d. Recalculate basic stats just in case
        if 'areas_inspecionadas' in report_data:
            for area in report_data['areas_inspecionadas']:
                items = area.get('itens', [])
                # Re-count NCs based on what we actually have
                area['items_nc'] = len(items) 
        
        # 4. Bind basic info if missing
        if 'nome_estabelecimento' not in report_data:
             report_data['nome_estabelecimento'] = inspection.establishment.name if inspection.establishment else "Estabelecimento"
        if 'aproveitamento_geral' not in report_data:
             report_data['aproveitamento_geral'] = 0

        # 5. [NEW] Fetch Recipients for Sharing Widget
        recipients = []
        est = inspection.establishment
        
        if est:
             # A. Establishment Responsible (Main Contact)
             if est.responsible_name or est.responsible_email or est.responsible_phone:
                 recipients.append({
                     'name': est.responsible_name or "Responsável da Loja",
                     'email': est.responsible_email,
                     'phone': est.responsible_phone,
                     'role': 'Responsável'
                 })
                 
             # B. Company Managers (Restricted per User Request)
             # if est.company and est.company.users:
             #     for u in est.company.users:
             #         if u.role == UserRole.MANAGER:
             #             recipients.append({
             #                 'name': u.name or "Gestor",
             #                 'email': u.email,
             #                 'phone': u.whatsapp,
             #                 'role': 'Gestor'
             #             })
                         
             # C. Linked Consultants (Restricted per User Request)
             # if est.users:
             #     for u in est.users:
             #         if u.role == UserRole.CONSULTANT:
             #             recipients.append({
             #                 'name': u.name or "Consultor",
             #                 'email': u.email,
             #                 'phone': u.whatsapp,
             #                 'role': 'Consultor'
             #             })

        return render_template('manager_plan_edit.html', 
                             inspection=inspection, 
                             plan=inspection.action_plan,
                             report_data=report_data,
                             recipients=recipients)
        
    except Exception as e:
        flash(f'Erro ao carregar plano: {e}', 'error')
        return redirect(url_for('manager.dashboard_manager'))
    finally:
        db.close()

@manager_bp.route('/manager/plan/<file_id>/save', methods=['POST'])
@login_required
def save_plan(file_id):
    # [CHANGED] Allow Consultants to Edit Plan (Requested by User)
    if current_user.role not in [UserRole.MANAGER, UserRole.ADMIN, UserRole.CONSULTANT]:
        return jsonify({'error': 'Unauthorized'}), 403
        
    data = request.json
    if not data:
        return jsonify({'error': 'No data'}), 400
        
    db = next(get_db())
    try:
        inspection = db.query(Inspection).filter_by(drive_file_id=file_id).first()
        if not inspection or not inspection.action_plan:
             return jsonify({'error': 'Plan not found'}), 404
             
        # Rule: Forbidden if already approved
        if inspection.status == InspectionStatus.APPROVED:
            return jsonify({'error': 'Este plano já foi aprovado e não pode mais ser editado.'}), 403

        plan = inspection.action_plan
        
        # Save enriched fields
        if 'summary_text' in data:
            plan.summary_text = data.get('summary_text')
        if 'strengths_text' in data:
            plan.strengths_text = data.get('strengths_text')
        
        # Process Items
        items_payload = data.get('items', [])
        current_item_ids = [str(item.id) for item in plan.items]
        incoming_ids = [item.get('id') for item in items_payload if item.get('id')]
        
        # 1. Update/Create
        for item_data in items_payload:
            if item_data.get('id'):
                # Update
                item = db.query(ActionPlanItem).get(uuid.UUID(item_data['id']))
                if item and item.action_plan_id == plan.id:
                    if 'problem' in item_data: item.problem_description = item_data.get('problem')
                    if 'action' in item_data: item.corrective_action = item_data.get('action')
                    if 'legal_basis' in item_data: item.legal_basis = item_data.get('legal_basis')
                    
                    if 'severity' in item_data:
                        try:
                            item.severity = SeverityLevel(item_data.get('severity', 'MEDIUM'))
                        except ValueError:
                             item.severity = SeverityLevel.MEDIUM
                    
                    if 'deadline' in item_data and item_data.get('deadline'):
                        try:
                            # Try ISO first
                            item.deadline_date = datetime.strptime(item_data.get('deadline'), '%Y-%m-%d').date()
                        except:
                            try:
                                # Try BR format (dd/mm/yyyy)
                                item.deadline_date = datetime.strptime(item_data.get('deadline'), '%d/%m/%Y').date()
                            except:
                                pass

            else:
                # Create
                deadline = None
                if item_data.get('deadline'):
                     try:
                        deadline = datetime.strptime(item_data.get('deadline'), '%Y-%m-%d').date()
                     except:
                        try:
                             deadline = datetime.strptime(item_data.get('deadline'), '%d/%m/%Y').date()
                        except:
                             pass

                new_item = ActionPlanItem(
                    action_plan_id=plan.id,
                    problem_description=item_data.get('problem'),
                    corrective_action=item_data.get('action'),
                    legal_basis=item_data.get('legal_basis'),
                    severity=SeverityLevel(item_data.get('severity', 'MEDIUM')) if item_data.get('severity') in SeverityLevel._member_names_ else SeverityLevel.MEDIUM,
                    status=ActionPlanItemStatus.OPEN,
                    deadline_date=deadline
                )
                db.add(new_item)
        
        # 2. Delete missing - DISABLED for Partial Updates
        # The frontend sends single-item updates (AutoSave). 
        # Enabling this would delete all other items.
        # for existing_id in current_item_ids:
        #    if existing_id not in incoming_ids:
        #         item_to_del = db.query(ActionPlanItem).get(uuid.UUID(existing_id))
        #         db.delete(item_to_del)
                 
        # Capture Responsible Info if provided
        resp_name = data.get('responsible_name')
        resp_phone = data.get('responsible_phone')
        whatsapp_link = None
        
        if inspection.establishment and (resp_name or resp_phone):
            if resp_name: inspection.establishment.responsible_name = resp_name
            if resp_phone: inspection.establishment.responsible_phone = resp_phone
            
        # Update Inspection Status to APPROVED if requested
        if data.get('approve'):
            inspection.status = InspectionStatus.APPROVED
            plan.approved_by_id = current_user.id
            plan.approved_at = datetime.utcnow()
            
            # Generate WhatsApp Link
            if resp_phone:
                # Format phone (remove non-digits, ensure DDI)
                clean_phone = "".join(filter(str.isdigit, resp_phone))
                if len(clean_phone) <= 11: clean_phone = "55" + clean_phone # Assume BR if no DDI
                
                # Link Logic: Use download_revised_pdf specifically
                # Note: json_id is file_id in this context
                download_url = url_for('download_revised_pdf', file_id=file_id, _external=True)
                msg = f"Olá {resp_name or 'Responsável'}, seu Plano de Ação para {inspection.establishment.name} foi aprovado. Acesso: {download_url}"
                import urllib.parse
                whatsapp_link = f"https://wa.me/{clean_phone}?text={urllib.parse.quote(msg)}"
            
            flash('Plano aprovado com sucesso!', 'success')
            
        db.commit()
        return jsonify({'success': True, 'whatsapp_link': whatsapp_link})
        
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()

@manager_bp.route('/manager/plan/<file_id>/approve', methods=['POST'])
@login_required
def approve_plan(file_id):
    if current_user.role not in [UserRole.MANAGER, UserRole.ADMIN]:
        return jsonify({'error': 'Unauthorized'}), 403
        
    db = next(get_db())
    try:
        inspection = db.query(Inspection).filter_by(drive_file_id=file_id).first()
        if not inspection or not inspection.action_plan:
             return jsonify({'error': 'Plan not found'}), 404
             
        inspection.status = InspectionStatus.APPROVED
        if inspection.action_plan:
            inspection.action_plan.approved_by_id = current_user.id
            inspection.action_plan.approved_at = datetime.utcnow()
        
        db.commit()
        return jsonify({'success': True, 'message': 'Plano aprovado com sucesso!'}), 200
        
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@manager_bp.route('/api/status')
@login_required
def api_status():
    """
    Endpoint da API para sondagem (polling) do Dashboard do Gestor.
    Retorna:
    {
        'pending': [{'name': 'Empresa X'}],
        'processed_raw': [
            {'establishment': 'Empresa X', 'date': '...', 'status': '...', 'review_link': '...'}
        ]
    }
    """
    establishment_id = request.args.get('establishment_id')
    
    db = next(get_db())
    try:
        # 1. Fetch Processed/Visible Inspections
        query = db.query(Inspection).options(defer(Inspection.processing_logs), joinedload(Inspection.establishment))
        
        # Filter by Company (Security)
        est_ids = []
        if current_user.company_id:
             # Find establishments of this company
             company_ests = db.query(Establishment).filter(Establishment.company_id == current_user.company_id).all()
             est_ids = [e.id for e in company_ests]
             # Fix: Include orphans (establishment_id is Null) but owned by company (client_id)
             # Note: Inspection model might not have client_id populated reliably in this version.
             query = query.filter(
                 Inspection.establishment_id.in_(est_ids)
             )
        
        # Filter by Specific Establishment if selected
        if establishment_id:
             try:
                 query = query.filter(Inspection.establishment_id == uuid.UUID(establishment_id))
             except:
                 pass # Invalid ID ignore
             
        # Order by Recent
        all_inspections = query.order_by(Inspection.created_at.desc()).limit(100).all()
        
        pending_list = []
        processed_list = []
        
        # 2. Add pending items from Inspections (if they have establishment linked)
        for insp in all_inspections:
            est_name = insp.establishment.name if insp.establishment else "Desconhecido"
            
            if insp.status == InspectionStatus.PROCESSING:
                # We handle duplicates below or just add
                pass # Skip strict inspection pending, use Jobs for source of truth on pending
            else:
                # Format Date
                date_str = insp.created_at.strftime('%d/%m/%Y %H:%M') if insp.created_at else ''
                
                # Link
                link_id = insp.drive_file_id
                if link_id:
                    review_link = url_for('manager.edit_plan', file_id=link_id)
                else:
                    review_link = "#" # Safety fallback
                
                processed_list.append({
                    'establishment': est_name,
                    'date': date_str,
                    'status': insp.status.value,
                    'review_link': review_link
                })

        # 3. [FIX] Fetch Pending JOBS (Source of Truth for Processing)
        # This ensures we see uploads even if Establishment Match failed (NULL ID)
        if current_user.company_id:
            from src.models_db import Job, JobStatus
            jobs_query = db.query(Job).filter(
                Job.company_id == current_user.company_id,
                Job.status.in_([JobStatus.PENDING, JobStatus.PROCESSING])
            )
            # Filter by Est if selected (if job input has it) 
            # Note: Input payload might have establishment_id as string
            pending_jobs = jobs_query.order_by(Job.created_at.desc()).all()
            
            for job in pending_jobs:
                # Check if filtered by establishment
                if establishment_id:
                    payload_est = job.input_payload.get('establishment_id') if job.input_payload else None
                    if payload_est and payload_est != establishment_id:
                        continue
                
                fname = "Relatório em Processamento"
                if job.input_payload and 'filename' in job.input_payload:
                    fname = job.input_payload['filename']
                
                pending_list.append({'name': fname})
                
        return jsonify({
            'pending': pending_list,
            'processed_raw': processed_list
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()
