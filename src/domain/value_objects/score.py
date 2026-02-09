"""
Score Value Object - Inspection scores and severity levels.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional
from ..exceptions import ValidationError


class SeverityLevel(str, Enum):
    """Severity levels for action plan items."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @classmethod
    def from_score(cls, score: float) -> 'SeverityLevel':
        """Determine severity based on score."""
        if score >= 8:
            return cls.LOW
        elif score >= 5:
            return cls.MEDIUM
        elif score >= 2:
            return cls.HIGH
        else:
            return cls.CRITICAL

    @property
    def weight(self) -> int:
        """Get numeric weight for calculations."""
        weights = {
            self.LOW: 1,
            self.MEDIUM: 2,
            self.HIGH: 3,
            self.CRITICAL: 4
        }
        return weights[self]

    @property
    def label_pt(self) -> str:
        """Get Portuguese label."""
        labels = {
            self.LOW: "Baixa",
            self.MEDIUM: "Média",
            self.HIGH: "Alta",
            self.CRITICAL: "Crítica"
        }
        return labels[self]


@dataclass(frozen=True)
class Score:
    """
    Immutable score value object for inspection items.

    Represents a score from 0 to 10, with associated status.

    Usage:
        score = Score(7.5, "Parcialmente Conforme")
        print(score.value)      # 7.5
        print(score.status)     # "Parcialmente Conforme"
        print(score.is_compliant)  # False
        print(score.severity)   # SeverityLevel.MEDIUM
    """

    value: float
    status: Optional[str] = None

    # Status mapping for compliance check
    COMPLIANT_STATUSES = {
        'conforme', 'ok', 'adequado', 'atende', 'regular',
        'satisfatório', 'satisfatorio', 'aprovado'
    }

    NON_COMPLIANT_STATUSES = {
        'não conforme', 'nao conforme', 'inadequado', 'irregular',
        'reprovado', 'crítico', 'critico', 'grave'
    }

    def __post_init__(self):
        # Validate score range
        if self.value < 0 or self.value > 10:
            raise ValidationError(
                f"Pontuação deve estar entre 0 e 10, recebido: {self.value}",
                "score"
            )

        # Normalize to float
        object.__setattr__(self, 'value', float(self.value))

    @property
    def percentage(self) -> float:
        """Get score as percentage (0-100)."""
        return self.value * 10

    @property
    def is_compliant(self) -> bool:
        """Check if score indicates compliance."""
        # If we have a status, use it
        if self.status:
            status_lower = self.status.lower().strip()
            if status_lower in self.COMPLIANT_STATUSES:
                return True
            if status_lower in self.NON_COMPLIANT_STATUSES:
                return False

        # Fall back to score-based compliance (>= 7 is compliant)
        return self.value >= 7.0

    @property
    def severity(self) -> SeverityLevel:
        """Get severity level based on score."""
        return SeverityLevel.from_score(self.value)

    @property
    def status_normalized(self) -> str:
        """Get normalized status string."""
        if self.is_compliant:
            return "Conforme"
        elif self.status and 'parcial' in self.status.lower():
            return "Parcialmente Conforme"
        else:
            return "Não Conforme"

    def __str__(self) -> str:
        return f"{self.value:.1f}/10"

    def __eq__(self, other) -> bool:
        if isinstance(other, Score):
            return self.value == other.value
        if isinstance(other, (int, float)):
            return self.value == other
        return False

    def __lt__(self, other) -> bool:
        if isinstance(other, Score):
            return self.value < other.value
        if isinstance(other, (int, float)):
            return self.value < other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.value)

    @classmethod
    def perfect(cls) -> 'Score':
        """Create a perfect score (10)."""
        return cls(10.0, "Conforme")

    @classmethod
    def zero(cls) -> 'Score':
        """Create a zero score."""
        return cls(0.0, "Não Conforme")

    @classmethod
    def from_percentage(cls, percentage: float, status: str = None) -> 'Score':
        """Create score from percentage (0-100)."""
        return cls(percentage / 10, status)
