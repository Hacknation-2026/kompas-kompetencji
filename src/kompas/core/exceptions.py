"""Domain-level exceptions mapped to HTTP responses by the API layer."""

from __future__ import annotations


class KompasError(Exception):
    """Base class for all application errors."""

    status_code: int = 400
    code: str = "kompas_error"

    def __init__(self, message: str, *, details: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConfigurationError(KompasError):
    """Invalid or missing configuration."""

    status_code = 500
    code = "configuration_error"


class NotFoundError(KompasError):
    """Requested entity does not exist."""

    status_code = 404
    code = "not_found"


class ValidationError(KompasError):
    """Business-rule validation failed."""

    status_code = 422
    code = "validation_error"


class WorkflowError(KompasError):
    """Illegal workflow transition or unmet step requirement."""

    status_code = 409
    code = "workflow_error"


class AuthenticationError(KompasError):
    """Missing / invalid credentials."""

    status_code = 401
    code = "authentication_error"


class AuthorizationError(KompasError):
    """Authenticated user lacks permission."""

    status_code = 403
    code = "authorization_error"


class ExternalServiceError(KompasError):
    """Upstream provider (LLM, SMTP, HR system) failed."""

    status_code = 502
    code = "external_service_error"
