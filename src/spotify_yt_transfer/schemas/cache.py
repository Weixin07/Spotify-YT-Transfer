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


class AuditMatchedTracksRequest(BaseModel):
    """Options for auditing cached matched tracks."""

    remove_flagged: bool = Field(
        False,
        description="Delete matched tracks whose YouTube titles contain disallowed terms.",
    )


class AuditMatchedTrack(BaseModel):
    """A matched track flagged for containing disallowed terms."""

    spotify_id: str = Field(..., description="Spotify track ID associated with the match.")
    youtube_id: str = Field(..., description="YouTube video ID currently cached.")
    title: str = Field(..., description="Current YouTube video title.")
    song_name: str = Field(..., description="Cached Spotify track name.")
    artist: str = Field(..., description="Cached Spotify artist.")


class AuditMatchedTracksResponse(BaseModel):
    """Summary of matched-track audit results."""

    total_checked: int = Field(..., description="Total matched tracks inspected.")
    flagged_count: int = Field(..., description="Number of tracks containing disallowed terms.")
    removed_count: int = Field(..., description="Number of flagged tracks removed from cache.")
    flagged: list[AuditMatchedTrack] = Field(
        default_factory=list,
        description="Details of flagged cached matches.",
    )
