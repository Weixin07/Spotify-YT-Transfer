"""Schemas for migration-related operations."""

from pydantic import BaseModel, Field, constr


class MigrateParams(BaseModel):
    """Parameters for playlist migration."""

    spotify_playlist_id: str | None = Field(
        None,
        description="Spotify playlist ID to migrate. If omitted, will migrate Liked Songs instead.",
        examples=["37i9dQZF1DXcBWIGoYBM5M"],
    )
    youtube_playlist_title: constr(min_length=1) = Field(  # type: ignore
        ...,
        description="Title for the new YouTube playlist",
        examples=["My Favorite Playlist"],
    )


class MigrateResponse(BaseModel):
    """Response after successful migration."""

    message: str = Field(
        ...,
        description="Success message",
        examples=["Migration complete"],
    )
    youtube_playlist_id: str = Field(
        ...,
        description="Created YouTube playlist ID",
        examples=["PL1234567890abcdef"],
    )


class MissingTrack(BaseModel):
    """Track that exists in Spotify playlist but not in YouTube playlist."""

    unique_id: str = Field(
        ...,
        description="Unique combination of track name and artist",
        examples=["Shape of You|Ed Sheeran"],
    )
    track_name: str = Field(
        ...,
        description="Name of the track",
        examples=["Shape of You"],
    )
    artist: str = Field(
        ...,
        description="Artist of the track",
        examples=["Ed Sheeran"],
    )
    album: str | None = Field(
        None,
        description="Album name",
        examples=["Divide"],
    )
    cached_youtube_id: str | None = Field(
        None,
        description="Cached YouTube video ID",
        examples=["dQw4w9WgXcQ"],
    )


class DuplicateTrack(BaseModel):
    """Track that appears multiple times in the playlist."""

    unique_id: str = Field(
        ...,
        description="Unique ID for track to detect duplicates",
        examples=["Shape of You|Ed Sheeran"],
    )
    count: int = Field(
        ...,
        description="Number of duplicate occurrences",
        examples=[2],
        ge=2,
    )


class UnavailableTrack(BaseModel):
    """Track with missing or incomplete metadata."""

    name: str | None = Field(
        None,
        description="Name of unavailable track",
    )
    artist: str | None = Field(
        None,
        description="Artist if known",
    )
    album: str | None = Field(
        None,
        description="Album if known",
    )
    duration_ms: int | None = Field(
        None,
        description="Duration of track in milliseconds",
        examples=[210000],
    )


class CheckMissingParams(BaseModel):
    """Parameters for checking missing tracks between playlists."""

    spotify_playlist_id: constr(min_length=1) = Field(  # type: ignore
        ...,
        description="Spotify playlist ID to compare",
        examples=["37i9dQZF1DXcBWIGoYBM5M"],
    )
    youtube_playlist_id: constr(min_length=1) = Field(  # type: ignore
        ...,
        description="YouTube playlist ID to compare",
        examples=["PLabcdef123456"],
    )


class CheckMissingResponse(BaseModel):
    """Response containing comparison results between Spotify and YouTube playlists."""

    missing_tracks: list[MissingTrack] = Field(
        ...,
        description="Tracks in Spotify playlist but not in YouTube playlist",
    )
    duplicate_tracks: list[DuplicateTrack] = Field(
        ...,
        description="Tracks that appear multiple times in the Spotify playlist",
    )
    unavailable_tracks: list[UnavailableTrack] = Field(
        ...,
        description="Tracks with missing or incomplete metadata",
    )
