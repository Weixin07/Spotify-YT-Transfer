"""Utilities for redacting sensitive information from logs."""

import logging
import re
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

# Sensitive query parameters that should be redacted
SENSITIVE_PARAMS = {
    "code",  # OAuth authorization code
    "state",  # OAuth state parameter
    "access_token",  # Access token
    "refresh_token",  # Refresh token
    "token",  # Generic token
    "api_key",  # API keys
    "apikey",
    "key",
    "secret",
    "password",
    "client_secret",
}

# Patterns for sensitive data in log messages
SENSITIVE_PATTERNS = [
    # Bearer tokens
    (re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE), "Bearer [REDACTED]"),
    # Authorization headers
    (re.compile(r"Authorization:\s*[^\s]+", re.IGNORECASE), "Authorization: [REDACTED]"),
    # Access tokens in JSON
    (re.compile(r'"access_token"\s*:\s*"[^"]*"', re.IGNORECASE), '"access_token": "[REDACTED]"'),
    # Refresh tokens in JSON
    (re.compile(r'"refresh_token"\s*:\s*"[^"]*"', re.IGNORECASE), '"refresh_token": "[REDACTED]"'),
    # Generic token patterns (alphanumeric strings longer than 20 chars that look like tokens)
    (
        re.compile(
            r"['\"]?(?:token|key|secret|password)['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9\-._~+/]{20,})['\"]?",
            re.IGNORECASE,
        ),
        lambda m: m.group(0).replace(m.group(1), "[REDACTED]"),
    ),
]


def redact_url(url: str) -> str:
    """
    Redact sensitive query parameters from a URL.

    Args:
        url: URL string that may contain sensitive parameters

    Returns:
        URL with sensitive parameters replaced with [REDACTED]

    Examples:
        >>> redact_url("http://localhost/callback?code=abc123&state=xyz")
        'http://localhost/callback?code=[REDACTED]&state=[REDACTED]'
    """
    if not url:
        return url

    try:
        parsed = urlparse(url)
        if not parsed.query:
            return url

        # Parse query parameters
        params = parse_qs(parsed.query, keep_blank_values=True)

        # Redact sensitive parameters
        redacted_params = {}
        for key, values in params.items():
            if key.lower() in SENSITIVE_PARAMS:
                redacted_params[key] = ["[REDACTED]"] * len(values)
            else:
                redacted_params[key] = values

        # Reconstruct URL with redacted parameters
        # Convert list values back to single values for urlencode
        flat_params = {k: v[0] if len(v) == 1 else v for k, v in redacted_params.items()}
        redacted_query = urlencode(flat_params, doseq=True)

        # Rebuild the URL
        redacted_parsed = parsed._replace(query=redacted_query)
        return urlunparse(redacted_parsed)

    except Exception:
        # If parsing fails, return original URL (better to log than crash)
        return url


def redact_message(message: str) -> str:
    """
    Redact sensitive information from a log message.

    Args:
        message: Log message that may contain sensitive data

    Returns:
        Message with sensitive data replaced with [REDACTED]

    Examples:
        >>> redact_message("Token: Bearer abc123xyz")
        'Token: Bearer [REDACTED]'
    """
    if not message:
        return message

    redacted = message

    # Apply all redaction patterns
    for pattern, replacement in SENSITIVE_PATTERNS:
        if callable(replacement):
            redacted = pattern.sub(replacement, redacted)
        else:
            redacted = pattern.sub(replacement, redacted)

    # Redact URLs in the message
    url_pattern = re.compile(r"https?://[^\s]+")
    urls = url_pattern.findall(redacted)
    for url in urls:
        redacted_url = redact_url(url)
        redacted = redacted.replace(url, redacted_url)

    return redacted


class RedactingFilter(logging.Filter):
    """
    Logging filter that redacts sensitive information from log records.

    This filter should be added to all handlers to prevent accidental
    exposure of tokens, credentials, and other sensitive data.

    Usage:
        handler.addFilter(RedactingFilter())
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Filter and redact sensitive information from log record.

        Args:
            record: Log record to filter

        Returns:
            True (always allow the record, just redact it)
        """
        # Redact the main message
        if hasattr(record, "msg") and isinstance(record.msg, str):
            record.msg = redact_message(record.msg)

        # Redact any arguments used in formatting
        if hasattr(record, "args") and record.args:
            if isinstance(record.args, dict):
                record.args = {k: self._redact_value(v) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self._redact_value(arg) for arg in record.args)
            else:
                record.args = self._redact_value(record.args)

        return True

    def _redact_value(self, value: Any) -> Any:
        """
        Redact a single value if it's a string containing sensitive data.

        Args:
            value: Value to potentially redact

        Returns:
            Redacted value or original value if not a string
        """
        if isinstance(value, str):
            return redact_message(value)
        return value
