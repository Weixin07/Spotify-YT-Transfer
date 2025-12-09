"""SQLAlchemy ORM models for database tables."""

from datetime import datetime, timedelta

from sqlalchemy import DateTime, String, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from spotify_yt_transfer.database.base import Base


class MatchedTrack(Base):
    """
    Stores successfully matched Spotify tracks with their YouTube video IDs.

    This table serves as a cache to avoid redundant YouTube API searches
    for tracks that have already been matched.
    """

    __tablename__ = "matched_tracks"

    spotify_id: Mapped[str] = mapped_column(String, primary_key=True, index=True, nullable=False)
    song_name: Mapped[str] = mapped_column(String, nullable=False)
    artist: Mapped[str] = mapped_column(String, nullable=False)
    album: Mapped[str | None] = mapped_column(String, nullable=True)
    youtube_id: Mapped[str] = mapped_column(String, nullable=False)

    def __repr__(self) -> str:
        return f"<MatchedTrack(spotify_id='{self.spotify_id}', song='{self.song_name}', artist='{self.artist}')>"


class FailedTrack(Base):
    """
    Stores tracks that failed to be added to YouTube playlists.

    Tracks failures for retry mechanisms and debugging purposes.
    """

    __tablename__ = "failed_tracks"

    spotify_id: Mapped[str] = mapped_column(String, primary_key=True, index=True, nullable=False)
    youtube_id: Mapped[str | None] = mapped_column(String, nullable=True)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)

    def __repr__(self) -> str:
        return f"<FailedTrack(spotify_id='{self.spotify_id}', reason='{self.reason}')>"


class OAuthState(Base):
    """
    Stores transient OAuth state tokens for CSRF protection.

    States are automatically purged after their time-to-live window.
    """

    __tablename__ = "oauth_states"

    state: Mapped[str] = mapped_column(String, primary_key=True, index=True, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # TTL in seconds (10 minutes) for state validity
    TTL_SECONDS = 600

    @classmethod
    def is_expired(cls, created_at: datetime | None) -> bool:
        """
        Check whether a stored state has expired.

        Args:
            created_at: Timestamp stored for the state

        Returns:
            True if the state is older than the TTL window.
        """
        if created_at is None:
            return True
        return created_at < datetime.utcnow() - timedelta(seconds=cls.TTL_SECONDS)

    @classmethod
    def purge_expired(cls, db: Session) -> int:
        """
        Delete all expired OAuth states from the database.

        Args:
            db: Active SQLAlchemy session

        Returns:
            Number of deleted rows
        """
        cutoff = datetime.utcnow() - timedelta(seconds=cls.TTL_SECONDS)
        result = db.query(cls).filter(cls.created_at < cutoff).delete()
        db.commit()
        return result

    @classmethod
    def exists(cls, db: Session, state: str, provider: str) -> bool:
        """
        Check if a state exists for the given provider.

        Args:
            db: Active SQLAlchemy session
            state: Random state string
            provider: OAuth provider name

        Returns:
            True if the state exists and is not expired.
        """
        stmt = select(cls.created_at).where(cls.state == state, cls.provider == provider)
        created_at = db.execute(stmt).scalar_one_or_none()
        if created_at is None:
            return False
        if cls.is_expired(created_at):
            db.query(cls).filter(cls.state == state, cls.provider == provider).delete()
            db.commit()
            return False
        return True
