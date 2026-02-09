"""
Base Entity - Abstract base for all domain entities.
"""

from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4


@dataclass
class Entity(ABC):
    """
    Base class for all domain entities.

    Entities have identity (id) and are mutable.
    They encapsulate business logic and rules.
    """
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    def __eq__(self, other) -> bool:
        if not isinstance(other, Entity):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    def mark_updated(self) -> None:
        """Mark entity as updated with current timestamp."""
        self.updated_at = datetime.utcnow()
