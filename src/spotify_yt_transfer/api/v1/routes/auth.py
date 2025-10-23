"""Authentication and OAuth callback endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from spotify_yt_transfer.api.dependencies import get_oauth_service
from spotify_yt_transfer.services import OAuthService, OAuthStateError

logger = logging.getLogger(__name__)

router = APIRouter()


def _extract_code_and_state(request: Request) -> tuple[str, str]:
    code = request.query_params.get("code")
    state = request.query_params.get("state")

    if not code:
        logger.error("OAuth callback missing 'code' parameter")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing code parameter in callback.")

    if not state:
        logger.error("OAuth callback missing 'state' parameter")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing state parameter in callback.")

    return code, state


@router.get(
    "/spotify/authorize",
    summary="Get Spotify authorization URL",
    description="Generates a Spotify OAuth2 authorization URL for headless deployments.",
)
async def spotify_authorize(oauth: OAuthService = Depends(get_oauth_service)) -> dict[str, str]:
    """
    Produce a Spotify authorization URL and CSRF state token.

    Returns:
        Dict containing the URL and state value.
    """
    response = oauth.build_spotify_authorize_url()
    return {"authorize_url": response.authorize_url, "state": response.state}


@router.get(
    "/spotify/callback",
    summary="Spotify OAuth2 callback",
    description="Handles Spotify OAuth2 callback by exchanging the code for access tokens.",
)
async def spotify_callback(
    request: Request,
    oauth: OAuthService = Depends(get_oauth_service),
) -> dict[str, Any]:
    """
    Handle Spotify OAuth2 callback and exchange code for tokens.

    Returns:
        Dictionary with success message and token information
    """
    code, state = _extract_code_and_state(request)

    try:
        logger.info("Processing Spotify OAuth callback (state=%s)", state)
        token_info = oauth.exchange_spotify_code(code=code, state=state)
    except OAuthStateError as exc:
        logger.warning("Spotify OAuth state validation failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Spotify authentication failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Authentication failed.") from exc

    logger.info("Spotify authentication successful for state=%s", state)
    return {"message": "Spotify authentication successful", "token_info": token_info}


@router.get(
    "/youtube/authorize",
    summary="Get YouTube authorization URL",
    description="Generates a YouTube OAuth2 authorization URL for headless deployments.",
)
async def youtube_authorize(oauth: OAuthService = Depends(get_oauth_service)) -> dict[str, str]:
    """
    Produce a YouTube authorization URL and CSRF state token.

    Returns:
        Dict containing the URL and state value.
    """
    response = oauth.build_youtube_authorize_url()
    return {"authorize_url": response.authorize_url, "state": response.state}


@router.get(
    "/youtube/callback",
    summary="YouTube OAuth2 callback",
    description="Handles YouTube OAuth2 callback by exchanging the code for access tokens.",
)
async def youtube_callback(
    request: Request,
    oauth: OAuthService = Depends(get_oauth_service),
) -> dict[str, Any]:
    """
    Handle YouTube OAuth2 callback and exchange code for tokens.

    Returns:
        Dictionary with success message and token information
    """
    code, state = _extract_code_and_state(request)

    try:
        logger.info("Processing YouTube OAuth callback (state=%s)", state)
        credentials_info = oauth.exchange_youtube_code(code=code, state=state)
    except OAuthStateError as exc:
        logger.warning("YouTube OAuth state validation failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("YouTube authentication failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Authentication failed.") from exc

    logger.info("YouTube authentication successful for state=%s", state)
    return {"message": "YouTube authentication successful", "credentials": credentials_info}
