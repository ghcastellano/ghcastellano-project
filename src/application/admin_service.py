"""Service for admin operations (company/manager CRUD with cascading)."""
import uuid
import secrets
import string
import logging
from dataclasses import dataclass
from typing import Optional

from werkzeug.security import generate_password_hash

from src.models_db import (
    Company, Establishment, User, UserRole,
    Inspection, ActionPlan, ActionPlanItem, Job,
)

logger = logging.getLogger(__name__)


@dataclass
class AdminResult:
    """Result of an admin operation."""
    success: bool
    message: str
    data: Optional[dict] = None
    error: Optional[str] = None


class AdminService:
    """Handles admin CRUD operations with proper cascade cleanup."""

    def __init__(self, uow, drive_service=None, email_service=None):
        self._uow = uow
        self._drive_service = drive_service
        self._email_service = email_service

    def create_company(self, name, cnpj=None):
        """
        Create a new company with optional Drive folder.

        Returns:
            AdminResult with company data on success.
        """
        if not name:
            return AdminResult(success=False, message='Nome da empresa é obrigatório.', error='MISSING_NAME')

        if cnpj and self._uow.companies.get_by_cnpj(cnpj):
            return AdminResult(success=False, message=f'Já existe uma empresa com o CNPJ {cnpj}.', error='DUPLICATE_CNPJ')

        company = Company(id=uuid.uuid4(), name=name, cnpj=cnpj)

        # Create Drive folder
        drive_folder_created = False
        if self._drive_service and getattr(self._drive_service, 'service', None):
            try:
                from src.config_helper import get_config
                root_id = get_config('GDRIVE_ROOT_FOLDER_ID')
                f_id, f_link = self._drive_service.create_folder(folder_name=name, parent_id=root_id)
                if f_id:
                    company.drive_folder_id = f_id
                    drive_folder_created = True
            except Exception as e:
                logger.error(f'Failed to create Drive folder: {e}')

        self._uow.companies.add(company)

        # Capture data before commit (SQLAlchemy expires attributes after commit)
        company_id = str(company.id)
        company_name = company.name
        company_cnpj = company.cnpj

        self._uow.commit()

        msg = f'Empresa {name} criada com sucesso!'
        if not drive_folder_created:
            msg += ' Pasta no Drive não pôde ser criada.'

        return AdminResult(
            success=True,
            message=msg,
            data={
                'id': company_id,
                'name': company_name,
                'cnpj': company_cnpj,
            },
        )

    def delete_company(self, company_id):
        """
        Delete company with full cascade: jobs, users, establishments, inspections.

        Returns:
            AdminResult.
        """
        company = self._uow.companies.get_by_id(company_id)
        if not company:
            return AdminResult(success=False, message='Empresa não encontrada.', error='NOT_FOUND')

        session = self._uow.session

        # 1. Delete Jobs
        session.query(Job).filter(Job.company_id == company_id).delete()

        # 2. Delete Users (nullify approvals first)
        users = session.query(User).filter(User.company_id == company_id).all()
        for user in users:
            session.query(ActionPlan).filter(
                ActionPlan.approved_by_id == user.id
            ).update({ActionPlan.approved_by_id: None})
            session.delete(user)

        # 3. Delete Establishments with nested cleanup
        establishments = session.query(Establishment).filter(
            Establishment.company_id == company_id
        ).all()
        for est in establishments:
            self._delete_establishment_cascade(session, est)

        # 4. Delete company Drive folder
        if company.drive_folder_id and self._drive_service:
            try:
                self._drive_service.delete_folder(company.drive_folder_id)
            except Exception as e:
                logger.error(f'Failed to delete Drive folder: {e}')

        # 5. Delete company
        session.delete(company)
        self._uow.commit()

        return AdminResult(success=True, message='Empresa e todos os dados vinculados removidos.')

    def create_manager(self, name, email, company_id, password=None):
        """
        Create a new manager user with strong password.

        Returns:
            AdminResult with user data and generated password.
        """
        if not email or not company_id:
            return AdminResult(success=False, message='Email e Empresa são obrigatórios.', error='MISSING_FIELDS')

        existing = self._uow.users.get_by_email(email)
        if existing:
            return AdminResult(success=False, message='Email já cadastrado.', error='DUPLICATE_EMAIL')

        # Generate strong password if not provided
        if not password or password == '123456':
            alphabet = string.ascii_letters + string.digits + '!@#$%&'
            password = ''.join(secrets.choice(alphabet) for _ in range(12))

        hashed = generate_password_hash(password)
        user = User(
            id=uuid.uuid4(),
            name=name,
            email=email,
            password_hash=hashed,
            role=UserRole.MANAGER,
            company_id=uuid.UUID(str(company_id)),
            must_change_password=True,
        )
        self._uow.users.add(user)

        # Capture data before commit (SQLAlchemy expires attributes after commit)
        user_id = str(user.id)
        user_name = user.name
        user_email = user.email
        company_name = ''
        try:
            company = self._uow.companies.get_by_id(company_id)
            if company:
                company_name = company.name
        except Exception:
            pass

        self._uow.commit()

        # Send welcome email
        email_sent = False
        if self._email_service:
            try:
                email_sent = self._email_service.send_welcome_email(email, name, password)
            except Exception as e:
                logger.error(f'Failed to send welcome email: {e}')

        return AdminResult(
            success=True,
            message=f'Gestor {name} criado com sucesso!',
            data={
                'id': user_id,
                'name': user_name,
                'email': user_email,
                'company_name': company_name,
                'company_id': str(company_id),
                'password': password,
                'email_sent': email_sent,
            },
        )

    def delete_manager(self, user_id):
        """
        Delete a manager, preserving action plan history.

        Returns:
            AdminResult.
        """
        user = self._uow.users.get_by_id(user_id)
        if not user or user.role != UserRole.MANAGER:
            return AdminResult(success=False, message='Gestor não encontrado.', error='NOT_FOUND')

        # Nullify approvals (preserve history)
        self._uow.session.query(ActionPlan).filter(
            ActionPlan.approved_by_id == user.id
        ).update({ActionPlan.approved_by_id: None})

        self._uow.users.delete(user)
        self._uow.commit()

        return AdminResult(success=True, message='Gestor removido com sucesso.')

    def update_manager(self, user_id, name=None, email=None, company_id=None, password=None):
        """
        Update manager fields.

        Returns:
            AdminResult.
        """
        user = self._uow.users.get_by_id(user_id)
        if not user or user.role != UserRole.MANAGER:
            return AdminResult(success=False, message='Gestor não encontrado.', error='NOT_FOUND')

        if name:
            user.name = name
        if email:
            user.email = email

        if company_id and str(company_id).strip():
            user.company_id = uuid.UUID(str(company_id))
        elif company_id is not None:
            user.company_id = None

        if password and len(password.strip()) > 0:
            user.password_hash = generate_password_hash(password)

        self._uow.commit()
        return AdminResult(success=True, message='Gestor atualizado com sucesso.')

    def get_monitor_data(self, limit=50):
        """
        Get recent jobs for admin monitoring.

        Returns:
            List of job dicts.
        """
        jobs = self._uow.jobs.get_for_monitor(limit=limit)
        result = []
        for job in jobs:
            payload = job.input_payload or {}
            result.append({
                'id': str(job.id),
                'type': job.type,
                'status': job.status.value if hasattr(job.status, 'value') else str(job.status),
                'company': job.company.name if job.company else 'N/A',
                'filename': payload.get('filename', 'N/A'),
                'establishment': payload.get('establishment_name', 'N/A'),
                'created_at': job.created_at.strftime('%d/%m/%Y %H:%M') if job.created_at else '',
                'execution_time': round(job.execution_time_seconds, 1) if job.execution_time_seconds else 0,
                'error_log': job.error_log[:100] if job.error_log else None,
            })
        return result

    def _delete_establishment_cascade(self, session, est):
        """Delete establishment with all nested inspections/plans."""
        inspections = session.query(Inspection).filter(
            Inspection.establishment_id == est.id
        ).all()
        for insp in inspections:
            if insp.action_plan:
                session.query(ActionPlanItem).filter(
                    ActionPlanItem.action_plan_id == insp.action_plan.id
                ).delete()
                session.delete(insp.action_plan)
            session.delete(insp)

        # Delete Drive folder
        if est.drive_folder_id and self._drive_service:
            try:
                self._drive_service.delete_folder(est.drive_folder_id)
            except Exception as e:
                logger.error(f'Failed to delete establishment Drive folder: {e}')

        session.delete(est)
