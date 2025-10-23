"""Schemas related to cache management endpoints."""

from pydantic import BaseModel, Field


class CacheInvalidateRequest(BaseModel):
    """Options for invalidating cached data."""

    matched_tracks: bool = Field(
        True,
        description="Purge cached Spotify-to-YouTube matches stored in the database.",
    )
    failed_tracks: bool = Field(
        False,
        description="Purge failed-track retry records stored in the database.",
    )
    youtube_search: bool = Field(
        True,
        description="Clear the in-memory YouTube search results cache.",
    )


class CacheInvalidateResponse(BaseModel):
    """Summary response after invalidating caches."""

    matched_tracks_removed: int = Field(
        ...,
        description="Number of matched-track cache rows removed from the database.",
    )
    failed_tracks_removed: int = Field(
        ...,
        description="Number of failed-track records removed from the database.",
    )
    youtube_cache_cleared: bool = Field(
        ...,
        description="Whether the in-memory YouTube search cache was cleared.",
    )
