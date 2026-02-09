# Domain Layer - Pure business logic, no dependencies on infrastructure

# Exceptions
from .exceptions import (
    DomainError,
    ValidationError,
    NotFoundError,
    UnauthorizedError,
    BusinessRuleViolationError,
    InvalidStatusTransitionError,
    InspectionNotFoundError,
    UserNotFoundError,
    CompanyNotFoundError,
    EstablishmentNotFoundError,
    ActionPlanNotFoundError,
)

# Value Objects
from .value_objects import (
    Email,
    Phone,
    Score,
    SeverityLevel,
)

# Entities
from .entities import (
    Entity,
    User,
    UserRole,
    Company,
    Establishment,
    Inspection,
    InspectionStatus,
    ActionPlan,
    ActionPlanItem,
    ActionPlanItemStatus,
)

__all__ = [
    # Exceptions
    'DomainError',
    'ValidationError',
    'NotFoundError',
    'UnauthorizedError',
    'BusinessRuleViolationError',
    'InvalidStatusTransitionError',
    'InspectionNotFoundError',
    'UserNotFoundError',
    'CompanyNotFoundError',
    'EstablishmentNotFoundError',
    'ActionPlanNotFoundError',
    # Value Objects
    'Email',
    'Phone',
    'Score',
    'SeverityLevel',
    # Entities
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
