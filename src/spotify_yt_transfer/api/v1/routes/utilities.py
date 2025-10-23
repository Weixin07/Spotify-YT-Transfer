"""Utility endpoints for playlist operations."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from spotify_yt_transfer.api.dependencies import get_cache_service, get_playlist_service, get_youtube_client
from spotify_yt_transfer.clients import YouTubeClient
from spotify_yt_transfer.schemas import (
    CacheInvalidateRequest,
    CacheInvalidateResponse,
    PlaylistInfo,
    SplitLikedSongsParams,
    SplitLikedSongsResponse,
    YouTubePlaylistParams,
    YouTubePlaylistResponse,
)
from spotify_yt_transfer.services import CacheService, PlaylistService

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
            "content": {"application/json": {"example": {"detail": "Playlist 'Foo' not found."}}},
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
        raise HTTPException(status_code=404, detail=f"Playlist '{params.playlist_name}' not found.")


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
        400: {
            "description": "Error splitting liked songs",
            "content": {
                "application/json": {"example": {"detail": "Error creating playlists: ..."}}
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

    except Exception as e:
        logger.error(f"Error splitting liked songs: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get(
    "/download-cover",
    summary="Download playlist cover image",
    description="Downloads the cover image of a Spotify playlist",
    responses={
        200: {
            "description": "Cover image (JPEG)",
            "content": {"image/jpeg": {}},
        },
        400: {
            "description": "Error downloading cover",
            "content": {"application/json": {"example": {"detail": "No cover image found"}}},
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

    except ValueError as e:
        logger.error(f"No cover image found: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Error downloading cover: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e


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

    result = await run_in_threadpool(
        service.invalidate,
        options.youtube_search,
        options.matched_tracks,
        options.failed_tracks,
    )

    response = CacheInvalidateResponse(
        matched_tracks_removed=result.matched_tracks_removed,
        failed_tracks_removed=result.failed_tracks_removed,
        youtube_cache_cleared=result.youtube_cache_cleared,
    )

    logger.info("Cache invalidation complete: %s", response.model_dump())
    return response
