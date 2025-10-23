"""Schemas for playlist-related operations."""

from pydantic import BaseModel, Field, constr


class YouTubePlaylistParams(BaseModel):
    """Parameters for retrieving YouTube playlist."""

    playlist_name: constr(min_length=1) = Field(  # type: ignore
        ...,
        description="Name of the YouTube playlist to retrieve",
        examples=["My Favourite Songs"],
    )


class YouTubePlaylistResponse(BaseModel):
    """Response containing YouTube playlist information."""

    playlist_name: str = Field(
        ...,
        description="Name of the YouTube playlist",
        examples=["My Favourite Songs"],
    )
    playlist_id: str = Field(
        ...,
        description="ID of the YouTube playlist",
        examples=["PLabcdef123456"],
    )


class PlaylistInfo(BaseModel):
    """Information about a created playlist."""

    name: str = Field(
        ...,
        description="Name of the playlist",
        examples=["Liked Songs-1"],
    )
    playlist_id: str = Field(
        ...,
        description="Spotify playlist ID",
        examples=["37i9dQZF1DXcBWIGoYBM5M"],
    )
    track_count: int = Field(
        ...,
        description="Number of tracks in playlist",
        examples=[1000],
    )


class SplitLikedSongsParams(BaseModel):
    """Parameters for splitting liked songs into multiple playlists."""

    playlist_base_name: constr(min_length=1) = Field(  # type: ignore
        ...,
        description="Base name for the split playlists. Will be suffixed with '-1', '-2', etc.",
        examples=["Liked Songs"],
    )
    tracks_per_playlist: int = Field(
        1000,
        description="Number of tracks per playlist (default: 1000, max: 10000)",
        examples=[1000],
        ge=1,
        le=10000,
    )
    public: bool = Field(
        False,
        description="Whether the created playlists should be public (default: False)",
        examples=[False],
    )


class SplitLikedSongsResponse(BaseModel):
    """Response after splitting liked songs into multiple playlists."""

    message: str = Field(
        ...,
        description="Success message",
        examples=["Successfully split 5600 liked songs into 6 playlists"],
    )
    total_tracks: int = Field(
        ...,
        description="Total number of liked songs processed",
        examples=[5600],
    )
    playlists_created: list[PlaylistInfo] = Field(
        ...,
        description="List of created playlists with their details",
    )
