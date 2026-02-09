# Value Objects - Immutable domain primitives
from .email import Email
from .phone import Phone
from .score import Score, SeverityLevel

__all__ = ['Email', 'Phone', 'Score', 'SeverityLevel']
