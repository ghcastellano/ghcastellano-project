"""
User Entity - Represents a system user.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List
from uuid import UUID, uuid4

from .base import Entity
from ..value_objects import Email, Phone
from ..exceptions import ValidationError, BusinessRuleViolationError


class UserRole(str, Enum):
    """User roles in the system."""
    CONSULTANT = "CONSULTANT"
    MANAGER = "MANAGER"
    ADMIN = "ADMIN"

    @property
    def label_pt(self) -> str:
        """Get Portuguese label for the role."""
        labels = {
            self.CONSULTANT: "Consultor",
            self.MANAGER: "Gestor",
            self.ADMIN: "Administrador"
        }
        return labels[self]

    @property
    def can_approve_plans(self) -> bool:
        """Check if role can approve action plans."""
        return self in (self.MANAGER, self.ADMIN)

    @property
    def can_manage_users(self) -> bool:
        """Check if role can manage other users."""
        return self in (self.MANAGER, self.ADMIN)

    @property
    def can_access_admin(self) -> bool:
        """Check if role can access admin panel."""
        return self == self.ADMIN


@dataclass
class User(Entity):
    """
    User entity representing a system user.

    Users can be consultants, managers, or admins.
    Each user belongs to a company and can have access to multiple establishments.
    """
    email: Email = None
    name: Optional[str] = None
    role: UserRole = UserRole.CONSULTANT
    is_active: bool = True
    must_change_password: bool = False
    company_id: Optional[UUID] = None
    whatsapp: Optional[Phone] = None

    # Not persisted - for domain operations
    _establishment_ids: List[UUID] = field(default_factory=list)

    def __post_init__(self):
        if self.email is None:
            raise ValidationError("Email é obrigatório para usuário", "email")

    @classmethod
    def create_consultant(
        cls,
        email: str,
        name: str,
        company_id: UUID,
        establishment_ids: List[UUID] = None
    ) -> 'User':
        """Factory method to create a consultant user."""
        user = cls(
            email=Email(email),
            name=name,
            role=UserRole.CONSULTANT,
            company_id=company_id,
            must_change_password=True
        )
        if establishment_ids:
            user._establishment_ids = establishment_ids
        return user

    @classmethod
    def create_manager(
        cls,
        email: str,
        name: str,
        company_id: UUID
    ) -> 'User':
        """Factory method to create a manager user."""
        return cls(
            email=Email(email),
            name=name,
            role=UserRole.MANAGER,
            company_id=company_id,
            must_change_password=True
        )

    @classmethod
    def create_admin(cls, email: str, name: str) -> 'User':
        """Factory method to create an admin user."""
        return cls(
            email=Email(email),
            name=name,
            role=UserRole.ADMIN,
            must_change_password=True
        )

    @property
    def is_consultant(self) -> bool:
        return self.role == UserRole.CONSULTANT

    @property
    def is_manager(self) -> bool:
        return self.role == UserRole.MANAGER

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    @property
    def display_name(self) -> str:
        """Get display name, falling back to email if name not set."""
        return self.name or str(self.email)

    def deactivate(self) -> None:
        """Deactivate the user."""
        if not self.is_active:
            raise BusinessRuleViolationError("Usuário já está inativo")
        self.is_active = False
        self.mark_updated()

    def activate(self) -> None:
        """Activate the user."""
        if self.is_active:
            raise BusinessRuleViolationError("Usuário já está ativo")
        self.is_active = True
        self.mark_updated()

    def require_password_change(self) -> None:
        """Mark user as requiring password change."""
        self.must_change_password = True
        self.mark_updated()

    def password_changed(self) -> None:
        """Mark password as changed."""
        self.must_change_password = False
        self.mark_updated()

    def can_access_establishment(self, establishment_id: UUID) -> bool:
        """Check if user can access a specific establishment."""
        if self.is_admin:
            return True
        return establishment_id in self._establishment_ids

    def assign_establishment(self, establishment_id: UUID) -> None:
        """Assign user to an establishment."""
        if not self.is_consultant:
            raise BusinessRuleViolationError(
                "Apenas consultores podem ser atribuídos a estabelecimentos"
            )
        if establishment_id not in self._establishment_ids:
            self._establishment_ids.append(establishment_id)
            self.mark_updated()

    def remove_establishment(self, establishment_id: UUID) -> None:
        """Remove user from an establishment."""
        if establishment_id in self._establishment_ids:
            self._establishment_ids.remove(establishment_id)
            self.mark_updated()

    def change_role(self, new_role: UserRole) -> None:
        """Change user role with validation."""
        if self.role == new_role:
            return

        # Clear establishment assignments if changing from consultant
        if self.role == UserRole.CONSULTANT and new_role != UserRole.CONSULTANT:
            self._establishment_ids = []

        self.role = new_role
        self.mark_updated()

    def __str__(self) -> str:
        return f"User({self.display_name}, {self.role.label_pt})"
