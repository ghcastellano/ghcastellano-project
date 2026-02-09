"""Unit tests for domain entities."""

import pytest
from uuid import uuid4

from src.domain import (
    User, UserRole, Company, Establishment,
    Inspection, InspectionStatus, ActionPlan, ActionPlanItem, ActionPlanItemStatus,
    ValidationError, BusinessRuleViolationError, InvalidStatusTransitionError,
    Email, Phone, SeverityLevel
)


class TestUser:
    """Tests for User entity."""

    def test_create_consultant(self):
        """Should create consultant with factory method."""
        company_id = uuid4()
        user = User.create_consultant(
            email="consultant@test.com",
            name="Test Consultant",
            company_id=company_id
        )
        assert user.is_consultant
        assert user.role == UserRole.CONSULTANT
        assert user.must_change_password

    def test_create_manager(self):
        """Should create manager with factory method."""
        company_id = uuid4()
        user = User.create_manager(
            email="manager@test.com",
            name="Test Manager",
            company_id=company_id
        )
        assert user.is_manager
        assert user.role == UserRole.MANAGER

    def test_create_admin(self):
        """Should create admin with factory method."""
        user = User.create_admin(
            email="admin@test.com",
            name="Test Admin"
        )
        assert user.is_admin
        assert user.role == UserRole.ADMIN

    def test_user_requires_email(self):
        """Should require email."""
        with pytest.raises(ValidationError):
            User(email=None, name="Test")

    def test_deactivate_user(self):
        """Should deactivate active user."""
        user = User.create_consultant("test@test.com", "Test", uuid4())
        assert user.is_active
        user.deactivate()
        assert not user.is_active

    def test_deactivate_inactive_raises_error(self):
        """Should raise error when deactivating inactive user."""
        user = User.create_consultant("test@test.com", "Test", uuid4())
        user.deactivate()
        with pytest.raises(BusinessRuleViolationError):
            user.deactivate()

    def test_password_change_flow(self):
        """Should handle password change requirement."""
        user = User.create_consultant("test@test.com", "Test", uuid4())
        assert user.must_change_password
        user.password_changed()
        assert not user.must_change_password

    def test_display_name(self):
        """Should return name or email as display name."""
        user1 = User.create_consultant("test@test.com", "John Doe", uuid4())
        user2 = User.create_consultant("noname@test.com", None, uuid4())
        assert user1.display_name == "John Doe"
        assert user2.display_name == "noname@test.com"


class TestUserRole:
    """Tests for UserRole enum."""

    def test_can_approve_plans(self):
        """Manager and Admin should be able to approve plans."""
        assert UserRole.MANAGER.can_approve_plans
        assert UserRole.ADMIN.can_approve_plans
        assert not UserRole.CONSULTANT.can_approve_plans

    def test_can_access_admin(self):
        """Only Admin should access admin panel."""
        assert UserRole.ADMIN.can_access_admin
        assert not UserRole.MANAGER.can_access_admin
        assert not UserRole.CONSULTANT.can_access_admin


class TestCompany:
    """Tests for Company entity."""

    def test_create_company(self):
        """Should create company with factory method."""
        company = Company.create("Test Company", "12345678901234")
        assert company.name == "Test Company"
        assert company.cnpj == "12345678901234"

    def test_company_requires_name(self):
        """Should require name."""
        with pytest.raises(ValidationError):
            Company(name="")

    def test_cnpj_normalization(self):
        """Should strip formatting from CNPJ."""
        company = Company.create("Test", "12.345.678/0001-90")
        assert company.cnpj == "12345678000190"

    def test_cnpj_formatted(self):
        """Should format CNPJ correctly."""
        company = Company.create("Test", "12345678000190")
        assert company.cnpj_formatted == "12.345.678/0001-90"

    def test_deactivate_company(self):
        """Should deactivate active company."""
        company = Company.create("Test")
        assert company.is_active
        company.deactivate()
        assert not company.is_active


class TestEstablishment:
    """Tests for Establishment entity."""

    def test_create_establishment(self):
        """Should create establishment with factory method."""
        est = Establishment.create(
            name="Test Store",
            company_id=uuid4(),
            code="STORE001"
        )
        assert est.name == "Test Store"
        assert est.code == "STORE001"

    def test_establishment_requires_name(self):
        """Should require name."""
        with pytest.raises(ValidationError):
            Establishment(name="")

    def test_code_normalization(self):
        """Should normalize code to uppercase."""
        est = Establishment.create("Test", uuid4(), code="store001")
        assert est.code == "STORE001"

    def test_update_responsible(self):
        """Should update responsible person info."""
        est = Establishment.create("Test", uuid4())
        est.update_responsible(
            name="John Doe",
            email="john@test.com",
            phone="11999998888"
        )
        assert est.responsible_name == "John Doe"
        assert est.can_send_whatsapp
        assert est.can_send_email


class TestInspection:
    """Tests for Inspection entity."""

    def test_create_inspection(self):
        """Should create inspection with factory method."""
        insp = Inspection.create(
            drive_file_id="abc123",
            establishment_id=uuid4()
        )
        assert insp.drive_file_id == "abc123"
        assert insp.status == InspectionStatus.PROCESSING

    def test_inspection_requires_drive_file_id(self):
        """Should require drive_file_id."""
        with pytest.raises(ValidationError):
            Inspection(drive_file_id="")

    def test_status_workflow(self):
        """Should follow status workflow."""
        insp = Inspection.create("abc123", uuid4())

        # Processing -> Pending Review
        assert insp.is_processing
        insp.mark_processing_complete()
        assert insp.is_pending_review

        # Pending Review -> Approved
        insp.approve()
        assert insp.is_approved

        # Approved -> Completed
        insp.complete()
        assert insp.is_completed

    def test_invalid_status_transition(self):
        """Should raise error for invalid transition."""
        insp = Inspection.create("abc123", uuid4())
        with pytest.raises(InvalidStatusTransitionError):
            insp.approve()  # Can't approve while processing

    def test_add_processing_log(self):
        """Should add processing log entries."""
        insp = Inspection.create("abc123", uuid4())
        insp.add_processing_log("Started processing", "AI_PROCESS")
        assert len(insp.processing_logs) == 1
        assert insp.processing_logs[0]["message"] == "Started processing"


class TestInspectionStatus:
    """Tests for InspectionStatus enum."""

    def test_terminal_status(self):
        """COMPLETED and REJECTED should be terminal."""
        assert InspectionStatus.COMPLETED.is_terminal
        assert InspectionStatus.REJECTED.is_terminal
        assert not InspectionStatus.PROCESSING.is_terminal

    def test_editable_status(self):
        """Only certain statuses should be editable."""
        assert InspectionStatus.PENDING_MANAGER_REVIEW.is_editable
        assert InspectionStatus.APPROVED.is_editable
        assert not InspectionStatus.PROCESSING.is_editable


class TestActionPlan:
    """Tests for ActionPlan entity."""

    def test_create_action_plan(self):
        """Should create action plan with factory method."""
        plan = ActionPlan.create(inspection_id=uuid4())
        assert plan.inspection_id is not None
        assert plan.item_count == 0

    def test_add_item(self):
        """Should add items to plan."""
        plan = ActionPlan.create(uuid4())
        item = ActionPlanItem(
            problem_description="Problem 1",
            corrective_action="Fix it"
        )
        plan.add_item(item)
        assert plan.item_count == 1

    def test_items_sorted_by_sector(self):
        """Items should be sorted by sector and order."""
        plan = ActionPlan.create(uuid4())
        plan.add_item(ActionPlanItem(
            problem_description="B",
            corrective_action="Fix",
            sector="Cozinha"
        ))
        plan.add_item(ActionPlanItem(
            problem_description="A",
            corrective_action="Fix",
            sector="Almoxarifado"
        ))

        items = plan.items
        assert items[0].sector == "Almoxarifado"
        assert items[1].sector == "Cozinha"

    def test_approve_plan(self):
        """Should approve plan with approver ID."""
        plan = ActionPlan.create(uuid4())
        approver_id = uuid4()
        plan.approve(approver_id)
        assert plan.is_approved
        assert plan.approved_by_id == approver_id
        assert plan.approved_at is not None

    def test_cannot_approve_twice(self):
        """Should not allow approving twice."""
        plan = ActionPlan.create(uuid4())
        plan.approve(uuid4())
        with pytest.raises(BusinessRuleViolationError):
            plan.approve(uuid4())

    def test_resolution_percentage(self):
        """Should calculate resolution percentage."""
        plan = ActionPlan.create(uuid4())
        plan.add_item(ActionPlanItem(problem_description="P1", corrective_action="A1"))
        plan.add_item(ActionPlanItem(problem_description="P2", corrective_action="A2"))

        assert plan.resolution_percentage == 0.0

        plan.items[0].resolve()
        assert plan.resolution_percentage == 50.0


class TestActionPlanItem:
    """Tests for ActionPlanItem entity."""

    def test_create_item(self):
        """Should create item with required fields."""
        item = ActionPlanItem(
            problem_description="Test Problem",
            corrective_action="Test Action"
        )
        assert item.problem_description == "Test Problem"
        assert item.status == ActionPlanItemStatus.OPEN

    def test_item_requires_problem(self):
        """Should require problem description."""
        with pytest.raises(ValidationError):
            ActionPlanItem(
                problem_description="",
                corrective_action="Action"
            )

    def test_item_requires_action(self):
        """Should require corrective action."""
        with pytest.raises(ValidationError):
            ActionPlanItem(
                problem_description="Problem",
                corrective_action=""
            )

    def test_from_ai_response(self):
        """Should create item from AI response preserving original data."""
        item = ActionPlanItem.from_ai_response(
            problem="AI Problem",
            action="AI Action",
            sector="Kitchen",
            score=6.5,
            status="Parcialmente Conforme"
        )
        assert item.original_score == 6.5
        assert item.original_status == "Parcialmente Conforme"
        assert item.severity == SeverityLevel.MEDIUM

    def test_resolve_item(self):
        """Should resolve item with optional notes."""
        item = ActionPlanItem(
            problem_description="Problem",
            corrective_action="Action"
        )
        item.resolve("Fixed successfully")
        assert item.is_resolved
        assert item.manager_notes == "Fixed successfully"

    def test_reopen_item(self):
        """Should reopen resolved item."""
        item = ActionPlanItem(
            problem_description="Problem",
            corrective_action="Action"
        )
        item.resolve()
        item.reopen()
        assert item.is_open

    def test_add_evidence(self):
        """Should add evidence URL."""
        item = ActionPlanItem(
            problem_description="Problem",
            corrective_action="Action"
        )
        item.add_evidence("https://example.com/image.jpg")
        assert item.has_evidence
        assert item.evidence_image_url == "https://example.com/image.jpg"

    def test_add_empty_evidence_raises_error(self):
        """Should raise error for empty evidence URL."""
        item = ActionPlanItem(
            problem_description="Problem",
            corrective_action="Action"
        )
        with pytest.raises(ValidationError):
            item.add_evidence("")
