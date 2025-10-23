"""Authentication and OAuth callback endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from spotipy.oauth2 import SpotifyOAuth

from spotify_yt_transfer.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/spotify/callback",
    summary="Spotify OAuth2 callback",
    description="Handles Spotify OAuth2 callback by exchanging the code for access tokens",
    responses={
        200: {
            "description": "Authentication successful",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Spotify authentication successful",
                        "token_info": {"access_token": "BQD...xyz"},
                    }
                }
            },
        },
        400: {
            "description": "Missing or invalid code parameter",
            "content": {
                "application/json": {"example": {"detail": "Missing code parameter in callback."}}
            },
        },
    },
)
async def spotify_callback(request: Request) -> dict[str, Any]:
    """
    Handle Spotify OAuth2 callback and exchange code for tokens.

    Args:
        request: The incoming HTTP request with query parameters

    Returns:
        Dictionary with success message and token information

    Raises:
        HTTPException: If code parameter is missing or authentication fails
    """
    code = request.query_params.get("code")

    if not code:
        logger.error("Spotify callback: Missing 'code' parameter")
        raise HTTPException(status_code=400, detail="Missing code parameter in callback.")

    try:
        logger.info("Processing Spotify callback with code received")

        spotify_auth_manager = SpotifyOAuth(
            client_id=settings.spotify.client_id,
            client_secret=settings.spotify.client_secret,
            redirect_uri=settings.spotify.redirect_uri,
            scope="playlist-read-private user-library-read playlist-modify-private playlist-modify-public",
        )

        # Exchange code for token (runs in sync, so wrap if needed in production)
        token_info = spotify_auth_manager.get_access_token(code)

        logger.info("Spotify authentication successful")
        return {"message": "Spotify authentication successful", "token_info": token_info}

    except Exception as e:
        logger.error(f"Spotify authentication failed: {e}")
        raise HTTPException(status_code=400, detail=f"Authentication failed: {str(e)}") from e
