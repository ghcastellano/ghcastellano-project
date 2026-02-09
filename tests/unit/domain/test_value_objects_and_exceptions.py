"""
Tests for domain value objects and exceptions - covering uncovered lines.
"""

import pytest
from dataclasses import dataclass
from uuid import uuid4

from src.domain import (
    ValidationError,
    NotFoundError,
    UnauthorizedError,
    BusinessRuleViolationError,
    InvalidStatusTransitionError,
    Email,
    Phone,
    SeverityLevel,
    Inspection,
    InspectionStatus,
)
from src.domain.exceptions import (
    InspectionNotFoundError,
    EstablishmentNotFoundError,
    UserNotFoundError,
    CompanyNotFoundError,
    ActionPlanNotFoundError,
    InspectionAlreadyProcessedError,
    DuplicateFileError,
)
from src.domain.value_objects.score import Score
from src.domain.entities.base import Entity


# Concrete subclass for testing the abstract Entity base class.
# Use eq=False so the dataclass decorator does not generate __eq__/__hash__,
# allowing Entity's __eq__ and __hash__ (based on id) to be inherited.
@dataclass(eq=False)
class ConcreteEntity(Entity):
    name: str = "test"


# ============================================================================
# Domain Exceptions
# ============================================================================


class TestNotFoundError:

    def test_without_identifier(self):
        err = NotFoundError("Item")
        assert err.message == "Item não encontrado"
        assert err.entity_type == "Item"
        assert err.identifier is None
        assert err.code == "ITEM_NOT_FOUND"

    def test_with_identifier(self):
        err = NotFoundError("Item", "abc-123")
        assert err.message == "Item 'abc-123' não encontrado"
        assert err.entity_type == "Item"
        assert err.identifier == "abc-123"
        assert err.code == "ITEM_NOT_FOUND"


class TestUnauthorizedError:

    def test_default_message(self):
        err = UnauthorizedError()
        assert err.message == "Acesso não autorizado"
        assert err.code == "UNAUTHORIZED"

    def test_custom_message(self):
        err = UnauthorizedError("Custom message")
        assert err.message == "Custom message"
        assert err.code == "UNAUTHORIZED"


class TestInspectionNotFoundError:

    def test_without_id(self):
        err = InspectionNotFoundError()
        assert err.message == "Inspeção não encontrado"
        assert err.entity_type == "Inspeção"
        assert err.code == "INSPEÇÃO_NOT_FOUND"

    def test_with_id(self):
        err = InspectionNotFoundError("insp-1")
        assert err.message == "Inspeção 'insp-1' não encontrado"
        assert err.entity_type == "Inspeção"


class TestEstablishmentNotFoundError:

    def test_without_id(self):
        err = EstablishmentNotFoundError()
        assert err.message == "Estabelecimento não encontrado"
        assert err.entity_type == "Estabelecimento"

    def test_with_id(self):
        err = EstablishmentNotFoundError("est-1")
        assert err.message == "Estabelecimento 'est-1' não encontrado"


class TestUserNotFoundError:

    def test_without_id(self):
        err = UserNotFoundError()
        assert err.message == "Usuário não encontrado"
        assert err.entity_type == "Usuário"

    def test_with_id(self):
        err = UserNotFoundError("user-1")
        assert err.message == "Usuário 'user-1' não encontrado"


class TestCompanyNotFoundError:

    def test_without_id(self):
        err = CompanyNotFoundError()
        assert err.message == "Empresa não encontrado"
        assert err.entity_type == "Empresa"

    def test_with_id(self):
        err = CompanyNotFoundError("comp-1")
        assert err.message == "Empresa 'comp-1' não encontrado"


class TestActionPlanNotFoundError:

    def test_without_id(self):
        err = ActionPlanNotFoundError()
        assert err.message == "Plano de Ação não encontrado"
        assert err.entity_type == "Plano de Ação"

    def test_with_id(self):
        err = ActionPlanNotFoundError("plan-1")
        assert err.message == "Plano de Ação 'plan-1' não encontrado"


class TestInspectionAlreadyProcessedError:

    def test_with_inspection_id(self):
        err = InspectionAlreadyProcessedError("insp-42")
        assert err.inspection_id == "insp-42"
        assert err.message == "Inspeção 'insp-42' já foi processada"
        assert err.rule == "ALREADY_PROCESSED"
        assert err.code == "BUSINESS_RULE_ALREADY_PROCESSED"

    def test_is_business_rule_violation(self):
        err = InspectionAlreadyProcessedError("x")
        assert isinstance(err, BusinessRuleViolationError)


class TestDuplicateFileError:

    def test_with_file_hash(self):
        err = DuplicateFileError("sha256-abc")
        assert err.file_hash == "sha256-abc"
        assert err.message == "Este arquivo já foi enviado anteriormente"
        assert err.rule == "DUPLICATE_FILE"
        assert err.code == "BUSINESS_RULE_DUPLICATE_FILE"

    def test_is_business_rule_violation(self):
        err = DuplicateFileError("hash")
        assert isinstance(err, BusinessRuleViolationError)


# ============================================================================
# Phone Value Object
# ============================================================================


class TestPhone:

    def test_empty_phone_raises_validation_error(self):
        with pytest.raises(ValidationError, match="Telefone é obrigatório"):
            Phone("")

    def test_none_phone_raises_validation_error(self):
        with pytest.raises(ValidationError):
            Phone(None)

    def test_12_digit_phone_with_country_code_55_normalization(self):
        # 12 digits: 55 + 10-digit number (landline)
        phone = Phone("551199999999")
        assert phone.value == "1199999999"

    def test_13_digit_phone_with_country_code_55_normalization(self):
        # 13 digits: 55 + 11-digit number (mobile)
        phone = Phone("5511999999999")
        assert phone.value == "11999999999"

    def test_invalid_ddd_below_11_raises_validation_error(self):
        with pytest.raises(ValidationError, match="DDD inválido"):
            Phone("0099999999")

    def test_invalid_ddd_with_leading_zeros(self):
        with pytest.raises(ValidationError, match="DDD inválido"):
            Phone("0199999999")

    def test_ddd_property_returns_first_two_digits(self):
        phone = Phone("11999999999")
        assert phone.ddd == "11"

    def test_number_property_returns_digits_after_ddd(self):
        phone = Phone("11999999999")
        assert phone.number == "999999999"

    def test_str_returns_formatted(self):
        phone = Phone("11999999999")
        result = str(phone)
        assert result == "(11) 99999-9999"

    def test_str_landline_format(self):
        phone = Phone("1133334444")
        result = str(phone)
        assert result == "(11) 3333-4444"

    def test_eq_with_string_matching_digits(self):
        phone = Phone("11999999999")
        assert phone == "11999999999"

    def test_eq_with_string_with_country_code_prefix(self):
        phone = Phone("11999999999")
        assert phone == "5511999999999"

    def test_eq_with_non_phone_non_str_returns_false(self):
        phone = Phone("11999999999")
        assert phone != 12345
        assert phone != None
        assert phone != ["11999999999"]

    def test_hash_works_in_set(self):
        phone1 = Phone("11999999999")
        phone2 = Phone("11999999999")
        phone_set = {phone1, phone2}
        assert len(phone_set) == 1

    def test_hash_different_phones(self):
        phone1 = Phone("11999999999")
        phone2 = Phone("21888888888")
        assert hash(phone1) != hash(phone2)

    def test_from_string_with_empty_string_returns_none(self):
        result = Phone.from_string("")
        assert result is None

    def test_from_string_with_none_returns_none(self):
        result = Phone.from_string(None)
        assert result is None

    def test_from_string_with_valid_string_returns_phone(self):
        result = Phone.from_string("11999999999")
        assert isinstance(result, Phone)
        assert result.value == "11999999999"

    def test_from_string_with_invalid_string_returns_none(self):
        result = Phone.from_string("invalid")
        assert result is None

    def test_from_string_with_invalid_ddd_returns_none(self):
        result = Phone.from_string("0099999999")
        assert result is None


# ============================================================================
# Score Value Object
# ============================================================================


class TestScore:

    def test_status_normalized_compliant(self):
        score = Score(9.0, "Conforme")
        assert score.status_normalized == "Conforme"

    def test_status_normalized_compliant_by_score(self):
        score = Score(8.0)
        assert score.status_normalized == "Conforme"

    def test_status_normalized_partial(self):
        score = Score(5.0, "Parcialmente Conforme")
        assert score.status_normalized == "Parcialmente Conforme"

    def test_status_normalized_partial_lowercase(self):
        score = Score(4.0, "parcial adequação")
        assert score.status_normalized == "Parcialmente Conforme"

    def test_status_normalized_non_compliant(self):
        score = Score(3.0, "Não Conforme")
        assert score.status_normalized == "Não Conforme"

    def test_status_normalized_non_compliant_by_score(self):
        score = Score(4.0)
        assert score.status_normalized == "Não Conforme"

    def test_eq_with_another_score(self):
        score1 = Score(7.5)
        score2 = Score(7.5)
        assert score1 == score2

    def test_eq_with_different_score(self):
        score1 = Score(7.5)
        score2 = Score(8.0)
        assert score1 != score2

    def test_eq_with_int(self):
        score = Score(7.0)
        assert score == 7

    def test_eq_with_float(self):
        score = Score(7.5)
        assert score == 7.5

    def test_eq_with_non_number_returns_false(self):
        score = Score(7.0)
        assert score != "7.0"
        assert score != None
        assert score != [7.0]

    def test_lt_with_score(self):
        score1 = Score(5.0)
        score2 = Score(8.0)
        assert score1 < score2
        assert not score2 < score1

    def test_lt_with_int(self):
        score = Score(5.0)
        assert score < 8
        assert not score < 3

    def test_lt_with_float(self):
        score = Score(5.0)
        assert score < 8.0
        assert not score < 3.0

    def test_lt_with_incompatible_type_returns_not_implemented(self):
        score = Score(5.0)
        result = score.__lt__("not a number")
        assert result is NotImplemented

    def test_hash_works(self):
        score1 = Score(7.5)
        score2 = Score(7.5)
        score_set = {score1, score2}
        assert len(score_set) == 1
        assert hash(score1) == hash(score2)

    def test_hash_different_scores(self):
        score1 = Score(7.5)
        score2 = Score(8.0)
        assert hash(score1) != hash(score2)


# ============================================================================
# Email Value Object
# ============================================================================


class TestEmail:

    def test_eq_with_another_email(self):
        email1 = Email("user@example.com")
        email2 = Email("user@example.com")
        assert email1 == email2

    def test_eq_with_different_email(self):
        email1 = Email("user@example.com")
        email2 = Email("other@example.com")
        assert email1 != email2

    def test_eq_with_string_case_insensitive(self):
        email = Email("user@example.com")
        assert email == "USER@EXAMPLE.COM"
        assert email == "User@Example.Com"
        assert email == "user@example.com"

    def test_eq_with_string_with_whitespace(self):
        email = Email("user@example.com")
        assert email == "  user@example.com  "

    def test_eq_with_non_email_non_str_returns_false(self):
        email = Email("user@example.com")
        assert email != 12345
        assert email != None
        assert email != ["user@example.com"]

    def test_hash_works(self):
        email1 = Email("user@example.com")
        email2 = Email("user@example.com")
        email_set = {email1, email2}
        assert len(email_set) == 1
        assert hash(email1) == hash(email2)

    def test_hash_different_emails(self):
        email1 = Email("user@example.com")
        email2 = Email("other@example.com")
        assert hash(email1) != hash(email2)


# ============================================================================
# InspectionStatus Enum
# ============================================================================


class TestInspectionStatus:

    def test_label_pt_processing(self):
        assert InspectionStatus.PROCESSING.label_pt == "Processando"

    def test_label_pt_pending_manager_review(self):
        assert InspectionStatus.PENDING_MANAGER_REVIEW.label_pt == "Aguardando Revisão"

    def test_label_pt_approved(self):
        assert InspectionStatus.APPROVED.label_pt == "Aprovado"

    def test_label_pt_pending_consultant_verification(self):
        assert InspectionStatus.PENDING_CONSULTANT_VERIFICATION.label_pt == "Aguardando Verificação"

    def test_label_pt_completed(self):
        assert InspectionStatus.COMPLETED.label_pt == "Concluído"

    def test_label_pt_rejected(self):
        assert InspectionStatus.REJECTED.label_pt == "Rejeitado"


# ============================================================================
# Inspection Entity
# ============================================================================


class TestInspection:

    def _make_inspection(self, status=InspectionStatus.PROCESSING, file_hash=None):
        """Helper to create an Inspection with required fields."""
        return Inspection(
            drive_file_id="abc12345xyz",
            establishment_id=uuid4(),
            status=status,
            file_hash=file_hash,
        )

    def test_is_rejected_true(self):
        insp = self._make_inspection(status=InspectionStatus.REJECTED)
        assert insp.is_rejected is True

    def test_is_rejected_false(self):
        insp = self._make_inspection(status=InspectionStatus.PROCESSING)
        assert insp.is_rejected is False

    def test_can_be_edited_when_pending_review(self):
        insp = self._make_inspection(status=InspectionStatus.PENDING_MANAGER_REVIEW)
        assert insp.can_be_edited is True

    def test_can_be_edited_when_approved(self):
        insp = self._make_inspection(status=InspectionStatus.APPROVED)
        assert insp.can_be_edited is True

    def test_can_be_edited_when_processing(self):
        insp = self._make_inspection(status=InspectionStatus.PROCESSING)
        assert insp.can_be_edited is False

    def test_is_terminal_when_completed(self):
        insp = self._make_inspection(status=InspectionStatus.COMPLETED)
        assert insp.is_terminal is True

    def test_is_terminal_when_rejected(self):
        insp = self._make_inspection(status=InspectionStatus.REJECTED)
        assert insp.is_terminal is True

    def test_is_terminal_when_processing(self):
        insp = self._make_inspection(status=InspectionStatus.PROCESSING)
        assert insp.is_terminal is False

    def test_transition_to_valid(self):
        insp = self._make_inspection(status=InspectionStatus.PROCESSING)
        insp.transition_to(InspectionStatus.PENDING_MANAGER_REVIEW)
        assert insp.status == InspectionStatus.PENDING_MANAGER_REVIEW
        assert insp.updated_at is not None

    def test_transition_to_invalid_raises(self):
        insp = self._make_inspection(status=InspectionStatus.PROCESSING)
        with pytest.raises(InvalidStatusTransitionError):
            insp.transition_to(InspectionStatus.COMPLETED)

    def test_reject_from_processing(self):
        insp = self._make_inspection(status=InspectionStatus.PROCESSING)
        insp.reject()
        assert insp.status == InspectionStatus.REJECTED
        assert insp.updated_at is not None

    def test_reject_from_pending_manager_review(self):
        insp = self._make_inspection(status=InspectionStatus.PENDING_MANAGER_REVIEW)
        insp.reject()
        assert insp.status == InspectionStatus.REJECTED

    def test_reject_from_approved_raises(self):
        insp = self._make_inspection(status=InspectionStatus.APPROVED)
        with pytest.raises(InvalidStatusTransitionError):
            insp.reject()

    def test_send_for_verification_from_approved(self):
        insp = self._make_inspection(status=InspectionStatus.APPROVED)
        insp.send_for_verification()
        assert insp.status == InspectionStatus.PENDING_CONSULTANT_VERIFICATION
        assert insp.updated_at is not None

    def test_send_for_verification_from_processing_raises(self):
        insp = self._make_inspection(status=InspectionStatus.PROCESSING)
        with pytest.raises(InvalidStatusTransitionError):
            insp.send_for_verification()

    def test_set_ai_response_stores_and_marks_updated(self):
        insp = self._make_inspection()
        response_data = {"items": [{"score": 8}], "summary": "Good"}
        insp.set_ai_response(response_data)
        assert insp.ai_raw_response == response_data
        assert insp.updated_at is not None

    def test_is_duplicate_of_matching_hash(self):
        insp = self._make_inspection(file_hash="sha256abc")
        assert insp.is_duplicate_of("sha256abc") is True

    def test_is_duplicate_of_non_matching_hash(self):
        insp = self._make_inspection(file_hash="sha256abc")
        assert insp.is_duplicate_of("sha256xyz") is False

    def test_is_duplicate_of_no_hash(self):
        insp = self._make_inspection(file_hash=None)
        assert insp.is_duplicate_of("sha256abc") is False

    def test_str_returns_formatted_string(self):
        insp = self._make_inspection(status=InspectionStatus.PROCESSING)
        result = str(insp)
        assert result == "Inspection(abc12345..., Processando)"


# ============================================================================
# Base Entity
# ============================================================================


class TestBaseEntity:

    def test_eq_same_id_returns_true(self):
        shared_id = uuid4()
        entity1 = ConcreteEntity(id=shared_id, name="first")
        entity2 = ConcreteEntity(id=shared_id, name="second")
        assert entity1 == entity2

    def test_eq_different_id_returns_false(self):
        entity1 = ConcreteEntity(id=uuid4(), name="first")
        entity2 = ConcreteEntity(id=uuid4(), name="second")
        assert entity1 != entity2

    def test_eq_with_non_entity_returns_false(self):
        entity = ConcreteEntity(id=uuid4(), name="test")
        assert entity != "not an entity"
        assert entity != 42
        assert entity != None

    def test_hash_based_on_id(self):
        shared_id = uuid4()
        entity1 = ConcreteEntity(id=shared_id, name="first")
        entity2 = ConcreteEntity(id=shared_id, name="second")
        assert hash(entity1) == hash(entity2)

    def test_hash_different_ids(self):
        entity1 = ConcreteEntity(id=uuid4(), name="first")
        entity2 = ConcreteEntity(id=uuid4(), name="second")
        assert hash(entity1) != hash(entity2)

    def test_hash_usable_in_set(self):
        shared_id = uuid4()
        entity1 = ConcreteEntity(id=shared_id, name="first")
        entity2 = ConcreteEntity(id=shared_id, name="second")
        entity_set = {entity1, entity2}
        assert len(entity_set) == 1
