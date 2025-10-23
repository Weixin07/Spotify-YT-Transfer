"""Pydantic schemas for request/response validation."""

from spotify_yt_transfer.schemas.cache import CacheInvalidateRequest, CacheInvalidateResponse
from spotify_yt_transfer.schemas.migration import (
    CheckMissingParams,
    CheckMissingResponse,
    DuplicateTrack,
    MigrateParams,
    MigrateResponse,
    MissingTrack,
    UnavailableTrack,
)
from spotify_yt_transfer.schemas.playlist import (
    PlaylistInfo,
    SplitLikedSongsParams,
    SplitLikedSongsResponse,
    YouTubePlaylistParams,
    YouTubePlaylistResponse,
)

__all__ = [
    # Cache schemas
    "CacheInvalidateRequest",
    "CacheInvalidateResponse",
    # Migration schemas
    "MigrateParams",
    "MigrateResponse",
    "CheckMissingParams",
    "CheckMissingResponse",
    "MissingTrack",
    "DuplicateTrack",
    "UnavailableTrack",
    # Playlist schemas
    "YouTubePlaylistParams",
    "YouTubePlaylistResponse",
    "SplitLikedSongsParams",
    "SplitLikedSongsResponse",
    "PlaylistInfo",
]
