from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from src.database import get_db
from src.models_db import User, UserRole, Establishment, Inspection, ActionPlan, ActionPlanItem, ActionPlanItemStatus, SeverityLevel, InspectionStatus, Company
from flask import current_app, jsonify
from datetime import datetime
from sqlalchemy.orm import joinedload, defer
from sqlalchemy.exc import IntegrityError
from src.services.email_service import EmailService # Mock verify first
from src.services.pdf_service import pdf_service
from src.services.drive_service import drive_service
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
        db.refresh(user) # Recarrega para garantir relacionamentos M2M
        
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
        drive_folder_created = False
        try:
             # Find Company Folder ID
             company = db.query(Company).get(current_user.company_id)
             if company and company.drive_folder_id:
                 from src.app import drive_service
                 if drive_service.service:
                     f_id, f_link = drive_service.create_folder(folder_name=name, parent_id=company.drive_folder_id)
                     if f_id:
                         est.drive_folder_id = f_id
                         drive_folder_created = True
             else:
                 current_app.logger.warning(f"⚠️ Company {company.name if company else 'N/A'} has no Drive Folder ID. Skipping Est folder.")
                 
        except Exception as drive_err:
             current_app.logger.error(f"Failed to create Drive folder for Establishment: {drive_err}")

        db.add(est)
        db.commit()
        
        msg = f'Estabelecimento {name} criado com sucesso!'
        if not drive_folder_created:
            msg += ' ⚠️ Pasta no Drive não pôde ser criada.'
        
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
             
        flash(msg, 'success' if drive_folder_created else 'warning')
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

        # Deletar pasta do Google Drive
        if est.drive_folder_id:
            drive_service.delete_folder(est.drive_folder_id)

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
                        status=ActionPlanItemStatus.OPEN,
                        order_index=i # [FIX] Save explicit order from JSON
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
             from src.app import to_brazil_time
             report_data['data_inspecao'] = report_data.get('inspection_date') or to_brazil_time(inspection.created_at).strftime('%d/%m/%Y')

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
                if 'nome_area' not in area: area['nome_area'] = area.get('name') or area.get('nome') or 'Área Desconhecida'
                
                # [FIX] Force high-precision data from AI Raw if available
                raw_match = raw_areas_map.get(area['nome_area'])
                if raw_match:
                    # Sync missing or zeroed values from raw JSON
                    for key in ['pontuacao_obtida', 'pontuacao_maxima', 'aproveitamento', 'pontuacao', 'max_score', 'score']:
                        if key in raw_match and (not area.get(key) or area.get(key) == 0):
                            area[key] = raw_match[key]
                
                # Backfill normalized keys for template
                if 'pontuacao_obtida' not in area: area['pontuacao_obtida'] = area.get('score') or area.get('pontuacao') or 0
                if 'pontuacao_maxima' not in area: area['pontuacao_maxima'] = area.get('max_score') or area.get('maximo') or 0
                if 'aproveitamento' not in area: 
                     if area['pontuacao_maxima'] > 0:
                         area['aproveitamento'] = (area['pontuacao_obtida'] / area['pontuacao_maxima']) * 100
                     else:
                         area['aproveitamento'] = 0

                # [NEW] Count NCs for this area (Required for Template Accordion)
                area['items_nc'] = sum(1 for item in area.get('itens', []) if 'conforme' in str(item.get('status', '')).lower() and 'não' in str(item.get('status', '')).lower() or 'parcial' in str(item.get('status', '')).lower())



                # Ensure final keys exist
                if 'pontuacao_obtida' not in area: area['pontuacao_obtida'] = area.get('score', 0)
                if 'pontuacao_maxima' not in area: area['pontuacao_maxima'] = area.get('max_score', 0)
                if 'aproveitamento' not in area: area['aproveitamento'] = area.get('percentage', 0)


        # 3. [CRITICAL FIX] Always rebuild 'itens' from Database to reflect Edits
        # While preserving Area Scores from JSON
        if inspection.action_plan.items:
            # 3a. Create Lookup for Scores from Original JSON (to recover lost scores)
            # We map "Problem Description" -> Score
            # [FIX] STRATEGY: Use (AreaName + Index) as primary key, fallback to Item Name
            score_map_by_index = {} # Key: (area_name, index) -> data
            score_map_by_text = {}  # Key: item_verificado_partial -> data
            
            if 'areas_inspecionadas' in report_data:
                for area in report_data['areas_inspecionadas']:
                    a_name = area.get('nome_area', 'Geral')
                    for idx, item in enumerate(area.get('itens', [])):
                         # [FIX] Garantir valor numérico seguro (evita NoneType > int)
                         score_v = item.get('pontuacao', 0)
                         if score_v is None: score_v = 0
                         
                         data_payload = {
                             'pontuacao': float(score_v),
                             'status': item.get('status'),
                             'item_verificado': item.get('item_verificado', ''),
                             'observacao': item.get('observacao', ''),
                         }
                         
                         # Mapa 1: Por Índice (Mais Robusto)
                         score_map_by_index[(a_name, idx)] = data_payload
                         
                         # Mapa 2: Por Texto (Fallback)
                         key = (item.get('item_verificado') or item.get('observacao') or "").strip()[:50]
                         score_map_by_text[key] = data_payload

            # 3b. Agrupar Itens do BD por Setor
            rebuilt_areas = {}
            # Inicializar com áreas existentes para manter notas/nomes
            # [FIX] Criar Mapa de Busca Normalizado (minusculo sem espaço -> objeto area)
            normalized_area_map = {}
            
            if 'areas_inspecionadas' in report_data:
                for area in report_data['areas_inspecionadas']:
                    key_name = area['nome_area']
                    rebuilt_areas[key_name] = area
                    area['itens'] = [] # Limpar itens JSON, encheremos com itens BD
                    
                    # Normalizar chave para busca
                    norm_key = key_name.strip().lower()
                    normalized_area_map[norm_key] = area

            # [FIX] Ordenação Estável por Índice de Ordem (se presente) então UUID
            db_items = sorted(
                inspection.action_items, 
                key=lambda i: (i.order_index if i.order_index is not None else float('inf'), str(i.id))
            )
            # Nota: action_items é uma propriedade retornando lista, então ordenamos aqui.
            
            for item in db_items:
                raw_area_name = item.nome_area or "Geral"
                norm_area_name = raw_area_name.strip().lower()
                
                # Tentar encontrar área existente via Mapa Normalizado
                target_area = normalized_area_map.get(norm_area_name)
                
                if target_area:
                    # Encontrou correspondência! Usar nome oficial do JSON
                    area_name = target_area['nome_area'] 
                else:
                    # Nenhuma correspondência, usar nome cru (criará nova área)
                    area_name = raw_area_name
                
                # Se área não estiver no JSON (ex: adicionada depois), criar
                if area_name not in rebuilt_areas:
                    rebuilt_areas[area_name] = {
                        'nome_area': area_name,
                        'items_nc': 0,
                        'pontuacao_obtida': 0,
                        'pontuacao_maxima': 0,
                        'aproveitamento': 0,
                        'itens': []
                    }
                
                # Recover Score and Status from JSON
                # [FIX] Robust Recovery Strategy
                raw_data = {}
                
                # Strategy 1: Match by Order Index (Perfect Match)
                if item.order_index is not None:
                     raw_data = score_map_by_index.get((area_name, item.order_index), {})
                
                # Strategy 2: Match by Extracted Name (Fallback for Legacy Data)
                if not raw_data:
                     # DB 'problem_description' is "Item Verified: Observation"
                     # We try to extract just the "Item Verified" part
                     full_desc = item.problem_description or ""
                     candidate_name = full_desc.split(":", 1)[0].strip() if ":" in full_desc else full_desc
                     key_text = candidate_name[:50]
                     raw_data = score_map_by_text.get(key_text, {})

                recovered_score = raw_data.get('pontuacao', 0)
                recovered_status = raw_data.get('status') # e.g. 'PARTIAL'
                recovered_item_verificado = raw_data.get('item_verificado', '')
                recovered_observacao = raw_data.get('observacao', '')
                
                # [FILTER] User Request: Only show NC or Partial items in the Action Plan View.
                # If item is marked as COMPLIANT/RESOLVED or has max score, skip adding to the list.
                # Note: Areas will still show up because we initialized them from the JSON structure above.
                
                # Check 1: Status String
                is_compliant_status = False
                status_check = (recovered_status or item.original_status or "").upper()
                if 'CONFORME' in status_check and 'NÃO' not in status_check and 'PARCIAL' not in status_check:
                    is_compliant_status = True
                if status_check == 'COMPLIANT' or status_check == 'RESOLVED':
                    is_compliant_status = True
                    
                # Check 2: Database Status Enum
                if item.status == ActionPlanItemStatus.RESOLVED and not item.manager_notes: 
                     # If RESOLVED but has manager notes, maybe it was fixed manually? 
                     # But standard "compliant" items come as RESOLVED without notes usually.
                     # Let's trust the status check mostly.
                     pass

                # Check 3: Perfect Score (Safety Net)
                # If score is max_score (e.g. 10/10), it's compliant.
                # We need item max score here. processor.py defaults to 10.
                is_perfect_score = False
                if item.original_score is not None and item.original_score >= 10: # Assuming 10 is max default
                     is_perfect_score = True
                
                # Apply Filter
                if is_compliant_status or is_perfect_score:
                    continue  # Skip this item in the EDIT view
                
                # [ML-READY] Prioridade de exibição: deadline_text > deadline_date > ai_suggested_deadline
                deadline_display = item.ai_suggested_deadline or "N/A"  # Fallback: Sugestão original da IA
                
                if item.deadline_date:
                    # Se tem data estruturada, formatar
                    try:
                        deadline_display = item.deadline_date.strftime('%d/%m/%Y')
                    except:
                        pass
                
                if item.deadline_text:
                    # Se gestor editou texto manualmente, priorizar essa versão
                    deadline_display = item.deadline_text
                
                template_item = {
                    'id': str(item.id),
                    'item_verificado': recovered_item_verificado or item.problem_description,
                    # [VITAL FIX] Use Recovered Status from JSON if available (e.g. 'PARTIAL')
                    # This allows enrich_data to correctly translate and score it.
                    'status': recovered_status or item.original_status or 'Não Conforme',
                    'observacao': recovered_observacao or item.problem_description,
                    'fundamento_legal': item.fundamento_legal,
                    'acao_corretiva_sugerida': item.corrective_action,
                    'prazo_sugerido': deadline_display, # Now reflects saved data
                    # [FIX] Score Priority: If original_score is 0 (suspicious) but we recovered a score, use recovered.
                    'pontuacao': item.original_score if (item.original_score is not None and item.original_score > 0) else (recovered_score if recovered_score > 0 else (item.original_score or 0)) 
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

        # 4b. Calculate general summary
        # Fallback: use area sums if top-level scores are missing
        if 'areas_inspecionadas' in report_data and report_data['areas_inspecionadas']:
            total_obtido = sum(float(area.get('pontuacao_obtida', 0) or 0) for area in report_data['areas_inspecionadas'])
            total_maximo = sum(float(area.get('pontuacao_maxima', 0) or 0) for area in report_data['areas_inspecionadas'])

            if 'pontuacao_geral' not in report_data or report_data.get('pontuacao_geral') == 0:
                report_data['pontuacao_geral'] = round(total_obtido, 2)

            if 'pontuacao_maxima_geral' not in report_data or report_data.get('pontuacao_maxima_geral') == 0:
                report_data['pontuacao_maxima_geral'] = round(total_maximo, 2)

        # ALWAYS recalculate percentage from top-level scores (never trust AI's aproveitamento)
        pg = float(report_data.get('pontuacao_geral', 0) or 0)
        pmg = float(report_data.get('pontuacao_maxima_geral', 0) or 0)
        if pmg > 0:
            report_data['aproveitamento_geral'] = round((pg / pmg * 100), 2)
        else:
            report_data['aproveitamento_geral'] = 0

        # [HOTFIX] Enrich Data via PDFService (Calculates Scores, Normalizes Status)
        try:
             pdf_service.enrich_data(report_data)
        except Exception as e:
             print(f"Enrichment Failed: {e}")

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

        # Compute status flags in Python (avoids Jinja2 Enum resolution issues)
        from src.models_db import InspectionStatus
        current_status = inspection.status
        status_value = current_status.value if hasattr(current_status, 'value') else str(current_status)
        is_locked = status_value in ['APPROVED', 'COMPLETED', 'PENDING_CONSULTANT_VERIFICATION']
        is_approved = status_value in ['APPROVED', 'PENDING_CONSULTANT_VERIFICATION', 'COMPLETED']

        return render_template('manager_plan_edit.html',
                             inspection=inspection,
                             plan=inspection.action_plan,
                             report_data=report_data,
                             recipients=recipients,
                             is_locked=is_locked,
                             is_approved=is_approved)
        
    except Exception as e:
        flash(f'Erro ao carregar plano: {e}', 'error')
        return redirect(url_for('manager.dashboard_manager'))
    finally:
        db.close()

def _prepare_pdf_data(inspection):
    """
    Helper to prepare data for PDF generation, merging AI raw data with DB edits.
    """
    if not inspection or not inspection.action_plan:
        return {}
        
    # 1. Base Data from AI Raw
    ai_raw = inspection.ai_raw_response or {}
    plan = inspection.action_plan
    
    merged_stats = ai_raw.copy()
    if plan.stats_json:
        merged_stats.update(plan.stats_json)
    
    data = merged_stats
    
    # 2. Rebuild Items from DB
    if plan.items:
        db_items = sorted(
            plan.items,
            key=lambda i: (i.order_index if i.order_index is not None else float('inf'), str(i.id))
        )

        # Build lookup to recover original item_verificado/observacao from AI JSON
        ai_item_map = {}  # (area_name, index) -> {item_verificado, observacao}
        if 'areas_inspecionadas' in data:
            for area in data['areas_inspecionadas']:
                a_name = area.get('nome_area', 'Geral')
                for idx, ai_item in enumerate(area.get('itens', [])):
                    ai_item_map[(a_name, idx)] = {
                        'item_verificado': ai_item.get('item_verificado', ''),
                        'observacao': ai_item.get('observacao', ''),
                    }

        rebuilt_areas = {}
        normalized_area_map = {}

        if 'areas_inspecionadas' in data:
            for area in data['areas_inspecionadas']:
                key = area.get('nome_area') or area.get('name')
                if key:
                    rebuilt_areas[key] = area
                    area['itens'] = []
                    normalized_area_map[key.strip().lower()] = area

        for item in db_items:
            raw_area_name = item.nome_area or item.sector or "Geral"
            norm_area_name = raw_area_name.strip().lower()
            
            target_area = normalized_area_map.get(norm_area_name)
            if target_area:
                area_name = target_area['nome_area']
            else:
                area_name = raw_area_name
            
            if area_name not in rebuilt_areas:
                rebuilt_areas[area_name] = {
                    'nome_area': area_name,
                    'itens': [], 'pontuacao_obtida': 0, 'pontuacao_maxima': 0, 'aproveitamento': 0
                }
            
            deadline_display = item.ai_suggested_deadline
            if item.deadline_text and item.deadline_text.strip():
                deadline_display = item.deadline_text
            elif item.deadline_date:
                try: deadline_display = item.deadline_date.strftime('%d/%m/%Y')
                except: pass
            
            score_val = item.original_score if item.original_score is not None else 0
            status_val = item.original_status or "Não Conforme"

            # Normalizar status para labels padrão em português
            status_lower = status_val.lower()
            if 'parcial' in status_lower:
                status_val = 'Parcialmente Conforme'
            elif 'não' in status_lower or 'nao' in status_lower:
                status_val = 'Não Conforme'
            elif 'conforme' in status_lower:
                status_val = 'Conforme'

            current_status = item.current_status or ("Pendente" if item.status == ActionPlanItemStatus.OPEN else "Pendente")

            # Determinar se item foi corrigido (apenas pelo consultor, não por ser originalmente conforme)
            is_corrected = (current_status == "Corrigido")

            # Recuperar item_verificado/observacao originais do JSON da IA
            ai_data = ai_item_map.get((area_name, item.order_index), {}) if item.order_index is not None else {}
            recovered_item_name = ai_data.get('item_verificado', '')
            recovered_obs = ai_data.get('observacao', '')

            rebuilt_areas[area_name]['itens'].append({
                'item_verificado': recovered_item_name or item.problem_description,
                'status': status_val, # AI Original
                'status_atual': current_status, # Current Workflow State
                'observacao': recovered_obs or item.problem_description,
                'fundamento_legal': item.legal_basis,
                'acao_corretiva_sugerida': item.corrective_action,
                'prazo_sugerido': deadline_display,
                'pontuacao': float(score_val),
                'manager_notes': item.manager_notes,
                # [NEW] Consultant verification fields for PDF
                'evidence_image_url': item.evidence_image_url,
                'correction_notes': item.correction_notes,
                'is_corrected': is_corrected,
                'original_status_label': status_val,
                'old_score_display': str(score_val) if score_val else None
            })

        # Recalculate NC Counts (inclui Não Conforme e Parcialmente Conforme)
        for area in rebuilt_areas.values():
            area['items_nc'] = sum(1 for i in area.get('itens', []) if i.get('status') != 'Conforme')

        data['areas_inspecionadas'] = list(rebuilt_areas.values())

    # Map Status for Template
    status_val = inspection.status.value if hasattr(inspection.status, 'value') else str(inspection.status)
    if status_val == 'COMPLETED':
        data['status_plano'] = 'CONCLUÍDO'
    elif status_val == 'APPROVED' or status_val == 'PENDING_CONSULTANT_VERIFICATION':
        data['status_plano'] = 'AGUARDANDO VISITA'
    else:
        data['status_plano'] = 'EM APROVAÇÃO'
        
    return data

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
                        deadline_input = item_data.get('deadline')
                        
                        # [ML-READY] Salvar versão textual se diferente da sugestão da IA
                        if deadline_input != item.ai_suggested_deadline:
                            item.deadline_text = deadline_input
                        
                    if 'current_status' in item_data:
                        item.current_status = item_data.get('current_status')
                        
                        # Tentar converter para Date estruturado
                        try:
                            # Try ISO first (YYYY-MM-DD)
                            item.deadline_date = datetime.strptime(deadline_input, '%Y-%m-%d').date()
                        except:
                            try:
                                # Try BR format (dd/mm/yyyy)
                                item.deadline_date = datetime.strptime(deadline_input, '%d/%m/%Y').date()
                            except:
                                # Não é data válida, mantém apenas texto em deadline_text
                                pass

            else:
                # Create
                deadline_date = None
                deadline_text = None
                
                if item_data.get('deadline'):
                    deadline_input = item_data.get('deadline')
                    deadline_text = deadline_input  # Salvar texto original
                    
                    # Tentar converter para Date
                    try:
                        deadline_date = datetime.strptime(deadline_input, '%Y-%m-%d').date()
                    except ValueError:
                        try:
                            deadline_date = datetime.strptime(deadline_input, '%d/%m/%Y').date()
                        except ValueError:
                            # Não é data válida, só mantém texto
                            pass

                new_item = ActionPlanItem(
                    action_plan_id=plan.id,
                    problem_description=item_data.get('problem'),
                    corrective_action=item_data.get('action'),
                    legal_basis=item_data.get('legal_basis'),
                    severity=SeverityLevel(item_data.get('severity', 'MEDIUM')) if item_data.get('severity') in SeverityLevel._member_names_ else SeverityLevel.MEDIUM,
                    status=ActionPlanItemStatus.OPEN,
                    deadline_date=deadline_date,
                    deadline_text=deadline_text,  # [ML-READY] Salvar texto original
                    order_index=len(plan.items), # [FIX] Append at end
                    current_status="Pendente" # Default new
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
            # [V17 Flow] Change from APPROVED to PENDING_CONSULTANT_VERIFICATION
            inspection.status = InspectionStatus.PENDING_CONSULTANT_VERIFICATION
            plan.approved_by_id = current_user.id
            plan.approved_at = datetime.utcnow()
            
            # Generate and Cache PDF
            try:
                from src.services.pdf_service import pdf_service
                from src.services.storage_service import storage_service
                import io
                
                pdf_data = _prepare_pdf_data(inspection)
                pdf_bytes = pdf_service.generate_pdf_bytes(pdf_data)
                
                # Upload to 'approved_pdfs' folder (or similar)
                filename = f"Plano_Aprovado_{inspection.id}.pdf"
                pdf_url = storage_service.upload_file(
                    io.BytesIO(pdf_bytes), 
                    destination_folder="approved_pdfs", 
                    filename=filename
                )
                plan.final_pdf_url = pdf_url
                flash("PDF Final Gerado e Salvo!", "success")
                
            except Exception as pdf_err:
                print(f"Failed to generate/cache PDF: {pdf_err}")
                # Don't block approval but warn
                
            
            # Generate WhatsApp Link
            if resp_phone:
                # Format phone (remove non-digits, ensure DDI)
                clean_phone = "".join(filter(str.isdigit, resp_phone))
                if len(clean_phone) <= 11: clean_phone = "55" + clean_phone # Assume BR if no DDI
                
                # Link Logic: Use final_pdf_url if available, else download_revised_pdf
                if plan.final_pdf_url:
                     download_url = plan.final_pdf_url
                else:
                     download_url = url_for('download_revised_pdf', file_id=file_id, _external=True)
                     
                msg = f"Olá {resp_name or 'Responsável'}, seu Plano de Ação para {inspection.establishment.name} foi aprovado. Acesso: {download_url}"
                import urllib.parse
                whatsapp_link = f"https://wa.me/{clean_phone}?text={urllib.parse.quote(msg)}"
            
            flash('Plano aprovado e enviado para verificação do consultor!', 'success')
            
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

        # [V17 Flow] Change status to PENDING_CONSULTANT_VERIFICATION (not APPROVED)
        inspection.status = InspectionStatus.PENDING_CONSULTANT_VERIFICATION
        plan = inspection.action_plan
        plan.approved_by_id = current_user.id
        plan.approved_at = datetime.utcnow()

        # Generate and cache PDF for sharing
        try:
            from src.services.pdf_service import pdf_service
            from src.services.storage_service import storage_service
            import io

            pdf_data = _prepare_pdf_data(inspection)
            pdf_bytes = pdf_service.generate_pdf_bytes(pdf_data)

            filename = f"Plano_Aprovado_{inspection.id}.pdf"
            pdf_url = storage_service.upload_file(
                io.BytesIO(pdf_bytes),
                destination_folder="approved_pdfs",
                filename=filename
            )
            plan.final_pdf_url = pdf_url
        except Exception as pdf_err:
            print(f"Failed to generate/cache PDF: {pdf_err}")
            # Don't block approval

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
                from src.app import to_brazil_time
                date_str = to_brazil_time(insp.created_at).strftime('%d/%m/%Y %H:%M') if insp.created_at else ''
                
                # Link
                link_id = insp.drive_file_id
                if link_id:
                    review_link = url_for('manager.edit_plan', file_id=link_id)
                else:
                    review_link = "#" # Safety fallback
                
                processed_list.append({
                    'id': str(insp.id),  # <-- ADICIONADO: ID para o tracker
                    'establishment': est_name,
                    'date': date_str,
                    'status': insp.status.value if insp.status else 'PENDING',  # <-- FIX: fallback se status for None
                    'review_link': review_link
                })

        # 3. [FIX] Fetch Pending JOBS (Source of Truth for Processing)
        # This ensures we see uploads even if Establishment Match failed (NULL ID)
        if current_user.company_id:
            from src.models_db import Job, JobStatus
            jobs_query = db.query(Job).filter(
                Job.company_id == current_user.company_id,
                Job.status.in_([JobStatus.PENDING, JobStatus.PROCESSING, JobStatus.FAILED])
            )
            # Filter by Est if selected (if job input has it) 
            # Note: Input payload might have establishment_id as string
            pending_jobs = jobs_query.order_by(Job.created_at.desc()).limit(10).all()
            
            for job in pending_jobs:
                # Check if filtered by establishment
                if establishment_id:
                    payload_est = job.input_payload.get('establishment_id') if job.input_payload else None
                    if payload_est and payload_est != establishment_id:
                        continue
                
                fname = "Relatório em Processamento"
                if job.input_payload and 'filename' in job.input_payload:
                    fname = job.input_payload['filename']
                
                # Check if Failed
                is_error = job.status == JobStatus.FAILED
                err_msg = job.error_log if is_error else None

                pending_list.append({
                    'name': fname,
                    'status': job.status.value,
                    'error': is_error,
                    'message': err_msg
                })
                
        return jsonify({
            'pending': pending_list,
            'processed_raw': processed_list
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()
