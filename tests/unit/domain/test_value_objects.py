"""Unit tests for domain value objects."""

import pytest
from src.domain import Email, Phone, Score, SeverityLevel, ValidationError


class TestEmail:
    """Tests for Email value object."""

    def test_valid_email(self):
        """Should accept valid email addresses."""
        email = Email("test@example.com")
        assert str(email) == "test@example.com"

    def test_email_normalization(self):
        """Should normalize email to lowercase."""
        email = Email("Test@EXAMPLE.COM")
        assert str(email) == "test@example.com"

    def test_email_strips_whitespace(self):
        """Should strip whitespace from email."""
        email = Email("  test@example.com  ")
        assert str(email) == "test@example.com"

    def test_invalid_email_raises_error(self):
        """Should raise ValidationError for invalid email."""
        with pytest.raises(ValidationError) as exc:
            Email("not-an-email")
        assert "email" in exc.value.field.lower()

    def test_empty_email_raises_error(self):
        """Should raise ValidationError for empty email."""
        with pytest.raises(ValidationError):
            Email("")

    def test_email_equality(self):
        """Emails should be equal if values match."""
        email1 = Email("test@example.com")
        email2 = Email("TEST@example.com")
        assert email1 == email2

    def test_email_domain_extraction(self):
        """Should extract domain from email."""
        email = Email("test@example.com")
        assert email.domain == "example.com"

    def test_email_local_part_extraction(self):
        """Should extract local part from email."""
        email = Email("test@example.com")
        assert email.local_part == "test"


class TestPhone:
    """Tests for Phone value object (Brazilian numbers)."""

    def test_valid_cellphone(self):
        """Should accept valid cellphone number."""
        phone = Phone("11999998888")
        assert phone.value == "11999998888"

    def test_valid_landline(self):
        """Should accept valid landline number."""
        phone = Phone("1133334444")
        assert phone.value == "1133334444"

    def test_formatted_cellphone(self):
        """Should format cellphone correctly."""
        phone = Phone("11999998888")
        assert phone.formatted == "(11) 99999-8888"

    def test_formatted_landline(self):
        """Should format landline correctly."""
        phone = Phone("1133334444")
        assert phone.formatted == "(11) 3333-4444"

    def test_phone_strips_formatting(self):
        """Should strip existing formatting."""
        phone = Phone("(11) 99999-8888")
        assert phone.value == "11999998888"

    def test_phone_with_country_code(self):
        """Should handle phone with country code."""
        phone = Phone("+5511999998888")
        assert phone.value == "11999998888"

    def test_invalid_phone_raises_error(self):
        """Should raise ValidationError for invalid phone."""
        with pytest.raises(ValidationError) as exc:
            Phone("123")
        assert "phone" in exc.value.field.lower() or "telefone" in exc.value.message.lower()

    def test_is_mobile(self):
        """Should correctly identify mobile number."""
        cell = Phone("11999998888")
        land = Phone("1133334444")
        assert cell.is_mobile
        assert not land.is_mobile

    def test_whatsapp_format(self):
        """Should generate correct WhatsApp format."""
        phone = Phone("11999998888")
        assert phone.whatsapp == "5511999998888"


class TestScore:
    """Tests for Score value object."""

    def test_valid_score(self):
        """Should accept valid score."""
        score = Score(7.5)
        assert score.value == 7.5

    def test_score_range_validation(self):
        """Should raise error for out-of-range scores."""
        with pytest.raises(ValidationError):
            Score(11.0)
        with pytest.raises(ValidationError):
            Score(-1.0)

    def test_score_percentage(self):
        """Should calculate percentage correctly."""
        score = Score(7.5)
        assert score.percentage == 75.0

    def test_score_string_representation(self):
        """Should format as X/10."""
        score = Score(7.5)
        assert str(score) == "7.5/10"

    def test_is_compliant_by_score(self):
        """Score >= 7 should be compliant."""
        compliant = Score(7.0)
        non_compliant = Score(6.9)
        assert compliant.is_compliant
        assert not non_compliant.is_compliant

    def test_is_compliant_by_status(self):
        """Status should override score for compliance."""
        score = Score(5.0, "Conforme")
        assert score.is_compliant

    def test_severity_from_score(self):
        """Should determine severity from score."""
        assert Score(9.0).severity == SeverityLevel.LOW
        assert Score(6.0).severity == SeverityLevel.MEDIUM
        assert Score(3.0).severity == SeverityLevel.HIGH
        assert Score(1.0).severity == SeverityLevel.CRITICAL

    def test_perfect_score_factory(self):
        """Should create perfect score."""
        score = Score.perfect()
        assert score.value == 10.0
        assert score.is_compliant

    def test_zero_score_factory(self):
        """Should create zero score."""
        score = Score.zero()
        assert score.value == 0.0
        assert not score.is_compliant

    def test_score_from_percentage(self):
        """Should create score from percentage."""
        score = Score.from_percentage(75.0)
        assert score.value == 7.5


class TestSeverityLevel:
    """Tests for SeverityLevel enum."""

    def test_from_score(self):
        """Should determine severity from score."""
        assert SeverityLevel.from_score(9.0) == SeverityLevel.LOW
        assert SeverityLevel.from_score(6.0) == SeverityLevel.MEDIUM
        assert SeverityLevel.from_score(3.0) == SeverityLevel.HIGH
        assert SeverityLevel.from_score(1.0) == SeverityLevel.CRITICAL

    def test_weight(self):
        """Should have correct weights."""
        assert SeverityLevel.LOW.weight == 1
        assert SeverityLevel.MEDIUM.weight == 2
        assert SeverityLevel.HIGH.weight == 3
        assert SeverityLevel.CRITICAL.weight == 4

    def test_portuguese_labels(self):
        """Should have Portuguese labels."""
        assert SeverityLevel.LOW.label_pt == "Baixa"
        assert SeverityLevel.MEDIUM.label_pt == "Média"
        assert SeverityLevel.HIGH.label_pt == "Alta"
        assert SeverityLevel.CRITICAL.label_pt == "Crítica"
