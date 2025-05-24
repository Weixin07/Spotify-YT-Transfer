from fastapi import Query
from pydantic import BaseModel, Field, constr, PositiveInt
from typing import Optional, List


class MigrateParams(BaseModel):
    spotify_playlist_id: Optional[str] = Query(
        None,
        description="Spotify playlist ID to migrate. If omitted, will migrate Liked Songs instead.",
    )
    youtube_playlist_title: constr(min_length=1) = Field(
        ..., description="Title for the new YouTube playlist"
    )


class MigrateResponse(BaseModel):
    message: str = Field(..., description="Success message")
    youtube_playlist_id: str = Field(..., description="Created YouTube playlist ID")


class CheckMissingParams(BaseModel):
    spotify_playlist_id: constr(min_length=1)
    youtube_playlist_id: constr(min_length=1)


class MissingTrack(BaseModel):
    unique_id: str
    track_name: str
    artist: str
    album: Optional[str] = None
    cached_youtube_id: Optional[str] = None


class DuplicateTrack(BaseModel):
    unique_id: str
    count: PositiveInt


class UnavailableTrack(BaseModel):
    name: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    duration_ms: Optional[int] = None


class CheckMissingResponse(BaseModel):
    missing_tracks: List[MissingTrack]
    duplicate_tracks: List[DuplicateTrack]
    unavailable_tracks: List[UnavailableTrack]


class YouTubePlaylistParams(BaseModel):
    playlist_name: constr(min_length=1)


class YouTubePlaylistResponse(BaseModel):
    playlist_name: str
    playlist_id: str
