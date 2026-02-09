"""
Supplementary unit tests for domain entities.

Covers all methods and properties not exercised in test_entities.py,
ensuring complete coverage of the domain entity layer.
"""

import pytest
from uuid import uuid4

from src.domain import (
    User, UserRole, Company, Establishment,
    Inspection, InspectionStatus, ActionPlan, ActionPlanItem, ActionPlanItemStatus,
    ValidationError, BusinessRuleViolationError, InvalidStatusTransitionError,
    Email, Phone, SeverityLevel
)
from src.domain.entities.establishment import Contact
from src.domain.value_objects import Score


# ---------------------------------------------------------------------------
# ActionPlanItemStatus
# ---------------------------------------------------------------------------

class TestActionPlanItemStatusExtra:
    """Tests for ActionPlanItemStatus.label_pt property."""

    def test_open_label_pt(self):
        """OPEN status should return 'Pendente'."""
        assert ActionPlanItemStatus.OPEN.label_pt == "Pendente"

    def test_in_progress_label_pt(self):
        """IN_PROGRESS status should return 'Em Andamento'."""
        assert ActionPlanItemStatus.IN_PROGRESS.label_pt == "Em Andamento"

    def test_resolved_label_pt(self):
        """RESOLVED status should return 'Corrigido'."""
        assert ActionPlanItemStatus.RESOLVED.label_pt == "Corrigido"


# ---------------------------------------------------------------------------
# ActionPlanItem
# ---------------------------------------------------------------------------

class TestActionPlanItemExtra:
    """Tests for ActionPlanItem methods/properties not covered elsewhere."""

    def _make_item(self, **kwargs):
        """Helper to build a minimal ActionPlanItem."""
        defaults = dict(
            problem_description="Problema de teste",
            corrective_action="Acao corretiva de teste",
        )
        defaults.update(kwargs)
        return ActionPlanItem(**defaults)

    # -- score property ----------------------------------------------------

    def test_score_returns_score_object_when_original_score_present(self):
        """score should return a Score value object when original_score is set."""
        item = ActionPlanItem.from_ai_response(
            problem="Prob",
            action="Act",
            score=7.5,
            status="Parcialmente Conforme",
        )
        score = item.score
        assert isinstance(score, Score)
        assert score.value == 7.5
        assert score.status == "Parcialmente Conforme"

    def test_score_returns_none_when_no_original_score(self):
        """score should return None when original_score is not set."""
        item = self._make_item()
        assert item.score is None

    def test_score_returns_score_with_zero_value(self):
        """score should return a Score object even when original_score is 0.0."""
        item = ActionPlanItem.from_ai_response(
            problem="Prob",
            action="Act",
            score=0.0,
            status="Nao Conforme",
        )
        score = item.score
        assert score is not None
        assert score.value == 0.0

    # -- start_progress ----------------------------------------------------

    def test_start_progress_sets_status_and_current_status(self):
        """start_progress should set IN_PROGRESS and 'Em Verificacao'."""
        item = self._make_item()
        item.start_progress()
        assert item.status == ActionPlanItemStatus.IN_PROGRESS
        assert item.current_status == "Em Verificação"

    # -- update_content ----------------------------------------------------

    def test_update_content_problem_only(self):
        """update_content should update only problem when given."""
        item = self._make_item()
        item.update_content(problem="  Novo problema  ")
        assert item.problem_description == "Novo problema"
        assert item.corrective_action == "Acao corretiva de teste"

    def test_update_content_action_only(self):
        """update_content should update only action when given."""
        item = self._make_item()
        item.update_content(action="  Nova acao  ")
        assert item.corrective_action == "Nova acao"
        assert item.problem_description == "Problema de teste"

    def test_update_content_deadline_and_notes(self):
        """update_content should update deadline_text and manager_notes."""
        item = self._make_item()
        item.update_content(deadline_text="30 dias", notes="Nota gerencial")
        assert item.deadline_text == "30 dias"
        assert item.manager_notes == "Nota gerencial"

    def test_update_content_all_fields(self):
        """update_content should update all fields at once."""
        item = self._make_item()
        item.update_content(
            problem="P2",
            action="A2",
            deadline_text="7 dias",
            notes="Urgente",
        )
        assert item.problem_description == "P2"
        assert item.corrective_action == "A2"
        assert item.deadline_text == "7 dias"
        assert item.manager_notes == "Urgente"

    def test_update_content_empty_problem_raises_validation_error(self):
        """update_content should raise ValidationError for blank problem."""
        item = self._make_item()
        with pytest.raises(ValidationError):
            item.update_content(problem="   ")

    def test_update_content_empty_action_raises_validation_error(self):
        """update_content should raise ValidationError for blank action."""
        item = self._make_item()
        with pytest.raises(ValidationError):
            item.update_content(action="  ")

    def test_update_content_none_values_leave_fields_unchanged(self):
        """update_content with all-None args should leave item unchanged."""
        item = self._make_item()
        original_problem = item.problem_description
        original_action = item.corrective_action
        item.update_content()
        assert item.problem_description == original_problem
        assert item.corrective_action == original_action

    # -- __str__ -----------------------------------------------------------

    def test_str_with_sector(self):
        """__str__ should include sector when present."""
        item = self._make_item(sector="Cozinha")
        text = str(item)
        assert "[Cozinha]" in text
        assert "ActionPlanItem(" in text

    def test_str_without_sector(self):
        """__str__ should omit sector bracket when sector is None."""
        item = self._make_item()
        text = str(item)
        assert "[" not in text
        assert "ActionPlanItem(" in text

    def test_str_truncates_long_problem(self):
        """__str__ should truncate problem description to 30 chars."""
        long_problem = "A" * 50
        item = self._make_item(problem_description=long_problem)
        text = str(item)
        # The first 30 characters followed by '...'
        assert "A" * 30 + "..." in text


# ---------------------------------------------------------------------------
# ActionPlan
# ---------------------------------------------------------------------------

class TestActionPlanExtra:
    """Tests for ActionPlan methods/properties not covered elsewhere."""

    def _make_plan(self, **kwargs):
        """Helper to build a minimal ActionPlan."""
        defaults = dict(inspection_id=uuid4())
        defaults.update(kwargs)
        return ActionPlan(**defaults)

    def _make_item(self, **kwargs):
        defaults = dict(
            problem_description="Problema",
            corrective_action="Acao",
        )
        defaults.update(kwargs)
        return ActionPlanItem(**defaults)

    # -- __post_init__ -----------------------------------------------------

    def test_post_init_raises_when_inspection_id_is_none(self):
        """ActionPlan should raise ValidationError when inspection_id is None."""
        with pytest.raises(ValidationError):
            ActionPlan(inspection_id=None)

    # -- open_items_count --------------------------------------------------

    def test_open_items_count(self):
        """open_items_count should return only open items."""
        plan = self._make_plan()
        item1 = self._make_item()
        item2 = self._make_item(problem_description="P2")
        item3 = self._make_item(problem_description="P3")
        plan.add_item(item1)
        plan.add_item(item2)
        plan.add_item(item3)
        item2.resolve()
        assert plan.open_items_count == 2

    # -- has_pdf -----------------------------------------------------------

    def test_has_pdf_false_by_default(self):
        """has_pdf should be False when no PDF URL set."""
        plan = self._make_plan()
        assert plan.has_pdf is False

    def test_has_pdf_true_when_url_set(self):
        """has_pdf should be True when final_pdf_url is set."""
        plan = self._make_plan()
        plan.set_pdf_url("https://example.com/plan.pdf")
        assert plan.has_pdf is True

    # -- sectors -----------------------------------------------------------

    def test_sectors_returns_sorted_unique_sectors(self):
        """sectors should return unique sectors in sorted order."""
        plan = self._make_plan()
        plan.add_item(self._make_item(sector="Cozinha"))
        plan.add_item(self._make_item(problem_description="P2", sector="Almoxarifado"))
        plan.add_item(self._make_item(problem_description="P3", sector="Cozinha"))
        plan.add_item(self._make_item(problem_description="P4"))  # no sector
        assert plan.sectors == ["Almoxarifado", "Cozinha"]

    def test_sectors_empty_when_no_items(self):
        """sectors should return empty list when plan has no items."""
        plan = self._make_plan()
        assert plan.sectors == []

    # -- items_by_sector ---------------------------------------------------

    def test_items_by_sector_groups_correctly(self):
        """items_by_sector should group items and use 'Geral' for None sector."""
        plan = self._make_plan()
        plan.add_item(self._make_item(sector="Cozinha"))
        plan.add_item(self._make_item(problem_description="P2", sector="Cozinha"))
        plan.add_item(self._make_item(problem_description="P3"))  # sector=None -> "Geral"
        by_sector = plan.items_by_sector
        assert len(by_sector["Cozinha"]) == 2
        assert len(by_sector["Geral"]) == 1

    # -- overall_score / overall_percentage --------------------------------

    def test_overall_score_from_stats(self):
        """overall_score should return value from stats_json."""
        plan = self._make_plan()
        plan.set_stats({"score": 8.5, "percentage": 85.0})
        assert plan.overall_score == 8.5

    def test_overall_score_none_when_no_stats(self):
        """overall_score should return None when stats_json is None."""
        plan = self._make_plan()
        assert plan.overall_score is None

    def test_overall_percentage_from_stats(self):
        """overall_percentage should return value from stats_json."""
        plan = self._make_plan()
        plan.set_stats({"score": 8.5, "percentage": 85.0})
        assert plan.overall_percentage == 85.0

    def test_overall_percentage_none_when_no_stats(self):
        """overall_percentage should return None when stats_json is None."""
        plan = self._make_plan()
        assert plan.overall_percentage is None

    # -- remove_item -------------------------------------------------------

    def test_remove_item_removes_and_reindexes(self):
        """remove_item should remove item and reindex remaining items."""
        plan = self._make_plan()
        item1 = self._make_item()
        item2 = self._make_item(problem_description="P2")
        item3 = self._make_item(problem_description="P3")
        plan.add_item(item1)
        plan.add_item(item2)
        plan.add_item(item3)

        plan.remove_item(item2.id)
        assert plan.item_count == 2
        # Remaining items should have sequential order_index
        remaining = plan._items
        assert remaining[0].order_index == 0
        assert remaining[1].order_index == 1

    def test_remove_item_nonexistent_id_does_nothing_harmful(self):
        """remove_item with non-existent ID should not crash."""
        plan = self._make_plan()
        plan.add_item(self._make_item())
        plan.remove_item(uuid4())
        assert plan.item_count == 1

    # -- get_item ----------------------------------------------------------

    def test_get_item_returns_item_by_id(self):
        """get_item should return the matching item."""
        plan = self._make_plan()
        item = self._make_item()
        plan.add_item(item)
        found = plan.get_item(item.id)
        assert found is item

    def test_get_item_returns_none_for_unknown_id(self):
        """get_item should return None when no item matches."""
        plan = self._make_plan()
        assert plan.get_item(uuid4()) is None

    # -- set_stats ---------------------------------------------------------

    def test_set_stats_updates_stats_and_marks_updated(self):
        """set_stats should store stats and mark entity updated."""
        plan = self._make_plan()
        stats = {"score": 9.0, "percentage": 90.0}
        plan.set_stats(stats)
        assert plan.stats_json == stats
        assert plan.updated_at is not None

    # -- set_summary -------------------------------------------------------

    def test_set_summary_with_strengths(self):
        """set_summary should store both summary and strengths."""
        plan = self._make_plan()
        plan.set_summary("Resumo geral", strengths="Pontos fortes")
        assert plan.summary_text == "Resumo geral"
        assert plan.strengths_text == "Pontos fortes"

    def test_set_summary_without_strengths(self):
        """set_summary without strengths should leave strengths unchanged."""
        plan = self._make_plan()
        plan.set_summary("Resumo apenas")
        assert plan.summary_text == "Resumo apenas"
        assert plan.strengths_text is None

    # -- set_pdf_url -------------------------------------------------------

    def test_set_pdf_url_stores_url(self):
        """set_pdf_url should store URL and mark entity updated."""
        plan = self._make_plan()
        plan.set_pdf_url("https://cdn.example.com/file.pdf")
        assert plan.final_pdf_url == "https://cdn.example.com/file.pdf"
        assert plan.updated_at is not None

    # -- calculate_stats ---------------------------------------------------

    def test_calculate_stats_empty_plan(self):
        """calculate_stats should return empty dict for plan with no items."""
        plan = self._make_plan()
        stats = plan.calculate_stats()
        assert stats == {}

    def test_calculate_stats_basic(self):
        """calculate_stats should compute totals, by_severity, by_sector."""
        plan = self._make_plan()
        plan.add_item(self._make_item(
            sector="Cozinha",
            severity=SeverityLevel.HIGH,
            original_score=3.0,
        ))
        item2 = self._make_item(
            problem_description="P2",
            sector="Cozinha",
            severity=SeverityLevel.HIGH,
            original_score=4.0,
        )
        plan.add_item(item2)
        item2.resolve()
        plan.add_item(self._make_item(
            problem_description="P3",
            severity=SeverityLevel.MEDIUM,
        ))

        stats = plan.calculate_stats()
        assert stats["total_items"] == 3
        assert stats["resolved_items"] == 1
        assert stats["resolution_percentage"] == pytest.approx(100 / 3)
        assert "HIGH" in stats["by_severity"]
        assert stats["by_severity"]["HIGH"]["total"] == 2
        assert stats["by_severity"]["HIGH"]["resolved"] == 1
        assert "Cozinha" in stats["by_sector"]
        assert stats["by_sector"]["Cozinha"]["avg_score"] == pytest.approx(3.5)
        # Item without sector goes to "Geral"
        assert "Geral" in stats["by_sector"]
        assert stats["by_sector"]["Geral"]["avg_score"] is None

    def test_calculate_stats_sets_stats_json(self):
        """calculate_stats should also set stats_json on the plan."""
        plan = self._make_plan()
        plan.add_item(self._make_item())
        stats = plan.calculate_stats()
        assert plan.stats_json is stats

    # -- __str__ -----------------------------------------------------------

    def test_str_pending(self):
        """__str__ should show 'Pendente' when plan is not approved."""
        plan = self._make_plan()
        text = str(plan)
        assert "Pendente" in text
        assert "0 itens" in text

    def test_str_approved(self):
        """__str__ should show 'Aprovado' when plan is approved."""
        plan = self._make_plan()
        plan.approve(uuid4())
        text = str(plan)
        assert "Aprovado" in text


# ---------------------------------------------------------------------------
# Contact
# ---------------------------------------------------------------------------

class TestContactEntity:
    """Tests for Contact dataclass."""

    def test_create_contact_basic(self):
        """Should create a contact with name and phone."""
        c = Contact(name="Joao Silva", phone=Phone("11999998888"))
        assert c.name == "Joao Silva"
        assert c.is_active is True

    def test_contact_strips_name(self):
        """Contact should strip whitespace from name."""
        c = Contact(name="  Joao Silva  ", phone=Phone("11999998888"))
        assert c.name == "Joao Silva"

    def test_contact_empty_name_raises_validation_error(self):
        """Contact with empty name should raise ValidationError."""
        with pytest.raises(ValidationError):
            Contact(name="", phone=Phone("11999998888"))

    def test_contact_whitespace_name_raises_validation_error(self):
        """Contact with whitespace-only name should raise ValidationError."""
        with pytest.raises(ValidationError):
            Contact(name="   ", phone=Phone("11999998888"))

    def test_contact_with_email_and_role(self):
        """Contact can have optional email and role."""
        c = Contact(
            name="Maria",
            phone=Phone("11999998888"),
            email=Email("maria@test.com"),
            role="Gerente",
        )
        assert str(c.email) == "maria@test.com"
        assert c.role == "Gerente"


# ---------------------------------------------------------------------------
# Establishment (extra methods)
# ---------------------------------------------------------------------------

class TestEstablishmentExtra:
    """Tests for Establishment methods/properties not covered elsewhere."""

    def _make_est(self, **kwargs):
        defaults = dict(name="Loja Teste", company_id=uuid4())
        defaults.update(kwargs)
        return Establishment.create(**defaults)

    # -- has_drive_folder / has_responsible ---------------------------------

    def test_has_drive_folder_false(self):
        est = self._make_est()
        assert est.has_drive_folder is False

    def test_has_drive_folder_true(self):
        est = self._make_est()
        est.set_drive_folder("folder-abc")
        assert est.has_drive_folder is True

    def test_has_responsible_false(self):
        est = self._make_est()
        assert est.has_responsible is False

    def test_has_responsible_true(self):
        est = self._make_est(responsible_name="Carlos")
        assert est.has_responsible is True

    # -- contacts / active_contacts ----------------------------------------

    def test_contacts_returns_copy(self):
        """contacts property should return a copy of the internal list."""
        est = self._make_est()
        contact = Contact(name="A", phone=Phone("11999998888"))
        est.add_contact(contact)
        contacts = est.contacts
        contacts.clear()
        assert len(est.contacts) == 1  # internal list unchanged

    def test_active_contacts_filters_inactive(self):
        """active_contacts should exclude inactive contacts."""
        est = self._make_est()
        c1 = Contact(name="Ativo", phone=Phone("11999998888"))
        c2 = Contact(name="Inativo", phone=Phone("11988887777"), is_active=False)
        est.add_contact(c1)
        est.add_contact(c2)
        active = est.active_contacts
        assert len(active) == 1
        assert active[0].name == "Ativo"

    # -- consultant_ids ----------------------------------------------------

    def test_consultant_ids_returns_copy(self):
        """consultant_ids property should return a copy."""
        est = self._make_est()
        cid = uuid4()
        est.assign_consultant(cid)
        ids = est.consultant_ids
        ids.clear()
        assert len(est.consultant_ids) == 1

    # -- set_drive_folder --------------------------------------------------

    def test_set_drive_folder_raises_on_empty(self):
        """set_drive_folder should raise ValidationError for empty string."""
        est = self._make_est()
        with pytest.raises(ValidationError):
            est.set_drive_folder("")

    # -- add_contact / remove_contact --------------------------------------

    def test_add_and_remove_contact(self):
        est = self._make_est()
        c = Contact(name="Ana", phone=Phone("11999998888"))
        est.add_contact(c)
        assert len(est.contacts) == 1
        est.remove_contact(c)
        assert len(est.contacts) == 0

    def test_remove_contact_not_present(self):
        """Removing a contact not in the list should be a no-op."""
        est = self._make_est()
        c = Contact(name="Fantasma", phone=Phone("11999998888"))
        est.remove_contact(c)  # should not raise
        assert len(est.contacts) == 0

    # -- assign_consultant / remove_consultant -----------------------------

    def test_assign_consultant_idempotent(self):
        """Assigning the same consultant twice should not duplicate."""
        est = self._make_est()
        cid = uuid4()
        est.assign_consultant(cid)
        est.assign_consultant(cid)
        assert len(est.consultant_ids) == 1

    def test_remove_consultant(self):
        est = self._make_est()
        cid = uuid4()
        est.assign_consultant(cid)
        est.remove_consultant(cid)
        assert len(est.consultant_ids) == 0

    def test_remove_consultant_not_present(self):
        """Removing a consultant not assigned should be a no-op."""
        est = self._make_est()
        est.remove_consultant(uuid4())
        assert len(est.consultant_ids) == 0

    # -- deactivate / activate ---------------------------------------------

    def test_deactivate_establishment(self):
        est = self._make_est()
        est.deactivate()
        assert est.is_active is False

    def test_deactivate_already_inactive_raises(self):
        est = self._make_est()
        est.deactivate()
        with pytest.raises(BusinessRuleViolationError):
            est.deactivate()

    def test_activate_inactive_establishment(self):
        est = self._make_est()
        est.deactivate()
        est.activate()
        assert est.is_active is True

    def test_activate_already_active_raises(self):
        est = self._make_est()
        with pytest.raises(BusinessRuleViolationError):
            est.activate()

    # -- update_info -------------------------------------------------------

    def test_update_info_name(self):
        est = self._make_est()
        est.update_info(name="  Nova Loja  ")
        assert est.name == "Nova Loja"

    def test_update_info_empty_name_raises(self):
        est = self._make_est()
        with pytest.raises(ValidationError):
            est.update_info(name="  ")

    def test_update_info_code(self):
        est = self._make_est()
        est.update_info(code="loja01")
        assert est.code == "LOJA01"

    def test_update_info_code_empty_sets_none(self):
        est = self._make_est(code="ABC")
        est.update_info(code="")
        assert est.code is None

    # -- __str__ -----------------------------------------------------------

    def test_str_with_code(self):
        est = self._make_est(code="L01")
        text = str(est)
        assert "Establishment(" in text
        assert "L01" in text

    def test_str_without_code(self):
        est = self._make_est()
        text = str(est)
        assert "Establishment(Loja Teste)" == text


# ---------------------------------------------------------------------------
# Company (extra methods)
# ---------------------------------------------------------------------------

class TestCompanyExtra:
    """Tests for Company methods/properties not covered elsewhere."""

    def _make_company(self, **kwargs):
        defaults = dict(name="Empresa Teste")
        defaults.update(kwargs)
        return Company.create(**defaults)

    # -- has_drive_folder --------------------------------------------------

    def test_has_drive_folder_false(self):
        co = self._make_company()
        assert co.has_drive_folder is False

    def test_has_drive_folder_true(self):
        co = self._make_company()
        co.set_drive_folder("folder-xyz")
        assert co.has_drive_folder is True

    # -- set_drive_folder --------------------------------------------------

    def test_set_drive_folder_raises_on_empty(self):
        co = self._make_company()
        with pytest.raises(ValidationError):
            co.set_drive_folder("")

    # -- activate ----------------------------------------------------------

    def test_activate_inactive_company(self):
        co = self._make_company()
        co.deactivate()
        co.activate()
        assert co.is_active is True

    def test_activate_already_active_raises(self):
        co = self._make_company()
        with pytest.raises(BusinessRuleViolationError):
            co.activate()

    # -- update_info -------------------------------------------------------

    def test_update_info_name(self):
        co = self._make_company()
        co.update_info(name="  Novo Nome  ")
        assert co.name == "Novo Nome"

    def test_update_info_empty_name_raises(self):
        co = self._make_company()
        with pytest.raises(ValidationError):
            co.update_info(name="  ")

    def test_update_info_cnpj(self):
        co = self._make_company()
        co.update_info(cnpj="12.345.678/0001-90")
        assert co.cnpj == "12345678000190"

    def test_update_info_clear_cnpj(self):
        co = self._make_company(cnpj="12345678000190")
        co.update_info(cnpj="")
        assert co.cnpj is None

    # -- can_be_deleted ----------------------------------------------------

    def test_can_be_deleted_true_when_counts_zero(self):
        co = self._make_company()
        assert co.can_be_deleted() is True

    def test_can_be_deleted_false_with_establishments(self):
        co = self._make_company()
        co._establishment_count = 1
        assert co.can_be_deleted() is False

    def test_can_be_deleted_false_with_users(self):
        co = self._make_company()
        co._user_count = 3
        assert co.can_be_deleted() is False

    # -- __str__ -----------------------------------------------------------

    def test_str_active(self):
        co = self._make_company()
        assert str(co) == "Company(Empresa Teste, Ativa)"

    def test_str_inactive(self):
        co = self._make_company()
        co.deactivate()
        assert str(co) == "Company(Empresa Teste, Inativa)"


# ---------------------------------------------------------------------------
# UserRole (extra)
# ---------------------------------------------------------------------------

class TestUserRoleExtra:
    """Tests for UserRole properties not covered elsewhere."""

    def test_label_pt_consultant(self):
        assert UserRole.CONSULTANT.label_pt == "Consultor"

    def test_label_pt_manager(self):
        assert UserRole.MANAGER.label_pt == "Gestor"

    def test_label_pt_admin(self):
        assert UserRole.ADMIN.label_pt == "Administrador"

    def test_can_manage_users_manager(self):
        assert UserRole.MANAGER.can_manage_users is True

    def test_can_manage_users_admin(self):
        assert UserRole.ADMIN.can_manage_users is True

    def test_can_manage_users_consultant(self):
        assert UserRole.CONSULTANT.can_manage_users is False


# ---------------------------------------------------------------------------
# User (extra methods)
# ---------------------------------------------------------------------------

class TestUserExtra:
    """Tests for User methods/properties not covered elsewhere."""

    def _consultant(self, **kwargs):
        return User.create_consultant(
            email=kwargs.pop("email", "c@test.com"),
            name=kwargs.pop("name", "Consultor"),
            company_id=kwargs.pop("company_id", uuid4()),
            **kwargs,
        )

    # -- activate ----------------------------------------------------------

    def test_activate_inactive_user(self):
        user = self._consultant()
        user.deactivate()
        user.activate()
        assert user.is_active is True

    def test_activate_already_active_raises(self):
        user = self._consultant()
        with pytest.raises(BusinessRuleViolationError):
            user.activate()

    # -- require_password_change -------------------------------------------

    def test_require_password_change(self):
        user = self._consultant()
        user.password_changed()
        assert user.must_change_password is False
        user.require_password_change()
        assert user.must_change_password is True
        assert user.updated_at is not None

    # -- can_access_establishment ------------------------------------------

    def test_admin_can_access_any_establishment(self):
        admin = User.create_admin("a@test.com", "Admin")
        assert admin.can_access_establishment(uuid4()) is True

    def test_consultant_can_access_assigned_establishment(self):
        est_id = uuid4()
        user = self._consultant(establishment_ids=[est_id])
        assert user.can_access_establishment(est_id) is True

    def test_consultant_cannot_access_unassigned_establishment(self):
        user = self._consultant()
        assert user.can_access_establishment(uuid4()) is False

    # -- assign_establishment ----------------------------------------------

    def test_assign_establishment_to_consultant(self):
        user = self._consultant()
        est_id = uuid4()
        user.assign_establishment(est_id)
        assert est_id in user._establishment_ids

    def test_assign_establishment_idempotent(self):
        user = self._consultant()
        est_id = uuid4()
        user.assign_establishment(est_id)
        user.assign_establishment(est_id)
        assert user._establishment_ids.count(est_id) == 1

    def test_assign_establishment_non_consultant_raises(self):
        manager = User.create_manager("m@test.com", "Mgr", uuid4())
        with pytest.raises(BusinessRuleViolationError):
            manager.assign_establishment(uuid4())

    # -- remove_establishment ----------------------------------------------

    def test_remove_establishment(self):
        est_id = uuid4()
        user = self._consultant(establishment_ids=[est_id])
        user.remove_establishment(est_id)
        assert est_id not in user._establishment_ids

    def test_remove_establishment_not_assigned(self):
        """Removing an unassigned establishment should be a no-op."""
        user = self._consultant()
        user.remove_establishment(uuid4())  # should not raise

    # -- change_role -------------------------------------------------------

    def test_change_role_consultant_to_manager_clears_establishments(self):
        est_id = uuid4()
        user = self._consultant(establishment_ids=[est_id])
        user.change_role(UserRole.MANAGER)
        assert user.role == UserRole.MANAGER
        assert user._establishment_ids == []

    def test_change_role_same_role_is_noop(self):
        user = self._consultant()
        old_updated = user.updated_at
        user.change_role(UserRole.CONSULTANT)
        assert user.updated_at == old_updated

    def test_change_role_manager_to_admin_keeps_empty_establishments(self):
        user = User.create_manager("m@test.com", "Mgr", uuid4())
        user.change_role(UserRole.ADMIN)
        assert user.role == UserRole.ADMIN

    # -- __str__ -----------------------------------------------------------

    def test_str_consultant(self):
        user = self._consultant(name="Joao")
        text = str(user)
        assert "Joao" in text
        assert "Consultor" in text

    def test_str_admin(self):
        user = User.create_admin("a@test.com", "Admin User")
        text = str(user)
        assert "Admin User" in text
        assert "Administrador" in text
