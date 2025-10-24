"""Shared service-layer exceptions with structured metadata."""

from __future__ import annotations

from typing import Any


class ServiceError(Exception):
    """Base class for service-layer errors with structured detail metadata."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "service_error",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}


class QuotaExceededError(ServiceError):
    """Raised when an external API quota has been exhausted."""

    def __init__(self, message: str, *, service: str, details: dict[str, Any] | None = None) -> None:
        merged_details: dict[str, Any] = {"service": service}
        if details:
            merged_details.update(details)
        super().__init__(message=message, code="quota_exceeded", details=merged_details)


class ExternalServiceError(ServiceError):
    """Raised when an upstream provider returns an unexpected error."""

    def __init__(
        self,
        message: str,
        *,
        service: str,
        code: str = "external_service_error",
        details: dict[str, Any] | None = None,
    ) -> None:
        merged_details: dict[str, Any] = {"service": service}
        if details:
            merged_details.update(details)
        super().__init__(message=message, code=code, details=merged_details)


class ValidationServiceError(ServiceError):
    """Raised when service preconditions or parameters are invalid."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message=message, code="validation_error", details=details or {})
