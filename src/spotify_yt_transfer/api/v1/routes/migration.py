"""Playlist migration endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool

from spotify_yt_transfer.api.dependencies import get_migration_service, get_playlist_service
from spotify_yt_transfer.schemas import (
    CheckMissingParams,
    CheckMissingResponse,
    MigrateParams,
    MigrateResponse,
)
from spotify_yt_transfer.services import MigrationService, PlaylistService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
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
    params: MigrateParams = Depends(),
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

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Migration failed: {error_msg}")

        # Check for quota exceeded
        if "quota exceeded" in error_msg.lower():
            raise HTTPException(status_code=429, detail=error_msg) from e

        raise HTTPException(status_code=400, detail=error_msg) from e


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
