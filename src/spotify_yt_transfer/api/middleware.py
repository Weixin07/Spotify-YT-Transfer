"""Middleware for redacting sensitive information from HTTP logs."""

import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from spotify_yt_transfer.core.log_redaction import redact_url

logger = logging.getLogger(__name__)


class RedactedLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs HTTP requests with sensitive data redacted.

    This middleware intercepts all incoming requests and logs them
    with URLs redacted to prevent exposure of OAuth codes, tokens,
    and other sensitive query parameters.

    IMPORTANT: This middleware should be added FIRST to ensure it
    runs before any other logging middleware.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """
        Process the request and log with redaction.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware or route handler

        Returns:
            HTTP response
        """
        # Redact URL before logging
        redacted_url = redact_url(str(request.url))
        method = request.method

        # Log the incoming request with redacted URL
        logger.debug(f"Incoming request: {method} {redacted_url}")

        # Track request timing
        start_time = time.time()

        # Process the request
        try:
            response = await call_next(request)
            process_time = time.time() - start_time

            # Log response with redacted URL
            logger.info(
                f"{method} {redacted_url} - {response.status_code} " f"({process_time:.3f}s)"
            )

            return response

        except Exception as exc:
            process_time = time.time() - start_time

            # Log errors with redacted URL
            logger.error(
                f"{method} {redacted_url} - ERROR: {exc.__class__.__name__} "
                f"({process_time:.3f}s)",
                exc_info=True,
            )
            raise
