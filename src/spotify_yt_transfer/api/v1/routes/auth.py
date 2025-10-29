"""Authentication and OAuth callback endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from spotipy.client import SpotifyException

from spotify_yt_transfer.api.dependencies import get_oauth_service
from spotify_yt_transfer.api.errors import ErrorCodes, error_response
from spotify_yt_transfer.services import OAuthService, OAuthStateError, ServiceError

logger = logging.getLogger(__name__)

router = APIRouter()


def _extract_code_and_state(request: Request) -> tuple[str, str]:
    """
    Extract OAuth code and state from request query parameters.

    Args:
        request: The incoming HTTP request

    Returns:
        Tuple of (code, state)

    Raises:
        HTTPException: If code or state is missing
    """
    code = request.query_params.get("code")
    state = request.query_params.get("state")

    if not code:
        logger.error("OAuth callback missing 'code' parameter")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(
                ErrorCodes.MISSING_PARAMETER,
                "Missing code parameter in callback",
                {"parameter": "code"},
            ),
        )

    if not state:
        logger.error("OAuth callback missing 'state' parameter")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(
                ErrorCodes.MISSING_PARAMETER,
                "Missing state parameter in callback",
                {"parameter": "state"},
            ),
        )

    return code, state


@router.get(
    "/spotify/authorize",
    summary="Get Spotify authorization URL (JSON)",
    description="Generates a Spotify OAuth2 authorization URL for headless deployments. Returns JSON with URL and state.",
)
async def spotify_authorize(
    oauth: OAuthService = Depends(get_oauth_service),
) -> dict[str, str]:
    """
    Produce a Spotify authorization URL and CSRF state token.

    Returns:
        Dict containing the URL and state value.
    """
    response = oauth.build_spotify_authorize_url()
    return {"authorize_url": response.authorize_url, "state": response.state}


@router.get(
    "/spotify/login",
    summary="Redirect to Spotify authorization",
    description="Automatically redirects to Spotify OAuth2 authorization page. Use this in a browser.",
)
async def spotify_login(
    oauth: OAuthService = Depends(get_oauth_service),
) -> RedirectResponse:
    """
    Redirect user directly to Spotify authorization page.

    This endpoint is designed for browser use - it will automatically
    redirect you to Spotify's login page.

    Returns:
        HTTP 302 redirect to Spotify authorization URL
    """
    response = oauth.build_spotify_authorize_url()
    logger.info("Redirecting to Spotify authorization page (state=%s)", response.state)
    return RedirectResponse(url=response.authorize_url, status_code=status.HTTP_302_FOUND)


@router.get(
    "/spotify/callback",
    summary="Spotify OAuth2 callback",
    description="Handles Spotify OAuth2 callback by exchanging the code for access tokens.",
    responses={
        200: {
            "description": "Authentication successful",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Spotify authentication successful",
                        "expires_in": 3600,
                    }
                }
            },
        },
        400: {
            "description": "Missing or invalid parameters",
            "content": {
                "application/json": {
                    "example": {
                        "detail": {
                            "code": "missing_parameter",
                            "message": "Missing code parameter in callback",
                            "details": {"parameter": "code"},
                        }
                    }
                }
            },
        },
    },
)
async def spotify_callback(
    request: Request,
    oauth: OAuthService = Depends(get_oauth_service),
) -> dict[str, Any]:
    """
    Handle Spotify OAuth2 callback and exchange code for tokens.

    SECURITY: Tokens are stored securely in OS keyring and NOT returned in response.

    Args:
        request: The incoming HTTP request with query parameters

    Returns:
        Dictionary with success message (tokens NOT included for security)

    Raises:
        HTTPException: If code/state is missing or authentication fails
    """
    code, state = _extract_code_and_state(request)

    try:
        # Note: URL redaction is handled by RedactedLoggingMiddleware
        logger.info("Processing Spotify OAuth callback (state=%s)", state)
        token_info = oauth.exchange_spotify_code(code=code, state=state)
    except OAuthStateError as exc:
        logger.warning("Spotify OAuth state validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(ErrorCodes.INVALID_STATE, str(exc)),
        ) from exc
    except SpotifyException as exc:
        logger.error("Spotify authentication failed due to upstream error: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=error_response(
                ErrorCodes.SPOTIFY_API_ERROR, "Spotify authentication failed", {"reason": str(exc)}
            ),
        ) from exc
    except ServiceError as exc:
        logger.error("OAuth service error during Spotify callback: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response(exc.code, str(exc), exc.details),
        ) from exc
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Unexpected Spotify authentication failure")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=error_response(
                ErrorCodes.AUTHENTICATION_FAILED, "Spotify authentication failed"
            ),
        ) from exc

    logger.info("Spotify authentication successful for state=%s", state)

    # SECURITY: Do NOT return tokens in HTTP response
    # Tokens are stored securely in OS keyring via KeyringCacheHandler
    return {
        "message": "Spotify authentication successful. Tokens stored securely.",
        "expires_in": token_info.get("expires_in", 3600) if token_info else 3600,
    }


@router.get(
    "/youtube/authorize",
    summary="Get YouTube authorization URL (JSON)",
    description="Generates a YouTube OAuth2 authorization URL for headless deployments. Returns JSON with URL and state.",
)
async def youtube_authorize(
    oauth: OAuthService = Depends(get_oauth_service),
) -> dict[str, str]:
    """
    Produce a YouTube authorization URL and CSRF state token.

    Returns:
        Dict containing the URL and state value.
    """
    response = oauth.build_youtube_authorize_url()
    return {"authorize_url": response.authorize_url, "state": response.state}


@router.get(
    "/youtube/login",
    summary="Redirect to YouTube authorization",
    description="Automatically redirects to YouTube OAuth2 authorization page. Use this in a browser.",
)
async def youtube_login(
    oauth: OAuthService = Depends(get_oauth_service),
) -> RedirectResponse:
    """
    Redirect user directly to YouTube authorization page.

    This endpoint is designed for browser use - it will automatically
    redirect you to YouTube's login page.

    Returns:
        HTTP 302 redirect to YouTube authorization URL
    """
    response = oauth.build_youtube_authorize_url()
    logger.info("Redirecting to YouTube authorization page (state=%s)", response.state)
    return RedirectResponse(url=response.authorize_url, status_code=status.HTTP_302_FOUND)


@router.get(
    "/youtube/callback",
    summary="YouTube OAuth2 callback",
    description="Handles YouTube OAuth2 callback by exchanging the code for access tokens.",
    responses={
        200: {
            "description": "Authentication successful",
            "content": {
                "application/json": {
                    "example": {
                        "message": "YouTube authentication successful",
                        "scopes": ["https://www.googleapis.com/auth/youtube.force-ssl"],
                    }
                }
            },
        },
        400: {
            "description": "Missing or invalid parameters",
            "content": {
                "application/json": {
                    "example": {
                        "detail": {
                            "code": "missing_parameter",
                            "message": "Missing code parameter in callback",
                            "details": {"parameter": "code"},
                        }
                    }
                }
            },
        },
    },
)
async def youtube_callback(
    request: Request,
    oauth: OAuthService = Depends(get_oauth_service),
) -> dict[str, Any]:
    """
    Handle YouTube OAuth2 callback and exchange code for tokens.

    SECURITY: Tokens are stored securely in OS keyring and NOT returned in response.

    Args:
        request: The incoming HTTP request with query parameters

    Returns:
        Dictionary with success message (tokens NOT included for security)

    Raises:
        HTTPException: If code/state is missing or authentication fails
    """
    code, state = _extract_code_and_state(request)

    try:
        # Note: URL redaction is handled by RedactedLoggingMiddleware
        logger.info("Processing YouTube OAuth callback (state=%s)", state)
        credentials_info = oauth.exchange_youtube_code(code=code, state=state)
    except OAuthStateError as exc:
        logger.warning("YouTube OAuth state validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(ErrorCodes.INVALID_STATE, str(exc)),
        ) from exc
    except ServiceError as exc:
        logger.error("OAuth service error during YouTube callback: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response(exc.code, str(exc), exc.details),
        ) from exc
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("YouTube authentication failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=error_response(
                ErrorCodes.AUTHENTICATION_FAILED, "YouTube authentication failed"
            ),
        ) from exc

    logger.info("YouTube authentication successful for state=%s", state)

    # SECURITY: Do NOT return tokens in HTTP response
    # Tokens are stored securely in OS keyring via YouTubeTokenStorage
    return {
        "message": "YouTube authentication successful. Tokens stored securely.",
        "scopes": credentials_info.get("scopes", []),
    }
