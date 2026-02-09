"""Service for plan save, approve, and review operations."""
import uuid
import urllib.parse
from datetime import datetime
from dataclasses import dataclass
from typing import Optional

from src.models_db import (
    InspectionStatus, ActionPlanItem, ActionPlanItemStatus, SeverityLevel,
)


@dataclass
class PlanResult:
    """Result of a plan operation."""
    success: bool
    message: str
    whatsapp_link: Optional[str] = None
    error: Optional[str] = None


class PlanService:
    """Handles plan save, approve, and review finalization."""

    def __init__(self, uow, pdf_service=None, storage_service=None):
        self._uow = uow
        self._pdf_service = pdf_service
        self._storage_service = storage_service

    def save_plan(self, file_id, data, current_user):
        """
        Save plan edits (items, summary, strengths).

        Args:
            file_id: Drive file ID of the inspection.
            data: JSON payload with items, summary_text, strengths_text, approve flag.
            current_user: The user performing the save.

        Returns:
            PlanResult with success/error details.
        """
        inspection = self._uow.inspections.get_by_drive_file_id(file_id)
        if not inspection or not inspection.action_plan:
            return PlanResult(success=False, message='Plan not found', error='NOT_FOUND')

        if inspection.status == InspectionStatus.APPROVED:
            return PlanResult(
                success=False,
                message='Este plano já foi aprovado e não pode mais ser editado.',
                error='ALREADY_APPROVED',
            )

        plan = inspection.action_plan

        # Save enriched fields
        if 'summary_text' in data:
            plan.summary_text = data.get('summary_text')
        if 'strengths_text' in data:
            plan.strengths_text = data.get('strengths_text')

        # Process items (upsert)
        self._process_items(plan, data.get('items', []))

        # Update establishment responsible info
        self._update_responsible_info(inspection, data)

        # Handle approval
        whatsapp_link = None
        if data.get('approve'):
            whatsapp_link = self._do_approve(inspection, plan, current_user, data)

        self._uow.commit()
        return PlanResult(success=True, message='Plano salvo com sucesso!', whatsapp_link=whatsapp_link)

    def approve_plan(self, file_id, current_user):
        """
        Approve plan directly (without item edits).

        Args:
            file_id: Drive file ID of the inspection.
            current_user: The user approving.

        Returns:
            PlanResult with success/error details.
        """
        inspection = self._uow.inspections.get_by_drive_file_id(file_id)
        if not inspection or not inspection.action_plan:
            return PlanResult(success=False, message='Plan not found', error='NOT_FOUND')

        plan = inspection.action_plan
        whatsapp_link = self._do_approve(inspection, plan, current_user, {})

        self._uow.commit()
        return PlanResult(success=True, message='Plano aprovado com sucesso!', whatsapp_link=whatsapp_link)

    def save_review(self, file_id, updates):
        """
        Save consultant review changes (item status updates).

        Args:
            file_id: Drive file ID.
            updates: Dict with item updates from consultant review.

        Returns:
            PlanResult.
        """
        inspection = self._uow.inspections.get_by_drive_file_id(file_id)
        if not inspection or not inspection.action_plan:
            return PlanResult(success=False, message='Plan not found', error='NOT_FOUND')

        plan = inspection.action_plan
        items_data = updates.get('items', [])

        for item_data in items_data:
            item_id = item_data.get('id')
            if not item_id:
                continue

            item = self._uow.action_plans.get_item_by_id(uuid.UUID(item_id))
            if not item or item.action_plan_id != plan.id:
                continue

            if 'current_status' in item_data:
                item.current_status = item_data['current_status']
            if 'manager_notes' in item_data:
                item.manager_notes = item_data['manager_notes']
            if 'evidence_image_url' in item_data:
                item.evidence_image_url = item_data['evidence_image_url']

        self._uow.commit()
        return PlanResult(success=True, message='Review salva com sucesso!')

    def finalize_verification(self, file_id):
        """
        Mark inspection as COMPLETED after consultant verification.

        Args:
            file_id: Drive file ID.

        Returns:
            PlanResult.
        """
        inspection = self._uow.inspections.get_by_drive_file_id(file_id)
        if not inspection:
            return PlanResult(success=False, message='Inspection not found', error='NOT_FOUND')

        inspection.status = InspectionStatus.COMPLETED
        self._uow.commit()
        return PlanResult(success=True, message='Verificação finalizada!')

    def _process_items(self, plan, items_payload):
        """Process item upserts (update existing or create new)."""
        for item_data in items_payload:
            if item_data.get('id'):
                self._update_item(plan, item_data)
            else:
                self._create_item(plan, item_data)

    @staticmethod
    def _update_responsible_info(inspection, data):
        """Update establishment responsible contact info if provided."""
        resp_name = data.get('responsible_name')
        resp_phone = data.get('responsible_phone')
        resp_email = data.get('responsible_email')

        if inspection.establishment and (resp_name or resp_phone or resp_email):
            if resp_name:
                inspection.establishment.responsible_name = resp_name
            if resp_phone:
                inspection.establishment.responsible_phone = resp_phone
            if resp_email:
                inspection.establishment.responsible_email = resp_email

    def _update_item(self, plan, item_data):
        """Update an existing plan item."""
        item = self._uow.action_plans.get_item_by_id(uuid.UUID(item_data['id']))
        if not item or item.action_plan_id != plan.id:
            return

        if 'problem' in item_data:
            item.problem_description = item_data['problem']
        if 'action' in item_data:
            item.corrective_action = item_data['action']
        if 'legal_basis' in item_data:
            item.legal_basis = item_data['legal_basis']
        if 'severity' in item_data:
            try:
                item.severity = SeverityLevel(item_data.get('severity', 'MEDIUM'))
            except ValueError:
                item.severity = SeverityLevel.MEDIUM
        if 'current_status' in item_data:
            item.current_status = item_data['current_status']

        if 'deadline' in item_data and item_data.get('deadline'):
            self._set_deadline(item, item_data['deadline'])

    def _create_item(self, plan, item_data):
        """Create a new plan item."""
        deadline_date = None
        deadline_text = None

        if item_data.get('deadline'):
            deadline_text = item_data['deadline']
            deadline_date = self._parse_date(deadline_text)

        severity = SeverityLevel.MEDIUM
        if item_data.get('severity') and item_data['severity'] in SeverityLevel._member_names_:
            severity = SeverityLevel(item_data['severity'])

        new_item = ActionPlanItem(
            action_plan_id=plan.id,
            problem_description=item_data.get('problem', ''),
            corrective_action=item_data.get('action', ''),
            legal_basis=item_data.get('legal_basis'),
            severity=severity,
            status=ActionPlanItemStatus.OPEN,
            deadline_date=deadline_date,
            deadline_text=deadline_text,
            order_index=len(plan.items) if plan.items else 0,
            current_status='Pendente',
        )
        self._uow.action_plans.add_item(new_item)

    def _do_approve(self, inspection, plan, current_user, data):
        """Execute approval logic: change status, generate PDF, build WhatsApp link."""
        inspection.status = InspectionStatus.PENDING_CONSULTANT_VERIFICATION
        plan.approved_by_id = current_user.id
        plan.approved_at = datetime.utcnow()

        # Generate and cache PDF
        self._generate_cached_pdf(inspection, plan)

        # Build WhatsApp link if phone provided
        resp_name = data.get('responsible_name')
        resp_phone = data.get('responsible_phone')
        if not resp_phone and inspection.establishment:
            resp_phone = inspection.establishment.responsible_phone
            resp_name = resp_name or (inspection.establishment.responsible_name if inspection.establishment else None)

        return self._build_whatsapp_link(
            resp_phone, resp_name, inspection, plan,
        )

    def _generate_cached_pdf(self, inspection, plan):
        """Generate PDF and store URL on plan."""
        if not self._pdf_service or not self._storage_service:
            return

        try:
            from src.application.inspection_data_service import InspectionDataService
            import io

            data_service = InspectionDataService(self._uow)
            pdf_data = data_service.get_pdf_data(inspection.drive_file_id)

            pdf_bytes = self._pdf_service.generate_pdf_bytes(pdf_data)
            filename = f'Plano_Aprovado_{inspection.id}.pdf'
            pdf_url = self._storage_service.upload_file(
                io.BytesIO(pdf_bytes),
                destination_folder='approved_pdfs',
                filename=filename,
            )
            plan.final_pdf_url = pdf_url
        except Exception:
            pass  # Don't block approval

    @staticmethod
    def _build_whatsapp_link(phone, name, inspection, plan):
        """Build WhatsApp share link with approval message."""
        if not phone:
            return None

        clean_phone = ''.join(filter(str.isdigit, phone))
        if len(clean_phone) <= 11:
            clean_phone = '55' + clean_phone

        download_url = plan.final_pdf_url or ''
        est_name = inspection.establishment.name if inspection.establishment else ''
        msg = f'Olá {name or "Responsável"}, seu Plano de Ação para {est_name} foi aprovado. Acesso: {download_url}'

        return f'https://wa.me/{clean_phone}?text={urllib.parse.quote(msg)}'

    @staticmethod
    def _set_deadline(item, deadline_input):
        """Set deadline on item: save text + try to parse as date."""
        if deadline_input != item.ai_suggested_deadline:
            item.deadline_text = deadline_input

        item.deadline_date = PlanService._parse_date(deadline_input)

    @staticmethod
    def _parse_date(text):
        """Try parsing a date string in ISO or BR format."""
        if not text:
            return None
        try:
            return datetime.strptime(text, '%Y-%m-%d').date()
        except ValueError:
            try:
                return datetime.strptime(text, '%d/%m/%Y').date()
            except ValueError:
                return None
