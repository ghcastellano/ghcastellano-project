"""
Domain Entities - Pure business objects without infrastructure dependencies.
"""

from .base import Entity
from .user import User, UserRole
from .company import Company
from .establishment import Establishment
from .inspection import Inspection, InspectionStatus
from .action_plan import ActionPlan, ActionPlanItem, ActionPlanItemStatus

__all__ = [
    'Entity',
    'User',
    'UserRole',
    'Company',
    'Establishment',
    'Inspection',
    'InspectionStatus',
    'ActionPlan',
    'ActionPlanItem',
    'ActionPlanItemStatus',
]
