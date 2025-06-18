from fastapi import Query
from pydantic import BaseModel, Field, constr, PositiveInt
from typing import Optional, List


class MigrateParams(BaseModel):
    spotify_playlist_id: Optional[str] = Query(
        None,
        description="Spotify playlist ID to migrate. If omitted, will migrate Liked Songs instead.",
        example="37i9dQZF1DXcBWIGoYBM5M",
    )
    youtube_playlist_title: constr(min_length=1) = Field(
        ...,
        example="My Favorite Playlist",
        description="Title for the new YouTube playlist",
    )


class MigrateResponse(BaseModel):
    message: str = Field(
        ..., example="Migration complete", description="Success message"
    )
    youtube_playlist_id: str = Field(
        ..., example="PL1234567890abcdef", description="Created YouTube playlist ID"
    )


class CheckMissingParams(BaseModel):
    spotify_playlist_id: constr(min_length=1) = Field(
        ...,
        example="37i9dQZF1DXcBWIGoYBM5M",
        description="Spotify playlist ID to compare",
    )
    youtube_playlist_id: constr(min_length=1) = Field(
        ..., example="PLabcdef123456", description="YouTube playlist ID to compare"
    )


class MissingTrack(BaseModel):
    unique_id: str = Field(
        ...,
        example="Shape of You|Ed Sheeran",
        description="Unique combination of track name and artist",
    )
    track_name: str = Field(
        ..., example="Shape of You", description="Name of the track"
    )
    artist: str = Field(..., example="Ed Sheeran", description="Artist of the track")
    album: Optional[str] = Field(None, example="Divide", description="Album name")
    cached_youtube_id: Optional[str] = Field(
        None, example="dQw4w9WgXcQ", description="Cached YouTube video ID"
    )


class DuplicateTrack(BaseModel):
    unique_id: str = Field(
        ...,
        example="Shape of You|Ed Sheeran",
        description="Unique ID for track to detect duplicates",
    )
    count: PositiveInt = Field(
        ..., example=2, description="Number of duplicate occurrences"
    )


class UnavailableTrack(BaseModel):
    name: Optional[str] = Field(
        None, example=None, description="Name of unavailable track"
    )
    artist: Optional[str] = Field(None, example=None, description="Artist if known")
    album: Optional[str] = Field(None, example=None, description="Album if known")
    duration_ms: Optional[int] = Field(
        None, example=210000, description="Duration of track in milliseconds"
    )


class CheckMissingResponse(BaseModel):
    missing_tracks: List[MissingTrack]
    duplicate_tracks: List[DuplicateTrack]
    unavailable_tracks: List[UnavailableTrack]


class YouTubePlaylistParams(BaseModel):
    playlist_name: constr(min_length=1) = Field(
        ...,
        example="My Favourite Songs",
        description="Name of the YouTube playlist to retrieve",
    )


class YouTubePlaylistResponse(BaseModel):
    playlist_name: str = Field(
        ..., example="My Favourite Songs", description="Name of the YouTube playlist"
    )
    playlist_id: str = Field(
        ..., example="PLabcdef123456", description="ID of the YouTube playlist"
    )
