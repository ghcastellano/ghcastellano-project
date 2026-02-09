"""
ActionPlan and ActionPlanItem Entities - Represents corrective action plans.
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4

from .base import Entity
from ..value_objects import Score, SeverityLevel
from ..exceptions import ValidationError, BusinessRuleViolationError


class ActionPlanItemStatus(str, Enum):
    """Status of individual action plan items."""
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"

    @property
    def label_pt(self) -> str:
        """Get Portuguese label for the status."""
        labels = {
            self.OPEN: "Pendente",
            self.IN_PROGRESS: "Em Andamento",
            self.RESOLVED: "Corrigido"
        }
        return labels[self]


@dataclass
class ActionPlanItem:
    """
    Individual item in an action plan.

    Represents a non-compliance finding and its corrective action.
    Preserves original AI data for fine-tuning purposes.
    """
    id: UUID = field(default_factory=uuid4)

    # Core content
    problem_description: str = ""
    corrective_action: str = ""
    legal_basis: Optional[str] = None

    # Deadline
    deadline_date: Optional[date] = None
    deadline_text: Optional[str] = None  # For ML training
    ai_suggested_deadline: Optional[str] = None  # Original AI suggestion

    # Classification
    severity: SeverityLevel = SeverityLevel.MEDIUM
    sector: Optional[str] = None
    order_index: int = 0

    # Status tracking
    status: ActionPlanItemStatus = ActionPlanItemStatus.OPEN
    current_status: Optional[str] = None  # Flexible status text

    # AI metadata (preserved for fine-tuning)
    original_status: Optional[str] = None
    original_score: Optional[float] = None

    # Manager input
    manager_notes: Optional[str] = None
    evidence_image_url: Optional[str] = None

    def __post_init__(self):
        if not self.problem_description:
            raise ValidationError("Descrição do problema é obrigatória", "problem_description")
        if not self.corrective_action:
            raise ValidationError("Ação corretiva é obrigatória", "corrective_action")

    @classmethod
    def from_ai_response(
        cls,
        problem: str,
        action: str,
        sector: Optional[str] = None,
        legal_basis: Optional[str] = None,
        deadline: Optional[str] = None,
        status: Optional[str] = None,
        score: Optional[float] = None,
        order: int = 0
    ) -> 'ActionPlanItem':
        """Create item from AI processing result, preserving original data."""
        # Determine severity from score if available
        severity = SeverityLevel.MEDIUM
        if score is not None:
            severity = SeverityLevel.from_score(score)

        return cls(
            problem_description=problem,
            corrective_action=action,
            sector=sector,
            legal_basis=legal_basis,
            ai_suggested_deadline=deadline,
            deadline_text=deadline,
            original_status=status,
            original_score=score,
            severity=severity,
            order_index=order
        )

    @property
    def is_resolved(self) -> bool:
        return self.status == ActionPlanItemStatus.RESOLVED

    @property
    def is_open(self) -> bool:
        return self.status == ActionPlanItemStatus.OPEN

    @property
    def has_evidence(self) -> bool:
        return bool(self.evidence_image_url)

    @property
    def score(self) -> Optional[Score]:
        """Get Score value object if original score exists."""
        if self.original_score is not None:
            return Score(self.original_score, self.original_status)
        return None

    def resolve(self, notes: Optional[str] = None) -> None:
        """Mark item as resolved."""
        self.status = ActionPlanItemStatus.RESOLVED
        self.current_status = "Corrigido"
        if notes:
            self.manager_notes = notes

    def reopen(self) -> None:
        """Reopen a resolved item."""
        self.status = ActionPlanItemStatus.OPEN
        self.current_status = "Reaberto"

    def start_progress(self) -> None:
        """Mark item as in progress."""
        self.status = ActionPlanItemStatus.IN_PROGRESS
        self.current_status = "Em Verificação"

    def add_evidence(self, image_url: str) -> None:
        """Add evidence image URL."""
        if not image_url:
            raise ValidationError("URL da evidência não pode ser vazia", "evidence_image_url")
        self.evidence_image_url = image_url

    def update_content(
        self,
        problem: Optional[str] = None,
        action: Optional[str] = None,
        deadline_text: Optional[str] = None,
        notes: Optional[str] = None
    ) -> None:
        """Update item content (manager edits)."""
        if problem is not None:
            if not problem.strip():
                raise ValidationError("Descrição do problema não pode ser vazia", "problem_description")
            self.problem_description = problem.strip()

        if action is not None:
            if not action.strip():
                raise ValidationError("Ação corretiva não pode ser vazia", "corrective_action")
            self.corrective_action = action.strip()

        if deadline_text is not None:
            self.deadline_text = deadline_text

        if notes is not None:
            self.manager_notes = notes

    def __str__(self) -> str:
        sector_str = f"[{self.sector}] " if self.sector else ""
        return f"ActionPlanItem({sector_str}{self.problem_description[:30]}...)"


@dataclass
class ActionPlan(Entity):
    """
    Action plan associated with an inspection.

    Contains multiple items representing non-conformities and their corrections.
    Stores statistics and can be approved by a manager.
    """
    inspection_id: UUID = None

    # Rich content
    summary_text: Optional[str] = None
    strengths_text: Optional[str] = None
    stats_json: Optional[Dict[str, Any]] = None

    # Approval info
    approved_by_id: Optional[UUID] = None
    approved_at: Optional[datetime] = None

    # PDF generation
    final_pdf_url: Optional[str] = None

    # Items
    _items: List[ActionPlanItem] = field(default_factory=list)

    def __post_init__(self):
        if self.inspection_id is None:
            raise ValidationError("ID da inspeção é obrigatório", "inspection_id")

    @classmethod
    def create(cls, inspection_id: UUID) -> 'ActionPlan':
        """Factory method to create a new action plan."""
        return cls(inspection_id=inspection_id)

    @property
    def items(self) -> List[ActionPlanItem]:
        """Get sorted list of items."""
        return sorted(self._items, key=lambda x: (x.sector or "", x.order_index))

    @property
    def item_count(self) -> int:
        """Get total number of items."""
        return len(self._items)

    @property
    def open_items_count(self) -> int:
        """Get count of open items."""
        return sum(1 for item in self._items if item.is_open)

    @property
    def resolved_items_count(self) -> int:
        """Get count of resolved items."""
        return sum(1 for item in self._items if item.is_resolved)

    @property
    def resolution_percentage(self) -> float:
        """Get percentage of resolved items."""
        if not self._items:
            return 0.0
        return (self.resolved_items_count / self.item_count) * 100

    @property
    def is_approved(self) -> bool:
        """Check if plan has been approved."""
        return self.approved_by_id is not None

    @property
    def has_pdf(self) -> bool:
        """Check if final PDF has been generated."""
        return bool(self.final_pdf_url)

    @property
    def sectors(self) -> List[str]:
        """Get unique sectors from items."""
        sectors = set(item.sector for item in self._items if item.sector)
        return sorted(sectors)

    @property
    def items_by_sector(self) -> Dict[str, List[ActionPlanItem]]:
        """Get items grouped by sector."""
        result = {}
        for item in self.items:
            sector = item.sector or "Geral"
            if sector not in result:
                result[sector] = []
            result[sector].append(item)
        return result

    @property
    def overall_score(self) -> Optional[float]:
        """Get overall score from stats."""
        if self.stats_json:
            return self.stats_json.get('score')
        return None

    @property
    def overall_percentage(self) -> Optional[float]:
        """Get overall percentage from stats."""
        if self.stats_json:
            return self.stats_json.get('percentage')
        return None

    def add_item(self, item: ActionPlanItem) -> None:
        """Add an item to the plan."""
        item.order_index = len(self._items)
        self._items.append(item)
        self.mark_updated()

    def remove_item(self, item_id: UUID) -> None:
        """Remove an item from the plan."""
        self._items = [i for i in self._items if i.id != item_id]
        # Reindex
        for idx, item in enumerate(self._items):
            item.order_index = idx
        self.mark_updated()

    def get_item(self, item_id: UUID) -> Optional[ActionPlanItem]:
        """Get item by ID."""
        for item in self._items:
            if item.id == item_id:
                return item
        return None

    def approve(self, approver_id: UUID) -> None:
        """Approve the action plan."""
        if self.is_approved:
            raise BusinessRuleViolationError("Plano já foi aprovado")
        self.approved_by_id = approver_id
        self.approved_at = datetime.utcnow()
        self.mark_updated()

    def set_stats(self, stats: Dict[str, Any]) -> None:
        """Set statistics JSON."""
        self.stats_json = stats
        self.mark_updated()

    def set_summary(self, summary: str, strengths: Optional[str] = None) -> None:
        """Set summary and strengths text."""
        self.summary_text = summary
        if strengths:
            self.strengths_text = strengths
        self.mark_updated()

    def set_pdf_url(self, url: str) -> None:
        """Set final PDF URL."""
        self.final_pdf_url = url
        self.mark_updated()

    def calculate_stats(self) -> Dict[str, Any]:
        """Calculate statistics from items."""
        if not self._items:
            return {}

        total_items = len(self._items)
        resolved = sum(1 for i in self._items if i.is_resolved)

        by_severity = {}
        by_sector = {}

        for item in self._items:
            # By severity
            sev = item.severity.value
            if sev not in by_severity:
                by_severity[sev] = {'total': 0, 'resolved': 0}
            by_severity[sev]['total'] += 1
            if item.is_resolved:
                by_severity[sev]['resolved'] += 1

            # By sector
            sector = item.sector or "Geral"
            if sector not in by_sector:
                by_sector[sector] = {'total': 0, 'resolved': 0, 'scores': []}
            by_sector[sector]['total'] += 1
            if item.is_resolved:
                by_sector[sector]['resolved'] += 1
            if item.original_score is not None:
                by_sector[sector]['scores'].append(item.original_score)

        # Calculate sector averages
        for sector, data in by_sector.items():
            if data['scores']:
                data['avg_score'] = sum(data['scores']) / len(data['scores'])
            else:
                data['avg_score'] = None
            del data['scores']

        stats = {
            'total_items': total_items,
            'resolved_items': resolved,
            'resolution_percentage': (resolved / total_items * 100) if total_items else 0,
            'by_severity': by_severity,
            'by_sector': by_sector
        }

        self.stats_json = stats
        return stats

    def __str__(self) -> str:
        status = "Aprovado" if self.is_approved else "Pendente"
        return f"ActionPlan({self.item_count} itens, {status})"
