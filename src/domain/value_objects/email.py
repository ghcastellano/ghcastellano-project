"""
Email Value Object - Immutable email with validation.
"""

import re
from dataclasses import dataclass
from ..exceptions import ValidationError


@dataclass(frozen=True)
class Email:
    """
    Immutable email value object with validation.

    Usage:
        email = Email("user@example.com")
        print(email.value)  # "user@example.com"
        print(email.domain)  # "example.com"
    """

    value: str

    # RFC 5322 simplified pattern
    EMAIL_PATTERN = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    )

    def __post_init__(self):
        if not self.value:
            raise ValidationError("Email é obrigatório", "email")

        normalized = self.value.strip().lower()

        if not self.EMAIL_PATTERN.match(normalized):
            raise ValidationError(f"Email inválido: {self.value}", "email")

        # Use object.__setattr__ because dataclass is frozen
        object.__setattr__(self, 'value', normalized)

    @property
    def domain(self) -> str:
        """Extract domain from email."""
        return self.value.split('@')[1]

    @property
    def local_part(self) -> str:
        """Extract local part (before @) from email."""
        return self.value.split('@')[0]

    def __str__(self) -> str:
        return self.value

    def __eq__(self, other) -> bool:
        if isinstance(other, Email):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other.lower().strip()
        return False

    def __hash__(self) -> int:
        return hash(self.value)
