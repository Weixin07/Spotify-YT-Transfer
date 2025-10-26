"""Centralized error response utilities for consistent API error handling.

This module provides utilities to generate structured, machine-readable error
responses that are consistent across all API endpoints.

Example Response Format:
    {
        "detail": {
            "code": "not_found",
            "message": "Playlist not found",
            "details": {"playlist_name": "My Songs"}
        }
    }
"""

from typing import Any


def error_response(
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Generate a structured error response payload.

    This ensures consistent error formatting across all API endpoints,
    making it easier for clients to programmatically handle errors.

    Args:
        code: Machine-readable error code (e.g., 'not_found', 'validation_error')
        message: Human-readable error message
        details: Optional dictionary with additional error context

    Returns:
        Structured error payload suitable for HTTPException detail parameter

    Examples:
        >>> error_response("not_found", "Playlist not found", {"name": "My Songs"})
        {"code": "not_found", "message": "Playlist not found", "details": {"name": "My Songs"}}

        >>> error_response("validation_error", "Invalid parameter")
        {"code": "validation_error", "message": "Invalid parameter"}
    """
    payload: dict[str, Any] = {
        "code": code,
        "message": message,
    }
    if details:
        payload["details"] = details
    return payload


# Common error codes for consistency
class ErrorCodes:
    """Standard error codes used across the API."""

    # Authentication & Authorization (4xx)
    MISSING_PARAMETER = "missing_parameter"
    INVALID_STATE = "invalid_state"
    OAUTH_CREDENTIALS_MISSING = "oauth_credentials_missing"
    AUTHENTICATION_FAILED = "authentication_failed"

    # Resource errors (4xx)
    NOT_FOUND = "not_found"
    PLAYLIST_NOT_FOUND = "playlist_not_found"
    COVER_NOT_FOUND = "cover_not_found"

    # Validation errors (4xx)
    VALIDATION_ERROR = "validation_error"
    INVALID_PARAMETER = "invalid_parameter"

    # External service errors (5xx)
    EXTERNAL_SERVICE_ERROR = "external_service_error"
    SPOTIFY_API_ERROR = "spotify_api_error"
    YOUTUBE_API_ERROR = "youtube_api_error"
    QUOTA_EXCEEDED = "quota_exceeded"

    # Server errors (5xx)
    UNEXPECTED_ERROR = "unexpected_error"
    SERVICE_ERROR = "service_error"
