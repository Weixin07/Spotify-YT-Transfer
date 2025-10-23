"""SQLAlchemy ORM models for database tables."""

from sqlalchemy import Column, String

from spotify_yt_transfer.database.base import Base


class MatchedTrack(Base):
    """
    Stores successfully matched Spotify tracks with their YouTube video IDs.

    This table serves as a cache to avoid redundant YouTube API searches
    for tracks that have already been matched.
    """

    __tablename__ = "matched_tracks"

    spotify_id = Column(String, primary_key=True, index=True, nullable=False)
    song_name = Column(String, nullable=False)
    artist = Column(String, nullable=False)
    album = Column(String, nullable=True)
    youtube_id = Column(String, nullable=False)

    def __repr__(self) -> str:
        return f"<MatchedTrack(spotify_id='{self.spotify_id}', song='{self.song_name}', artist='{self.artist}')>"


class FailedTrack(Base):
    """
    Stores tracks that failed to be added to YouTube playlists.

    Tracks failures for retry mechanisms and debugging purposes.
    """

    __tablename__ = "failed_tracks"

    spotify_id = Column(String, primary_key=True, index=True, nullable=False)
    youtube_id = Column(String, nullable=True)
    reason = Column(String, nullable=True)

    def __repr__(self) -> str:
        return f"<FailedTrack(spotify_id='{self.spotify_id}', reason='{self.reason}')>"
