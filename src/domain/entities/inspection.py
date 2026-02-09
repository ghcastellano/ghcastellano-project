"""
Inspection Entity - Represents a sanitary inspection report.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from uuid import UUID

from .base import Entity
from ..exceptions import ValidationError, BusinessRuleViolationError, InvalidStatusTransitionError


class InspectionStatus(str, Enum):
    """Inspection status workflow."""
    PROCESSING = "PROCESSING"
    PENDING_MANAGER_REVIEW = "PENDING_MANAGER_REVIEW"
    APPROVED = "APPROVED"
    PENDING_CONSULTANT_VERIFICATION = "PENDING_CONSULTANT_VERIFICATION"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"

    @property
    def label_pt(self) -> str:
        """Get Portuguese label for the status."""
        labels = {
            self.PROCESSING: "Processando",
            self.PENDING_MANAGER_REVIEW: "Aguardando Revisão",
            self.APPROVED: "Aprovado",
            self.PENDING_CONSULTANT_VERIFICATION: "Aguardando Verificação",
            self.COMPLETED: "Concluído",
            self.REJECTED: "Rejeitado"
        }
        return labels[self]

    @property
    def is_terminal(self) -> bool:
        """Check if this is a terminal status."""
        return self in (self.COMPLETED, self.REJECTED)

    @property
    def is_editable(self) -> bool:
        """Check if inspection can be edited in this status."""
        return self in (self.PENDING_MANAGER_REVIEW, self.APPROVED)

    @property
    def can_transition_to(self) -> List['InspectionStatus']:
        """Get valid status transitions from current status."""
        transitions = {
            self.PROCESSING: [self.PENDING_MANAGER_REVIEW, self.REJECTED],
            self.PENDING_MANAGER_REVIEW: [self.APPROVED, self.REJECTED],
            self.APPROVED: [self.PENDING_CONSULTANT_VERIFICATION, self.COMPLETED],
            self.PENDING_CONSULTANT_VERIFICATION: [self.COMPLETED],
            self.COMPLETED: [],
            self.REJECTED: []
        }
        return transitions.get(self, [])


@dataclass
class Inspection(Entity):
    """
    Inspection entity representing a sanitary inspection report.

    An inspection goes through a workflow:
    1. PROCESSING - Being processed by AI
    2. PENDING_MANAGER_REVIEW - Waiting for manager approval
    3. APPROVED - Approved by manager
    4. PENDING_CONSULTANT_VERIFICATION - Field verification needed
    5. COMPLETED - Fully completed
    """
    drive_file_id: str = ""
    establishment_id: Optional[UUID] = None
    status: InspectionStatus = InspectionStatus.PROCESSING

    drive_web_link: Optional[str] = None
    file_hash: Optional[str] = None  # For duplicate detection

    # AI processing data
    ai_raw_response: Optional[Dict[str, Any]] = None
    processing_logs: List[Dict[str, Any]] = field(default_factory=list)

    # Metadata
    processed_filename: Optional[str] = None

    def __post_init__(self):
        if not self.drive_file_id:
            raise ValidationError("ID do arquivo no Drive é obrigatório", "drive_file_id")

    @classmethod
    def create(
        cls,
        drive_file_id: str,
        establishment_id: UUID,
        file_hash: Optional[str] = None,
        drive_web_link: Optional[str] = None
    ) -> 'Inspection':
        """Factory method to create a new inspection."""
        return cls(
            drive_file_id=drive_file_id,
            establishment_id=establishment_id,
            file_hash=file_hash,
            drive_web_link=drive_web_link,
            status=InspectionStatus.PROCESSING
        )

    @property
    def is_processing(self) -> bool:
        return self.status == InspectionStatus.PROCESSING

    @property
    def is_pending_review(self) -> bool:
        return self.status == InspectionStatus.PENDING_MANAGER_REVIEW

    @property
    def is_approved(self) -> bool:
        return self.status == InspectionStatus.APPROVED

    @property
    def is_completed(self) -> bool:
        return self.status == InspectionStatus.COMPLETED

    @property
    def is_rejected(self) -> bool:
        return self.status == InspectionStatus.REJECTED

    @property
    def can_be_edited(self) -> bool:
        """Check if inspection can be edited."""
        return self.status.is_editable

    @property
    def is_terminal(self) -> bool:
        """Check if inspection is in terminal status."""
        return self.status.is_terminal

    def _validate_transition(self, new_status: InspectionStatus) -> None:
        """Validate status transition."""
        if new_status not in self.status.can_transition_to:
            raise InvalidStatusTransitionError(
                current_status=self.status.value,
                new_status=new_status.value,
                entity_type="Inspection"
            )

    def transition_to(self, new_status: InspectionStatus) -> None:
        """Transition to a new status with validation."""
        self._validate_transition(new_status)
        self.status = new_status
        self.mark_updated()

    def mark_processing_complete(self) -> None:
        """Mark AI processing as complete, ready for review."""
        self._validate_transition(InspectionStatus.PENDING_MANAGER_REVIEW)
        self.status = InspectionStatus.PENDING_MANAGER_REVIEW
        self.mark_updated()

    def approve(self) -> None:
        """Approve the inspection."""
        self._validate_transition(InspectionStatus.APPROVED)
        self.status = InspectionStatus.APPROVED
        self.mark_updated()

    def reject(self) -> None:
        """Reject the inspection."""
        self._validate_transition(InspectionStatus.REJECTED)
        self.status = InspectionStatus.REJECTED
        self.mark_updated()

    def send_for_verification(self) -> None:
        """Send for field verification by consultant."""
        self._validate_transition(InspectionStatus.PENDING_CONSULTANT_VERIFICATION)
        self.status = InspectionStatus.PENDING_CONSULTANT_VERIFICATION
        self.mark_updated()

    def complete(self) -> None:
        """Mark inspection as completed."""
        if self.status not in (InspectionStatus.APPROVED, InspectionStatus.PENDING_CONSULTANT_VERIFICATION):
            raise InvalidStatusTransitionError(
                current_status=self.status.value,
                new_status=InspectionStatus.COMPLETED.value,
                entity_type="Inspection"
            )
        self.status = InspectionStatus.COMPLETED
        self.mark_updated()

    def add_processing_log(self, message: str, stage: Optional[str] = None) -> None:
        """Add a processing log entry."""
        log_entry = {
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
            "stage": stage
        }
        self.processing_logs.append(log_entry)

    def set_ai_response(self, response: Dict[str, Any]) -> None:
        """Store the raw AI response."""
        self.ai_raw_response = response
        self.mark_updated()

    def is_duplicate_of(self, file_hash: str) -> bool:
        """Check if this inspection is a duplicate based on file hash."""
        return self.file_hash == file_hash if self.file_hash else False

    def __str__(self) -> str:
        return f"Inspection({self.drive_file_id[:8]}..., {self.status.label_pt})"
