from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from src.database import get_db
from src.models_db import User, UserRole, Establishment, Inspection, ActionPlan, ActionPlanItem, ActionPlanItemStatus, SeverityLevel, InspectionStatus, Company
from flask import current_app, jsonify
from datetime import datetime
import json
from src.services.email_service import EmailService # Mock verify first
from werkzeug.security import generate_password_hash
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
        # Load necessary data for dropdowns and lists
        # Ensure company relation is loaded
        establishments = []
        # Reload current_user to ensure attached session if needed (optional)
        
        company = db.query(Company).get(current_user.company_id) if current_user.company_id else None
        if company:
            establishments = company.establishments
            
        consultants = db.query(User).filter(
            User.role == UserRole.CONSULTANT,
            User.company_id == current_user.company_id
        ).all()
        
        return render_template('dashboard_manager.html', 
                               user_role='MANAGER',
                               establishments=establishments,
                               consultants=consultants,
                               selected_est_id=establishment_id)
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
        flash('Preencha todos os campos e selecione ao menos um estabelecimento', 'error')
        return redirect(url_for('manager.dashboard_manager'))
        
    db = next(get_db())
    try:
        # Check permissions and existing assigned establishments
        establishments_to_assign = []
        for est_id in establishment_ids:
            try:
                est = db.query(Establishment).get(uuid.UUID(est_id))
                # Validate if Manager has access to this establishment (assuming logical ownership or global admin)
                # Na nova regra, Manager vê TUDO ou apenas a lista global?
                # Se "Company" existe, Manager só pode assignar ests da sua empresa?
                # O usuário disse "Company não tem relacionamento com ests", mas Manager tem?
                # Assumption: Manager has Global Access OR "Company" concept persists for Manager Scope.
                # Mantendo lógica anterior: Se est tem company_id, checa. Se é null (decoupled), permite se Manager for da mesma "Company" (???)
                # Simplificação: Manager pode associar qualquer estabelecimento listado no dashboard dele.
                if est:
                    establishments_to_assign.append(est)
            except:
                pass
        
        if not establishments_to_assign:
            flash('Nenhum estabelecimento válido selecionado.', 'error')
            return redirect(url_for('manager.dashboard_manager'))

        # Check user exists
        if db.query(User).filter_by(email=email).first():
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
        
        # Assign M2M
        user.establishments = establishments_to_assign
        
        db.add(user)
        db.commit()
        
        flash(f'Consultor criado com {len(establishments_to_assign)} estabelecimentos! Senha: {temp_pass}', 'success')
        
    except Exception as e:
        db.rollback()
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
             
        # Check ownership (Consultant must belong to Manager's company)
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
        return jsonify({'success': True, 'message': 'Consultor atualizado!'}), 200
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
        flash('Nome do estabelecimento é obrigatório.', 'error')
        return redirect(url_for('manager.dashboard_manager'))
        
    if not current_user.company_id:
        flash('Erro: Gestor não está vinculado a uma empresa.', 'error')
        return redirect(url_for('manager.dashboard_manager'))
        
    db = next(get_db())
    try:
        est = Establishment(
            name=name,
            code=code,
            company_id=current_user.company_id, # Link auto to manager's company
            drive_folder_id="" # Optional init
        )
        db.add(est)
        db.commit()
        flash(f'Estabelecimento {name} criado com sucesso!', 'success')
    except Exception as e:
        db.rollback()
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
        db.commit()
        
        return jsonify({'success': True, 'message': 'Estabelecimento atualizado!'}), 200
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
    if current_user.role not in [UserRole.MANAGER, UserRole.ADMIN]:
        flash('Acesso negado', 'error')
        return redirect(url_for('root'))
    
    db = next(get_db())
    try:
        # 1. Try to find Inspection in DB
        inspection = db.query(Inspection).filter_by(drive_file_id=file_id).first()
        
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
                
                # Create/Get Inspection if missing
                if not inspection:
                    # Link to Establishment if possible
                    est_name = data.get('estabelecimento')
                    est = db.query(Establishment).filter_by(name=est_name).first()
                    
                    inspection = Inspection(
                        drive_file_id=file_id,
                        status=InspectionStatus.PENDING_MANAGER_REVIEW,
                        client_id=None, # Legacy field, made nullable in V12
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

        # Blocking check: If approved, we might want to show a read-only view or just warn.
        # But for now, the template will handle the UI side, we just pass the info.
        
        return render_template('manager_plan_edit.html', inspection=inspection, plan=inspection.action_plan)
        
    except Exception as e:
        flash(f'Erro ao carregar plano: {e}', 'error')
        return redirect(url_for('manager.dashboard_manager'))
    finally:
        db.close()

@manager_bp.route('/manager/plan/<file_id>/save', methods=['POST'])
@login_required
def save_plan(file_id):
    if current_user.role not in [UserRole.MANAGER, UserRole.ADMIN]:
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
                    item.problem_description = item_data.get('problem')
                    item.corrective_action = item_data.get('action')
                    item.legal_basis = item_data.get('legal_basis')
                    try:
                        item.severity = SeverityLevel(item_data.get('severity', 'MEDIUM'))
                    except ValueError:
                         item.severity = SeverityLevel.MEDIUM
                    
                    if item_data.get('deadline'):
                        try:
                            item.deadline_date = datetime.strptime(item_data.get('deadline'), '%Y-%m-%d').date()
                        except:
                            pass
            else:
                # Create
                deadline = None
                if item_data.get('deadline'):
                     try:
                        deadline = datetime.strptime(item_data.get('deadline'), '%Y-%m-%d').date()
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
        
        # 2. Delete missing
        for existing_id in current_item_ids:
            if existing_id not in incoming_ids:
                 item_to_del = db.query(ActionPlanItem).get(uuid.UUID(existing_id))
                 db.delete(item_to_del)
                 
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
