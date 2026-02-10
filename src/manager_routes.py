from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, session, current_app, jsonify,
)
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash

from src.models_db import (
    User, UserRole, Establishment, Inspection, ActionPlan, ActionPlanItem,
    ActionPlanItemStatus, SeverityLevel, InspectionStatus, JobStatus,
)
from src.container import (
    get_uow, get_plan_service, get_inspection_data_service, get_tracker_service,
)

import uuid
import random
import string
import logging

logger = logging.getLogger(__name__)

manager_bp = Blueprint('manager', __name__)


def generate_temp_password(length=8):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@manager_bp.route('/dashboard/manager')
@login_required
def dashboard_manager():
    if current_user.role != UserRole.MANAGER:
        flash('Acesso negado', 'error')
        return redirect(url_for('root'))

    establishment_id = request.args.get('establishment_id')
    uow = get_uow()

    company = uow.companies.get_by_id(current_user.company_id) if current_user.company_id else None
    all_establishments = sorted(company.establishments, key=lambda x: x.name) if company else []
    establishments = all_establishments

    consultants = uow.users.get_consultants_for_company(current_user.company_id)

    # Session filter persistence
    if establishment_id is not None:
        if establishment_id:
            session['selected_est_id'] = establishment_id
        else:
            session.pop('selected_est_id', None)
            establishment_id = None
    elif 'selected_est_id' in session:
        establishment_id = session['selected_est_id']

    # Apply establishment filter
    if establishment_id:
        target = next((e for e in all_establishments if str(e.id) == establishment_id), None)
        if target:
            establishments = [target]
            consultants = [c for c in consultants if target in c.establishments]

    return render_template(
        'dashboard_manager_v2.html',
        user_role='MANAGER',
        company=company,
        establishments=establishments,
        all_establishments=all_establishments,
        consultants=consultants,
        selected_est_id=establishment_id,
    )


# ---------------------------------------------------------------------------
# Tracker
# ---------------------------------------------------------------------------

@manager_bp.route('/api/tracker/<uuid:inspection_id>')
@login_required
def tracker_details(inspection_id):
    if current_user.role != UserRole.MANAGER:
        return jsonify({'error': 'Unauthorized'}), 403

    uow = get_uow()
    insp = uow.inspections.get_by_id(inspection_id)
    if not insp:
        return jsonify({'error': 'Not found'}), 404

    # Security: must belong to manager's company
    if not insp.establishment or insp.establishment.company_id != current_user.company_id:
        return jsonify({'error': 'Unauthorized access to this inspection'}), 403

    tracker_svc = get_tracker_service()
    return jsonify(tracker_svc.get_tracker_data(insp))


# ---------------------------------------------------------------------------
# Consultant CRUD
# ---------------------------------------------------------------------------

@manager_bp.route('/manager/consultant/new', methods=['POST'])
@login_required
def create_consultant():
    if current_user.role != UserRole.MANAGER:
        flash('Acesso negado', 'error')
        return redirect(url_for('root'))

    name = request.form.get('name')
    email = request.form.get('email')
    establishment_ids = request.form.getlist('establishment_ids')

    if not name or not email or not establishment_ids:
        msg = 'Preencha todos os campos e selecione lojas.'
        if request.accept_mimetypes.accept_json:
            return jsonify({'error': msg}), 400
        flash(msg, 'error')
        return redirect(url_for('manager.dashboard_manager'))

    uow = get_uow()
    try:
        # Validate establishments
        establishments_to_assign = []
        for est_id in establishment_ids:
            try:
                est = uow.establishments.get_by_id(uuid.UUID(est_id))
                if est:
                    establishments_to_assign.append(est)
            except Exception:
                pass

        if not establishments_to_assign:
            msg = 'Nenhuma loja válida selecionada.'
            if request.accept_mimetypes.accept_json:
                return jsonify({'error': msg}), 400
            flash(msg, 'error')
            return redirect(url_for('manager.dashboard_manager'))

        if uow.users.get_by_email(email):
            msg = 'Email já cadastrado.'
            if request.accept_mimetypes.accept_json:
                return jsonify({'error': msg}), 400
            flash(msg, 'error')
            return redirect(url_for('manager.dashboard_manager'))

        temp_pass = generate_temp_password()
        user = User(
            id=uuid.uuid4(),
            name=name,
            email=email,
            password_hash=generate_password_hash(temp_pass),
            role=UserRole.CONSULTANT,
            company_id=current_user.company_id,
            must_change_password=True,
        )
        user.establishments = establishments_to_assign
        uow.users.add(user)

        # Capture data before commit (SQLAlchemy expires attributes after commit)
        user_data = {
            'id': str(user.id),
            'name': user.name,
            'email': user.email,
            'establishment_ids': [str(e.id) for e in establishments_to_assign],
            'establishments': [{'id': str(e.id), 'name': e.name} for e in establishments_to_assign],
        }
        num_establishments = len(establishments_to_assign)

        uow.commit()

        # Send welcome email
        try:
            current_app.email_service.send_welcome_email(email, name, temp_pass)
        except Exception as e:
            logger.warning(f"Failed to send welcome email to {email}: {e}")

        msg = f'Consultor criado com {num_establishments} estabelecimentos! Senha: {temp_pass}'
        if request.accept_mimetypes.accept_json:
            return jsonify({
                'success': True,
                'message': msg,
                'consultant': user_data,
            }), 201

        flash(msg, 'success')

    except Exception as e:
        uow.rollback()
        if request.accept_mimetypes.accept_json:
            return jsonify({'error': str(e)}), 500
        flash(f'Erro: {e}', 'error')

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

    uow = get_uow()
    try:
        user = uow.users.get_by_id(user_id)
        if not user or user.role != UserRole.CONSULTANT:
            return jsonify({'error': 'Consultor não encontrado.'}), 404
        if user.company_id != current_user.company_id:
            return jsonify({'error': 'Acesso negado a este consultor.'}), 403

        user.name = name
        user.email = email

        if password and len(password.strip()) > 0:
            user.password_hash = generate_password_hash(password)

        if establishment_ids:
            new_establishments = []
            for est_id in establishment_ids:
                est = uow.establishments.get_by_id(uuid.UUID(est_id))
                if est and est.company_id == current_user.company_id:
                    new_establishments.append(est)
            user.establishments = new_establishments

        # Capture data before commit (SQLAlchemy expires attributes after commit)
        user_data = {
            'id': str(user.id),
            'name': user.name,
            'email': user.email,
            'establishment_ids': [str(e.id) for e in user.establishments],
        }

        uow.commit()

        return jsonify({
            'success': True,
            'message': 'Consultor atualizado!',
            'consultant': user_data,
        }), 200

    except Exception as e:
        uow.rollback()
        return jsonify({'error': str(e)}), 500


@manager_bp.route('/manager/consultant/<uuid:user_id>/delete', methods=['POST'])
@login_required
def delete_consultant(user_id):
    if current_user.role != UserRole.MANAGER:
        return jsonify({'error': 'Acesso negado'}), 403

    uow = get_uow()
    try:
        user = uow.users.get_by_id(user_id)
        if not user or user.role != UserRole.CONSULTANT:
            return jsonify({'error': 'Consultor não encontrado'}), 404
        if user.company_id != current_user.company_id:
            return jsonify({'error': 'Acesso negado'}), 403

        uow.users.delete(user)
        uow.commit()
        return jsonify({'success': True, 'message': 'Consultor removido!'}), 200

    except Exception as e:
        uow.rollback()
        return jsonify({'error': str(e)}), 500


# ---------------------------------------------------------------------------
# Establishment CRUD
# ---------------------------------------------------------------------------

@manager_bp.route('/manager/establishment/new', methods=['POST'])
@login_required
def create_establishment():
    if current_user.role != UserRole.MANAGER:
        flash('Acesso negado', 'error')
        return redirect(url_for('root'))

    name = request.form.get('name')
    code = request.form.get('code')

    if not name:
        msg = 'Nome do estabelecimento é obrigatório.'
        if request.accept_mimetypes.accept_json:
            return jsonify({'error': msg}), 400
        flash(msg, 'error')
        return redirect(url_for('manager.dashboard_manager'))

    if not current_user.company_id:
        msg = 'Gestor sem empresa vinculada.'
        if request.accept_mimetypes.accept_json:
            return jsonify({'error': msg}), 400
        flash(f'Erro: {msg}', 'error')
        return redirect(url_for('manager.dashboard_manager'))

    uow = get_uow()
    try:
        est = Establishment(
            id=uuid.uuid4(),
            name=name,
            code=code,
            company_id=current_user.company_id,
            drive_folder_id="",
            responsible_name=request.form.get('responsible_name'),
            responsible_email=request.form.get('responsible_email'),
            responsible_phone=request.form.get('responsible_phone'),
        )

        # Try creating Drive folder
        drive_folder_created = False
        try:
            company = uow.companies.get_by_id(current_user.company_id)
            if company and company.drive_folder_id:
                drive_svc = getattr(current_app, 'drive_service', None)
                if drive_svc and drive_svc.service:
                    f_id, f_link = drive_svc.create_folder(
                        folder_name=name, parent_id=company.drive_folder_id,
                    )
                    if f_id:
                        est.drive_folder_id = f_id
                        drive_folder_created = True
        except Exception as drive_err:
            current_app.logger.error(f"Failed to create Drive folder: {drive_err}")

        uow.establishments.add(est)

        # Capture data before commit (SQLAlchemy expires attributes after commit)
        est_data = {
            'id': str(est.id),
            'name': est.name,
            'code': est.code,
            'company_id': str(est.company_id) if est.company_id else None,
            'responsible_name': est.responsible_name,
            'responsible_email': est.responsible_email,
            'responsible_phone': est.responsible_phone,
        }
        # Get company name before commit
        company_obj = uow.companies.get_by_id(est.company_id) if est.company_id else None
        est_data['company_name'] = company_obj.name if company_obj else None

        uow.commit()

        msg = f'Estabelecimento {name} criado com sucesso!'
        if not drive_folder_created:
            msg += ' Pasta no Drive nao pôde ser criada.'

        if request.accept_mimetypes.accept_json:
            return jsonify({
                'success': True,
                'message': msg,
                'establishment': est_data,
            }), 201

        flash(msg, 'success' if drive_folder_created else 'warning')

    except Exception as e:
        uow.rollback()
        if request.accept_mimetypes.accept_json:
            return jsonify({'error': str(e)}), 500
        flash(f'Erro ao criar estabelecimento: {e}', 'error')

    return redirect(url_for('manager.dashboard_manager'))


@manager_bp.route('/manager/establishment/<uuid:est_id>/update', methods=['POST'])
@login_required
def update_establishment(est_id):
    if current_user.role != UserRole.MANAGER:
        return jsonify({'error': 'Acesso negado'}), 403

    name = request.form.get('name')
    if not name:
        return jsonify({'error': 'Nome é obrigatório.'}), 400

    uow = get_uow()
    try:
        est = uow.establishments.get_by_id(est_id)
        if not est:
            return jsonify({'error': 'Estabelecimento não encontrado.'}), 404
        if est.company_id != current_user.company_id:
            return jsonify({'error': 'Acesso negado a este estabelecimento.'}), 403

        est.name = name
        est.code = request.form.get('code')
        est.responsible_name = request.form.get('responsible_name')
        est.responsible_email = request.form.get('responsible_email')
        est.responsible_phone = request.form.get('responsible_phone')

        # Capture data before commit (SQLAlchemy expires attributes after commit)
        est_data = {
            'id': str(est.id),
            'name': est.name,
            'code': est.code,
            'responsible_name': est.responsible_name,
            'responsible_email': est.responsible_email,
            'responsible_phone': est.responsible_phone,
        }
        uow.commit()

        return jsonify({
            'success': True,
            'message': 'Estabelecimento atualizado!',
            'establishment': est_data,
        }), 200

    except Exception as e:
        uow.rollback()
        return jsonify({'error': str(e)}), 500


@manager_bp.route('/manager/establishment/<uuid:est_id>/delete', methods=['POST'])
@login_required
def delete_establishment(est_id):
    if current_user.role != UserRole.MANAGER:
        return jsonify({'error': 'Acesso negado'}), 403

    uow = get_uow()
    try:
        est = uow.establishments.get_by_id(est_id)
        if not est:
            return jsonify({'error': 'Estabelecimento não encontrado'}), 404
        if est.company_id != current_user.company_id:
            return jsonify({'error': 'Acesso negado'}), 403

        # Delete Drive folder if it exists
        if est.drive_folder_id:
            try:
                drive_svc = getattr(current_app, 'drive_service', None)
                if drive_svc:
                    drive_svc.delete_folder(est.drive_folder_id)
            except Exception:
                pass

        uow.establishments.delete(est)
        uow.commit()
        return jsonify({'success': True, 'message': 'Estabelecimento removido!'}), 200

    except Exception as e:
        uow.rollback()
        return jsonify({'error': str(e)}), 500


# ---------------------------------------------------------------------------
# Plan View / Edit  (THE BIG REFACTORING WIN)
# ---------------------------------------------------------------------------

@manager_bp.route('/manager/plan/<file_id>', methods=['GET'])
@login_required
def edit_plan(file_id):
    if current_user.role not in [UserRole.MANAGER, UserRole.ADMIN, UserRole.CONSULTANT]:
        flash('Acesso não autorizado.', 'error')
        return redirect(url_for('manager.dashboard_manager'))

    try:
        data_svc = get_inspection_data_service()
        result = data_svc.get_plan_edit_data(file_id)

        # Legacy migration: import from Drive if not in DB
        if not result:
            result = _try_migrate_from_drive(file_id)
            if not result:
                flash('Plano não encontrado.', 'error')
                return redirect(url_for('manager.dashboard_manager'))

        inspection = result['inspection']
        plan = result['plan']
        report_data = result['data']

        # Apply summary overrides
        if plan and plan.summary_text:
            report_data['resumo_geral'] = plan.summary_text
        elif not report_data.get('resumo_geral'):
            ai_raw = inspection.ai_raw_response or {}
            report_data['resumo_geral'] = (
                ai_raw.get('summary') or ai_raw.get('summary_text') or 'Resumo não disponível.'
            )

        # Normalize template-expected keys
        if 'nome_estabelecimento' not in report_data:
            report_data['nome_estabelecimento'] = (
                inspection.establishment.name if inspection.establishment else 'Estabelecimento'
            )
        if 'data_inspecao' not in report_data:
            from src.app import to_brazil_time
            report_data['data_inspecao'] = (
                to_brazil_time(inspection.created_at).strftime('%d/%m/%Y')
                if inspection.created_at else ''
            )
        if 'aproveitamento_geral' not in report_data:
            report_data['aproveitamento_geral'] = 0

        # Recalculate general scores from areas
        areas = report_data.get('areas_inspecionadas', [])
        if areas:
            total_obtido = sum(float(a.get('pontuacao_obtida', 0) or 0) for a in areas)
            total_maximo = sum(float(a.get('pontuacao_maxima', 0) or 0) for a in areas)

            if not report_data.get('pontuacao_geral'):
                report_data['pontuacao_geral'] = round(total_obtido, 2)
            if not report_data.get('pontuacao_maxima_geral'):
                report_data['pontuacao_maxima_geral'] = round(total_maximo, 2)

        pg = float(report_data.get('pontuacao_geral', 0) or 0)
        pmg = float(report_data.get('pontuacao_maxima_geral', 0) or 0)
        if pmg > 0:
            report_data['aproveitamento_geral'] = round((pg / pmg * 100), 2)

        # Enrich data for template display
        try:
            from src.services.pdf_service import pdf_service
            pdf_service.enrich_data(report_data)
        except Exception:
            pass

        # Build recipients for sharing widget
        recipients = _build_recipients(inspection)

        # Status flags
        status_value = inspection.status.value if hasattr(inspection.status, 'value') else str(inspection.status)
        is_locked = status_value in ['APPROVED', 'COMPLETED', 'PENDING_CONSULTANT_VERIFICATION']
        is_approved = status_value in ['APPROVED', 'PENDING_CONSULTANT_VERIFICATION', 'COMPLETED']

        return render_template(
            'manager_plan_edit.html',
            inspection=inspection,
            plan=plan,
            report_data=report_data,
            recipients=recipients,
            is_locked=is_locked,
            is_approved=is_approved,
        )

    except Exception as e:
        flash(f'Erro ao carregar plano: {e}', 'error')
        return redirect(url_for('manager.dashboard_manager'))


def _try_migrate_from_drive(file_id):
    """Legacy migration: import inspection data from Drive JSON."""
    drive = getattr(current_app, 'drive_service', None)
    if not drive:
        return None

    try:
        data = drive.read_json(file_id)
        if data is None:
            data = {}

        uow = get_uow()

        # Find or link establishment
        est_name = data.get('estabelecimento')
        est = None
        if est_name:
            est = uow.session.query(Establishment).filter_by(name=est_name).first()

        inspection = Inspection(
            drive_file_id=file_id,
            status=InspectionStatus.PENDING_MANAGER_REVIEW,
            establishment_id=est.id if est else None,
            ai_raw_response=data,
        )
        uow.inspections.add(inspection)
        uow.flush()

        plan = ActionPlan(inspection_id=inspection.id)
        uow.session.add(plan)
        uow.flush()

        # Parse items from legacy JSON
        items_data = data.get('nao_conformidades', [])
        for idx, item in enumerate(items_data):
            sev_str = item.get('gravidade', 'MEDIUM').upper()
            try:
                severity = SeverityLevel[sev_str]
            except (KeyError, ValueError):
                severity = SeverityLevel.MEDIUM

            uow.action_plans.add_item(ActionPlanItem(
                action_plan_id=plan.id,
                problem_description=item.get('problema', 'N/A'),
                corrective_action=item.get('acao_corretiva', 'N/A'),
                legal_basis=item.get('base_legal'),
                severity=severity,
                status=ActionPlanItemStatus.OPEN,
                order_index=idx,
            ))

        uow.commit()

        # Re-fetch via service for consistent format
        from src.container import get_inspection_data_service
        return get_inspection_data_service().get_plan_edit_data(file_id)

    except Exception as e:
        logger.error(f"Migration from Drive failed for {file_id}: {e}")
        return None


def _build_recipients(inspection):
    """Build recipients list for sharing widget."""
    recipients = []
    est = inspection.establishment
    if est and (est.responsible_name or est.responsible_email or est.responsible_phone):
        recipients.append({
            'name': est.responsible_name or 'Responsável da Loja',
            'email': est.responsible_email,
            'phone': est.responsible_phone,
            'role': 'Responsável',
        })
    return recipients


# ---------------------------------------------------------------------------
# Plan Save / Approve  (delegates to PlanService)
# ---------------------------------------------------------------------------

@manager_bp.route('/manager/plan/<file_id>/save', methods=['POST'])
@login_required
def save_plan(file_id):
    if current_user.role not in [UserRole.MANAGER, UserRole.ADMIN, UserRole.CONSULTANT]:
        return jsonify({'error': 'Unauthorized'}), 403

    data = request.json
    if not data:
        return jsonify({'error': 'No data'}), 400

    plan_svc = get_plan_service()
    result = plan_svc.save_plan(file_id, data, current_user)

    if not result.success:
        status_code = 404 if result.error == 'NOT_FOUND' else 403
        return jsonify({'error': result.message}), status_code

    return jsonify({'success': True, 'whatsapp_link': result.whatsapp_link})


@manager_bp.route('/manager/plan/<file_id>/approve', methods=['POST'])
@login_required
def approve_plan(file_id):
    if current_user.role not in [UserRole.MANAGER, UserRole.ADMIN]:
        return jsonify({'error': 'Unauthorized'}), 403

    plan_svc = get_plan_service()
    result = plan_svc.approve_plan(file_id, current_user)

    if not result.success:
        return jsonify({'error': result.message}), 404

    return jsonify({'success': True, 'message': result.message}), 200


# ---------------------------------------------------------------------------
# Manager API Status (polling endpoint)
# ---------------------------------------------------------------------------

@manager_bp.route('/api/status')
@login_required
def api_status():
    """Polling endpoint for Manager Dashboard."""
    establishment_id = request.args.get('establishment_id')
    uow = get_uow()

    try:
        # Get inspections for manager's company
        est_id_filter = None
        if establishment_id:
            try:
                est_id_filter = uuid.UUID(establishment_id)
            except ValueError:
                pass

        inspections = uow.inspections.get_for_manager(
            company_id=current_user.company_id,
            establishment_id=est_id_filter,
            limit=100,
        )

        from src.app import to_brazil_time

        # Build job info map (filename + uploader)
        file_ids = [insp.drive_file_id for insp in inspections if insp.drive_file_id]
        job_info_map = uow.jobs.get_job_info_map(file_ids)

        processed_list = []
        for insp in inspections:
            if insp.status == InspectionStatus.PROCESSING:
                continue

            est_name = insp.establishment.name if insp.establishment else 'Desconhecido'
            date_str = to_brazil_time(insp.created_at).strftime('%d/%m/%Y %H:%M') if insp.created_at else ''
            review_link = url_for('manager.edit_plan', file_id=insp.drive_file_id) if insp.drive_file_id else '#'
            job_info = job_info_map.get(insp.drive_file_id, {})
            filename = job_info.get('filename', '')
            consultant_name = job_info.get('uploaded_by_name', '')

            # Fallback: infer from establishment's assigned consultants
            if not consultant_name and insp.establishment:
                try:
                    users = insp.establishment.users
                    if users and len(users) == 1:
                        consultant_name = users[0].name
                except Exception:
                    pass

            processed_list.append({
                'id': str(insp.id),
                'establishment': est_name,
                'filename': filename,
                'consultant': consultant_name,
                'date': date_str,
                'status': insp.status.value if insp.status else 'PENDING',
                'review_link': review_link,
            })

        # Fetch pending jobs
        pending_list = []
        if current_user.company_id:
            est_ids = [e.id for e in uow.establishments.get_by_company(current_user.company_id)]
            jobs = uow.jobs.get_pending_for_company(
                company_id=current_user.company_id,
                establishment_ids=est_ids,
                limit=10,
            )

            for job in jobs:
                payload = job.input_payload or {}
                # Apply establishment filter if selected
                if establishment_id:
                    payload_est = payload.get('establishment_id')
                    if payload_est and payload_est != establishment_id:
                        continue

                fname = payload.get('filename', 'Relatório em Processamento')
                is_error = job.status == JobStatus.FAILED

                pending_list.append({
                    'name': fname,
                    'status': job.status.value,
                    'error': is_error,
                    'message': job.error_log if is_error else None,
                })

        return jsonify({
            'pending': pending_list,
            'processed_raw': processed_list,
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500
