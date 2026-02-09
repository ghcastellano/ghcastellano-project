"""
Establishment Entity - Represents a store/unit of a company.
"""

from dataclasses import dataclass, field
from typing import Optional, List
from uuid import UUID

from .base import Entity
from ..value_objects import Email, Phone
from ..exceptions import ValidationError, BusinessRuleViolationError


@dataclass
class Contact:
    """Contact information for an establishment."""
    name: str
    phone: Phone
    email: Optional[Email] = None
    role: Optional[str] = None  # Ex: Gerente, Dono
    is_active: bool = True

    def __post_init__(self):
        if not self.name or not self.name.strip():
            raise ValidationError("Nome do contato é obrigatório", "name")
        self.name = self.name.strip()


@dataclass
class Establishment(Entity):
    """
    Establishment entity representing a store/unit of a company.

    Each establishment can have:
    - Multiple consultants assigned
    - Multiple contacts (responsible persons)
    - Its own Drive folder
    - Multiple inspections
    """
    name: str = ""
    company_id: Optional[UUID] = None
    code: Optional[str] = None  # Internal code/identifier
    drive_folder_id: Optional[str] = None
    is_active: bool = True

    # Responsible person info (primary contact)
    responsible_name: Optional[str] = None
    responsible_email: Optional[Email] = None
    responsible_phone: Optional[Phone] = None

    # Not persisted directly - managed through repository
    _contacts: List[Contact] = field(default_factory=list)
    _consultant_ids: List[UUID] = field(default_factory=list)

    def __post_init__(self):
        if not self.name or not self.name.strip():
            raise ValidationError("Nome do estabelecimento é obrigatório", "name")
        self.name = self.name.strip()

        if self.code:
            self.code = self.code.strip().upper()

    @classmethod
    def create(
        cls,
        name: str,
        company_id: UUID,
        code: Optional[str] = None,
        responsible_name: Optional[str] = None,
        responsible_email: Optional[str] = None,
        responsible_phone: Optional[str] = None
    ) -> 'Establishment':
        """Factory method to create a new establishment."""
        return cls(
            name=name,
            company_id=company_id,
            code=code,
            responsible_name=responsible_name,
            responsible_email=Email(responsible_email) if responsible_email else None,
            responsible_phone=Phone(responsible_phone) if responsible_phone else None
        )

    @property
    def has_drive_folder(self) -> bool:
        """Check if establishment has a Drive folder configured."""
        return bool(self.drive_folder_id)

    @property
    def has_responsible(self) -> bool:
        """Check if establishment has a responsible person defined."""
        return bool(self.responsible_name)

    @property
    def can_send_whatsapp(self) -> bool:
        """Check if establishment can receive WhatsApp messages."""
        return bool(self.responsible_phone)

    @property
    def can_send_email(self) -> bool:
        """Check if establishment can receive emails."""
        return bool(self.responsible_email)

    @property
    def contacts(self) -> List[Contact]:
        """Get list of contacts."""
        return self._contacts.copy()

    @property
    def active_contacts(self) -> List[Contact]:
        """Get list of active contacts only."""
        return [c for c in self._contacts if c.is_active]

    @property
    def consultant_ids(self) -> List[UUID]:
        """Get list of assigned consultant IDs."""
        return self._consultant_ids.copy()

    def set_drive_folder(self, folder_id: str) -> None:
        """Set the Drive folder ID."""
        if not folder_id:
            raise ValidationError("ID da pasta do Drive não pode ser vazio", "drive_folder_id")
        self.drive_folder_id = folder_id
        self.mark_updated()

    def update_responsible(
        self,
        name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None
    ) -> None:
        """Update responsible person information."""
        if name is not None:
            self.responsible_name = name.strip() if name else None

        if email is not None:
            self.responsible_email = Email(email) if email else None

        if phone is not None:
            self.responsible_phone = Phone(phone) if phone else None

        self.mark_updated()

    def add_contact(self, contact: Contact) -> None:
        """Add a contact to the establishment."""
        self._contacts.append(contact)
        self.mark_updated()

    def remove_contact(self, contact: Contact) -> None:
        """Remove a contact from the establishment."""
        if contact in self._contacts:
            self._contacts.remove(contact)
            self.mark_updated()

    def assign_consultant(self, consultant_id: UUID) -> None:
        """Assign a consultant to this establishment."""
        if consultant_id not in self._consultant_ids:
            self._consultant_ids.append(consultant_id)
            self.mark_updated()

    def remove_consultant(self, consultant_id: UUID) -> None:
        """Remove a consultant from this establishment."""
        if consultant_id in self._consultant_ids:
            self._consultant_ids.remove(consultant_id)
            self.mark_updated()

    def deactivate(self) -> None:
        """Deactivate the establishment."""
        if not self.is_active:
            raise BusinessRuleViolationError("Estabelecimento já está inativo")
        self.is_active = False
        self.mark_updated()

    def activate(self) -> None:
        """Activate the establishment."""
        if self.is_active:
            raise BusinessRuleViolationError("Estabelecimento já está ativo")
        self.is_active = True
        self.mark_updated()

    def update_info(
        self,
        name: Optional[str] = None,
        code: Optional[str] = None
    ) -> None:
        """Update establishment basic information."""
        if name is not None:
            if not name.strip():
                raise ValidationError("Nome do estabelecimento não pode ser vazio", "name")
            self.name = name.strip()

        if code is not None:
            self.code = code.strip().upper() if code else None

        self.mark_updated()

    def __str__(self) -> str:
        code_str = f" ({self.code})" if self.code else ""
        return f"Establishment({self.name}{code_str})"
