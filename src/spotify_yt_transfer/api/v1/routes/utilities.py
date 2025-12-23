"""Utility endpoints for playlist operations."""

import logging

import requests
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from spotipy.client import SpotifyException

from spotify_yt_transfer.api.dependencies import (
    get_cache_service,
    get_playlist_service,
    get_youtube_client,
)
from spotify_yt_transfer.api.errors import ErrorCodes, error_response
from spotify_yt_transfer.clients import YouTubeClient
from spotify_yt_transfer.schemas import (
    AuditMatchedTracksRequest,
    AuditMatchedTracksResponse,
    CacheInvalidateRequest,
    CacheInvalidateResponse,
    PlaylistInfo,
    SplitLikedSongsParams,
    SplitLikedSongsResponse,
    YouTubePlaylistParams,
    YouTubePlaylistResponse,
)
from spotify_yt_transfer.services import (
    CacheService,
    PlaylistService,
    QuotaExceededError,
    ServiceError,
    ValidationServiceError,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/youtube/playlist",
    response_model=YouTubePlaylistResponse,
    summary="Get YouTube playlist by name",
    description="Retrieves the YouTube playlist ID for a given playlist name in the user's account",
    responses={
        200: {
            "description": "Playlist found",
            "content": {
                "application/json": {
                    "example": {
                        "playlist_name": "My Favourite Songs",
                        "playlist_id": "PLabcdef123456",
                    }
                }
            },
        },
        404: {
            "description": "Playlist not found",
            "content": {
                "application/json": {
                    "example": {
                        "detail": {
                            "code": "playlist_not_found",
                            "message": "Playlist 'My Playlist' not found.",
                        }
                    }
                }
            },
        },
    },
)
async def get_youtube_playlist_id(
    params: YouTubePlaylistParams = Depends(),
    yt: YouTubeClient = Depends(get_youtube_client),
) -> YouTubePlaylistResponse:
    """
    Retrieve YouTube playlist ID by name.

    Args:
        params: Playlist name parameters
        yt: YouTube client dependency

    Returns:
        Playlist name and ID

    Raises:
        HTTPException: If playlist not found
    """
    logger.info(f"Searching for YouTube playlist: {params.playlist_name}")

    playlist_id = await run_in_threadpool(yt.find_playlist_by_name, params.playlist_name)

    if playlist_id:
        return YouTubePlaylistResponse(playlist_name=params.playlist_name, playlist_id=playlist_id)
    else:
        raise HTTPException(
            status_code=404,
            detail=error_response(
                ErrorCodes.PLAYLIST_NOT_FOUND,
                "Playlist not found",
                {"playlist_name": params.playlist_name},
            ),
        )


@router.post(
    "/split-liked-songs",
    response_model=SplitLikedSongsResponse,
    summary="Split liked songs into multiple playlists",
    description=(
        "Splits the user's Spotify liked songs into multiple playlists with a "
        "specified number of tracks per playlist"
    ),
    responses={
        200: {
            "description": "Liked songs split successfully",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Successfully split 5600 liked songs into 6 playlists",
                        "total_tracks": 5600,
                        "playlists_created": [
                            {"name": "Liked Songs-1", "playlist_id": "abc123", "track_count": 1000}
                        ],
                    }
                }
            },
        },
        422: {
            "description": "Validation error for invalid parameters",
            "content": {
                "application/json": {
                    "example": {
                        "detail": {
                            "code": "validation_error",
                            "message": "Tracks per playlist must be between 1 and 10000",
                            "details": {"field": "tracks_per_playlist"},
                        }
                    }
                }
            },
        },
        502: {
            "description": "External service error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": {
                            "code": "external_service_error",
                            "message": "Spotify API failure",
                            "details": {"reason": "..."},
                        }
                    }
                }
            },
        },
    },
)
async def split_liked_songs(
    params: SplitLikedSongsParams,
    service: PlaylistService = Depends(get_playlist_service),
) -> SplitLikedSongsResponse:
    """
    Split user's liked songs into multiple playlists.

    Args:
        params: Split parameters (base name, tracks per playlist, public flag)
        service: Playlist service dependency

    Returns:
        Result with total tracks and created playlists

    Raises:
        HTTPException: On API errors
    """
    logger.info(
        f"Splitting liked songs: {params.tracks_per_playlist} tracks per playlist, "
        f"base name: {params.playlist_base_name}"
    )

    try:
        result = await run_in_threadpool(
            service.split_liked_songs,
            params.playlist_base_name,
            params.tracks_per_playlist,
            params.public,
        )

        playlists = [PlaylistInfo(**p) for p in result["playlists_created"]]

        return SplitLikedSongsResponse(
            message=f"Successfully split {result['total_tracks']} liked songs into {len(playlists)} playlists",
            total_tracks=result["total_tracks"],
            playlists_created=playlists,
        )

    except ValidationServiceError as exc:
        logger.warning("Validation error while splitting liked songs: %s", exc)
        raise HTTPException(
            status_code=422,
            detail=error_response(exc.code, str(exc), exc.details),
        ) from exc
    except ValueError as exc:
        logger.warning("Invalid parameters for splitting liked songs: %s", exc)
        raise HTTPException(
            status_code=422,
            detail=error_response(ErrorCodes.VALIDATION_ERROR, str(exc)),
        ) from exc
    except SpotifyException as exc:
        logger.error("Spotify API failure while splitting liked songs: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=502,
            detail=error_response(
                ErrorCodes.EXTERNAL_SERVICE_ERROR, "Spotify API failure", {"reason": str(exc)}
            ),
        ) from exc
    except ServiceError as exc:
        logger.error("Service error while splitting liked songs: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=error_response(exc.code, str(exc), exc.details),
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error splitting liked songs")
        raise HTTPException(
            status_code=500,
            detail=error_response(
                ErrorCodes.UNEXPECTED_ERROR, "Unexpected error splitting liked songs"
            ),
        ) from exc


@router.get(
    "/download-cover",
    summary="Download playlist cover image",
    description="Downloads the cover image of a Spotify playlist",
    responses={
        200: {
            "description": "Cover image (JPEG)",
            "content": {"image/jpeg": {}},
        },
        404: {
            "description": "Cover image not found for the given playlist ID",
            "content": {
                "application/json": {
                    "example": {
                        "detail": {
                            "code": "cover_not_found",
                            "message": "No cover image found for this playlist",
                            "details": {"playlist_id": "..."},
                        }
                    }
                }
            },
        },
        422: {
            "description": "Validation error for invalid playlist ID",
            "content": {
                "application/json": {
                    "example": {
                        "detail": {
                            "code": "validation_error",
                            "message": "Invalid playlist ID format",
                            "details": {"field": "playlist_id"},
                        }
                    }
                }
            },
        },
        502: {
            "description": "External service error when downloading the image",
            "content": {
                "application/json": {
                    "example": {
                        "detail": {
                            "code": "external_service_error",
                            "message": "Image download failed",
                            "details": {"reason": "..."},
                        }
                    }
                }
            },
        },
    },
)
async def download_cover(
    playlist_id: str,
    filename: str = "cover.jpg",
    service: PlaylistService = Depends(get_playlist_service),
) -> Response:
    """
    Download Spotify playlist cover image.

    Args:
        playlist_id: Spotify playlist ID
        filename: Optional filename for download
        service: Playlist service dependency

    Returns:
        JPEG image as streaming response

    Raises:
        HTTPException: If cover image not found or download fails
    """
    logger.info(f"Downloading cover for playlist: {playlist_id}")

    try:
        image_bytes = await run_in_threadpool(
            service.download_playlist_cover,
            playlist_id,
        )

        return StreamingResponse(
            iter([image_bytes]),
            media_type="image/jpeg",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except ValueError as exc:
        logger.info("No cover image found for playlist %s: %s", playlist_id, exc)
        raise HTTPException(
            status_code=404,
            detail=error_response(
                ErrorCodes.COVER_NOT_FOUND, str(exc), {"playlist_id": playlist_id}
            ),
        ) from exc
    except requests.RequestException as exc:
        logger.error("HTTP error while downloading cover: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=502,
            detail=error_response(
                ErrorCodes.EXTERNAL_SERVICE_ERROR, "Image download failed", {"reason": str(exc)}
            ),
        ) from exc
    except ServiceError as exc:
        logger.error("Service error while downloading cover: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=error_response(exc.code, str(exc), exc.details),
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error downloading cover")
        raise HTTPException(
            status_code=500,
            detail=error_response(
                ErrorCodes.UNEXPECTED_ERROR, "Unexpected error downloading cover"
            ),
        ) from exc


@router.post(
    "/cache/invalidate",
    response_model=CacheInvalidateResponse,
    summary="Invalidate cached data",
    description=(
        "Clears cached Spotify-to-YouTube matches, failed track logs, and the in-memory "
        "YouTube search cache. Useful when playlists have changed or cached results appear stale."
    ),
    responses={
        200: {
            "description": "Caches invalidated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "matched_tracks_removed": 12,
                        "failed_tracks_removed": 4,
                        "youtube_cache_cleared": True,
                    }
                }
            },
        },
    },
)
async def invalidate_cache(
    options: CacheInvalidateRequest,
    service: CacheService = Depends(get_cache_service),
) -> CacheInvalidateResponse:
    """
    Invalidate cached data such as matched tracks and YouTube search results.

    Args:
        options: Cache invalidation options
        service: Cache service dependency

    Returns:
        Summary of invalidation actions
    """
    logger.info(
        "Invalidating caches (matched_tracks=%s, failed_tracks=%s, youtube=%s)",
        options.matched_tracks,
        options.failed_tracks,
        options.youtube_search,
    )

    try:
        result = await run_in_threadpool(
            service.invalidate,
            options.youtube_search,
            options.matched_tracks,
            options.failed_tracks,
        )

        service.repository.commit()

        response = CacheInvalidateResponse(
            matched_tracks_removed=result.matched_tracks_removed,
            failed_tracks_removed=result.failed_tracks_removed,
            youtube_cache_cleared=result.youtube_cache_cleared,
        )

        logger.info("Cache invalidation complete: %s", response.model_dump())
        return response
    except ValidationServiceError as exc:
        logger.warning("Cache invalidation validation error: %s", exc)
        raise HTTPException(
            status_code=422,
            detail=error_response(exc.code, str(exc), exc.details),
        ) from exc
    except ServiceError as exc:
        logger.error("Cache invalidation service error: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=error_response(exc.code, str(exc), exc.details),
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error invalidating cache")
        raise HTTPException(
            status_code=500,
            detail=error_response(
                ErrorCodes.UNEXPECTED_ERROR, "Unexpected error invalidating cache"
            ),
        ) from exc


@router.post(
    "/cache/audit-matched-tracks",
    response_model=AuditMatchedTracksResponse,
    summary="Audit cached matches for disallowed terms",
    description=(
        "Scans cached matched tracks and reports any whose YouTube titles contain disallowed terms. "
        "Optionally deletes flagged matches to force re-matching on the next run."
    ),
)
async def audit_matched_tracks(
    options: AuditMatchedTracksRequest,
    service: CacheService = Depends(get_cache_service),
) -> AuditMatchedTracksResponse:
    """
    Inspect cached matched tracks for disallowed terms and optionally remove them.
    """
    logger.info("Auditing matched tracks (remove_flagged=%s)", options.remove_flagged)

    try:
        result = await run_in_threadpool(service.audit_matched_tracks, options.remove_flagged)
        service.repository.commit()

        response = AuditMatchedTracksResponse(
            total_checked=result.total_checked,
            flagged_count=len(result.flagged),
            removed_count=result.removed,
            flagged=[
                {
                    "spotify_id": item.spotify_id,
                    "youtube_id": item.youtube_id,
                    "title": item.title,
                    "song_name": item.song_name,
                    "artist": item.artist,
                }
                for item in result.flagged
            ],
        )

        logger.info(
            "Audit complete: checked=%s flagged=%s removed=%s",
            response.total_checked,
            response.flagged_count,
            response.removed_count,
        )

        return response
    except QuotaExceededError as exc:
        logger.warning("Audit aborted due to quota exhaustion: %s", exc)
        raise HTTPException(
            status_code=429,
            detail=error_response(exc.code, str(exc), exc.details),
        ) from exc
    except ServiceError as exc:
        logger.error("Audit service error: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=error_response(exc.code, str(exc), exc.details),
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error auditing matched tracks")
        raise HTTPException(
            status_code=500,
            detail=error_response(
                ErrorCodes.UNEXPECTED_ERROR, "Unexpected error auditing matched tracks"
            ),
        ) from exc
