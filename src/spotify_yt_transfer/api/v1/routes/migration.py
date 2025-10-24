"""Playlist migration endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from googleapiclient.errors import HttpError
from spotipy.client import SpotifyException

from spotify_yt_transfer.api.dependencies import get_migration_service, get_playlist_service
from spotify_yt_transfer.clients.errors import OAuthCredentialsMissing
from spotify_yt_transfer.schemas import (
    CheckMissingParams,
    CheckMissingResponse,
    MigrateParams,
    MigrateResponse,
)
from spotify_yt_transfer.services import (
    MigrationService,
    PlaylistService,
    QuotaExceededError,
    ServiceError,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _error_payload(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"code": code, "message": message}
    if details:
        payload["details"] = details
    return payload


@router.post(
    "/migrate",
    response_model=MigrateResponse,
    summary="Migrate Spotify playlist to YouTube",
    description=(
        "Migrates a Spotify playlist (or liked songs if no playlist ID is provided) "
        "to a YouTube Music playlist"
    ),
    responses={
        200: {
            "description": "Migration completed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Migration complete",
                        "youtube_playlist_id": "PL1234567890abcdef",
                    }
                }
            },
        },
        400: {
            "description": "Invalid request or API error",
            "content": {
                "application/json": {"example": {"detail": "Error retrieving Spotify tracks: ..."}}
            },
        },
        429: {
            "description": "YouTube API quota exceeded",
            "content": {"application/json": {"example": {"detail": "YouTube API quota exceeded"}}},
        },
    },
)
async def migrate_playlist(
    params: MigrateParams,
    service: MigrationService = Depends(get_migration_service),
) -> dict[str, str]:
    """
    Migrate a Spotify playlist to YouTube Music.

    Given either a Spotify playlist ID or the user's liked songs, this endpoint:
    1. Retrieves tracks from Spotify
    2. Finds or creates a YouTube playlist
    3. Searches YouTube for each track and adds videos to the playlist
    4. Handles failures and retries

    Args:
        params: Migration parameters (Spotify playlist ID and YouTube playlist title)
        service: Migration service dependency

    Returns:
        Dictionary with migration status and YouTube playlist ID

    Raises:
        HTTPException: On API errors, quota exceeded, or authentication issues
    """
    logger.info(
        f"Received migration request for playlist: {params.spotify_playlist_id or 'Liked Songs'}"
    )

    try:
        result = await run_in_threadpool(
            service.migrate_playlist,
            params.youtube_playlist_title,
            params.spotify_playlist_id,
        )
        return result

    except QuotaExceededError as exc:
        logger.warning("Migration aborted due to quota exhaustion: %s", exc)
        raise HTTPException(
            status_code=429,
            detail=_error_payload(exc.code, str(exc), exc.details),
        ) from exc
    except OAuthCredentialsMissing as exc:
        logger.warning("Migration requires refreshed OAuth credentials: %s", exc)
        raise HTTPException(
            status_code=401,
            detail=_error_payload("oauth_credentials_missing", str(exc)),
        ) from exc
    except (SpotifyException, HttpError) as exc:
        logger.error("Upstream API failure during migration: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=502,
            detail=_error_payload("external_service_error", "Upstream API failure", {"reason": str(exc)}),
        ) from exc
    except ServiceError as exc:
        logger.error("Migration service error: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=_error_payload(exc.code, str(exc), exc.details),
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected migration failure")
        raise HTTPException(
            status_code=500,
            detail=_error_payload("unexpected_error", "Unexpected migration failure"),
        ) from exc


@router.get(
    "/check-missing",
    response_model=CheckMissingResponse,
    summary="Check for missing tracks",
    description=(
        "Compares a Spotify playlist with a YouTube playlist and returns "
        "tracks that are missing, duplicated, or unavailable"
    ),
    responses={
        200: {
            "description": "Comparison results",
            "content": {
                "application/json": {
                    "example": {
                        "missing_tracks": [
                            {
                                "unique_id": "Song|Artist",
                                "track_name": "Song",
                                "artist": "Artist",
                                "album": "Album",
                                "cached_youtube_id": "abcd1234",
                            }
                        ],
                        "duplicate_tracks": [{"unique_id": "Song|Artist", "count": 2}],
                        "unavailable_tracks": [
                            {"name": "Song", "artist": None, "album": None, "duration_ms": None}
                        ],
                    }
                }
            },
        },
        400: {
            "description": "Invalid request",
            "content": {"application/json": {"example": {"detail": "Invalid playlist IDs"}}},
        },
    },
)
async def check_missing_tracks(
    params: CheckMissingParams = Depends(),
    service: PlaylistService = Depends(get_playlist_service),
) -> CheckMissingResponse:
    """
    Compare Spotify and YouTube playlists to find missing tracks.

    Args:
        params: Spotify and YouTube playlist IDs
        service: Playlist service dependency

    Returns:
        Comparison results with missing, duplicate, and unavailable tracks

    Raises:
        HTTPException: On API errors or invalid playlist IDs
    """
    logger.info(
        f"Checking missing tracks: Spotify={params.spotify_playlist_id}, "
        f"YouTube={params.youtube_playlist_id}"
    )

    try:
        result = await run_in_threadpool(
            service.find_missing_tracks,
            params.spotify_playlist_id,
            params.youtube_playlist_id,
        )
        return CheckMissingResponse(**result)

    except Exception as e:
        logger.error(f"Error checking missing tracks: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
