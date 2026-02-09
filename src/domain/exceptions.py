"""
Domain exceptions - Business-level errors.

These exceptions represent business rule violations and domain-specific errors.
They should be caught at the application layer and translated to appropriate responses.
"""


class DomainError(Exception):
    """Base exception for all domain errors."""

    def __init__(self, message: str, code: str = "DOMAIN_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class ValidationError(DomainError):
    """Raised when validation fails."""

    def __init__(self, message: str, field: str = None):
        self.field = field
        code = f"VALIDATION_ERROR_{field.upper()}" if field else "VALIDATION_ERROR"
        super().__init__(message, code)


class NotFoundError(DomainError):
    """Raised when an entity is not found."""

    def __init__(self, entity_type: str, identifier: str = None):
        self.entity_type = entity_type
        self.identifier = identifier
        message = f"{entity_type} não encontrado"
        if identifier:
            message = f"{entity_type} '{identifier}' não encontrado"
        super().__init__(message, f"{entity_type.upper()}_NOT_FOUND")


class UnauthorizedError(DomainError):
    """Raised when user doesn't have permission."""

    def __init__(self, message: str = "Acesso não autorizado"):
        super().__init__(message, "UNAUTHORIZED")


class BusinessRuleViolationError(DomainError):
    """Raised when a business rule is violated."""

    def __init__(self, rule: str, message: str):
        self.rule = rule
        super().__init__(message, f"BUSINESS_RULE_{rule.upper()}")


# Specific domain errors

class InspectionNotFoundError(NotFoundError):
    """Raised when an inspection is not found."""

    def __init__(self, inspection_id: str = None):
        super().__init__("Inspeção", inspection_id)


class EstablishmentNotFoundError(NotFoundError):
    """Raised when an establishment is not found."""

    def __init__(self, establishment_id: str = None):
        super().__init__("Estabelecimento", establishment_id)


class UserNotFoundError(NotFoundError):
    """Raised when a user is not found."""

    def __init__(self, user_id: str = None):
        super().__init__("Usuário", user_id)


class InvalidStatusTransitionError(BusinessRuleViolationError):
    """Raised when an invalid status transition is attempted."""

    def __init__(self, current_status: str, target_status: str):
        self.current_status = current_status
        self.target_status = target_status
        message = f"Não é possível mudar de '{current_status}' para '{target_status}'"
        super().__init__("STATUS_TRANSITION", message)


class InspectionAlreadyProcessedError(BusinessRuleViolationError):
    """Raised when trying to process an already processed inspection."""

    def __init__(self, inspection_id: str):
        self.inspection_id = inspection_id
        message = f"Inspeção '{inspection_id}' já foi processada"
        super().__init__("ALREADY_PROCESSED", message)


class DuplicateFileError(BusinessRuleViolationError):
    """Raised when a duplicate file is uploaded."""

    def __init__(self, file_hash: str):
        self.file_hash = file_hash
        message = "Este arquivo já foi enviado anteriormente"
        super().__init__("DUPLICATE_FILE", message)
