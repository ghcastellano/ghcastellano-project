"""
Phone Value Object - Immutable phone number with validation.
"""

import re
from dataclasses import dataclass
from typing import Optional
from ..exceptions import ValidationError


@dataclass(frozen=True)
class Phone:
    """
    Immutable phone number value object with Brazilian format validation.

    Supports formats:
        - 11999999999 (11 digits with DDD)
        - 5511999999999 (13 digits with country code)
        - (11) 99999-9999
        - +55 11 99999-9999

    Usage:
        phone = Phone("11999999999")
        print(phone.value)       # "11999999999"
        print(phone.formatted)   # "(11) 99999-9999"
        print(phone.whatsapp)    # "5511999999999"
    """

    value: str

    def __post_init__(self):
        if not self.value:
            raise ValidationError("Telefone é obrigatório", "phone")

        # Remove all non-digits
        digits = re.sub(r'\D', '', self.value)

        # Validate length
        if len(digits) < 10 or len(digits) > 13:
            raise ValidationError(
                f"Telefone inválido: {self.value}. Use formato: 11999999999",
                "phone"
            )

        # Normalize to 11 digits (DDD + number) if has country code
        if len(digits) == 13 and digits.startswith('55'):
            digits = digits[2:]  # Remove country code
        elif len(digits) == 12 and digits.startswith('55'):
            digits = digits[2:]

        # Validate DDD (Brazilian area codes are 11-99)
        ddd = int(digits[:2])
        if ddd < 11 or ddd > 99:
            raise ValidationError(f"DDD inválido: {ddd}", "phone")

        object.__setattr__(self, 'value', digits)

    @property
    def ddd(self) -> str:
        """Extract DDD (area code)."""
        return self.value[:2]

    @property
    def number(self) -> str:
        """Extract number without DDD."""
        return self.value[2:]

    @property
    def formatted(self) -> str:
        """Format as (XX) XXXXX-XXXX."""
        if len(self.value) == 11:
            return f"({self.value[:2]}) {self.value[2:7]}-{self.value[7:]}"
        else:  # 10 digits (landline)
            return f"({self.value[:2]}) {self.value[2:6]}-{self.value[6:]}"

    @property
    def whatsapp(self) -> str:
        """Format for WhatsApp API (with country code)."""
        return f"55{self.value}"

    @property
    def is_mobile(self) -> bool:
        """Check if it's a mobile number (starts with 9 after DDD)."""
        return len(self.value) == 11 and self.value[2] == '9'

    def __str__(self) -> str:
        return self.formatted

    def __eq__(self, other) -> bool:
        if isinstance(other, Phone):
            return self.value == other.value
        if isinstance(other, str):
            other_digits = re.sub(r'\D', '', other)
            if len(other_digits) == 13 and other_digits.startswith('55'):
                other_digits = other_digits[2:]
            return self.value == other_digits
        return False

    def __hash__(self) -> int:
        return hash(self.value)

    @classmethod
    def from_string(cls, value: str) -> Optional['Phone']:
        """Create Phone from string, returns None if invalid."""
        if not value:
            return None
        try:
            return cls(value)
        except ValidationError:
            return None
