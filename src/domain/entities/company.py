"""
Company Entity - Represents a client company.
"""

from dataclasses import dataclass, field
from typing import Optional, List
from uuid import UUID

from .base import Entity
from ..exceptions import ValidationError, BusinessRuleViolationError


@dataclass
class Company(Entity):
    """
    Company entity representing a client organization.

    Companies have establishments (stores/units) and users.
    Each company has a dedicated folder in Google Drive.
    """
    name: str = ""
    cnpj: Optional[str] = None
    is_active: bool = True
    drive_folder_id: Optional[str] = None

    # Not persisted - for domain operations
    _establishment_count: int = 0
    _user_count: int = 0

    def __post_init__(self):
        if not self.name or not self.name.strip():
            raise ValidationError("Nome da empresa é obrigatório", "name")
        self.name = self.name.strip()

        if self.cnpj:
            self.cnpj = self._normalize_cnpj(self.cnpj)

    @staticmethod
    def _normalize_cnpj(cnpj: str) -> str:
        """Remove formatting from CNPJ, keeping only digits."""
        return ''.join(filter(str.isdigit, cnpj))

    @staticmethod
    def _format_cnpj(cnpj: str) -> str:
        """Format CNPJ with standard Brazilian formatting."""
        if not cnpj or len(cnpj) != 14:
            return cnpj or ""
        return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"

    @classmethod
    def create(cls, name: str, cnpj: Optional[str] = None) -> 'Company':
        """Factory method to create a new company."""
        return cls(name=name, cnpj=cnpj)

    @property
    def cnpj_formatted(self) -> str:
        """Get CNPJ with standard formatting."""
        return self._format_cnpj(self.cnpj) if self.cnpj else ""

    @property
    def has_drive_folder(self) -> bool:
        """Check if company has a Drive folder configured."""
        return bool(self.drive_folder_id)

    def set_drive_folder(self, folder_id: str) -> None:
        """Set the Drive folder ID."""
        if not folder_id:
            raise ValidationError("ID da pasta do Drive não pode ser vazio", "drive_folder_id")
        self.drive_folder_id = folder_id
        self.mark_updated()

    def deactivate(self) -> None:
        """Deactivate the company."""
        if not self.is_active:
            raise BusinessRuleViolationError("Empresa já está inativa")
        self.is_active = False
        self.mark_updated()

    def activate(self) -> None:
        """Activate the company."""
        if self.is_active:
            raise BusinessRuleViolationError("Empresa já está ativa")
        self.is_active = True
        self.mark_updated()

    def update_info(self, name: Optional[str] = None, cnpj: Optional[str] = None) -> None:
        """Update company information."""
        if name is not None:
            if not name.strip():
                raise ValidationError("Nome da empresa não pode ser vazio", "name")
            self.name = name.strip()

        if cnpj is not None:
            self.cnpj = self._normalize_cnpj(cnpj) if cnpj else None

        self.mark_updated()

    def can_be_deleted(self) -> bool:
        """Check if company can be safely deleted."""
        return self._establishment_count == 0 and self._user_count == 0

    def __str__(self) -> str:
        status = "Ativa" if self.is_active else "Inativa"
        return f"Company({self.name}, {status})"
