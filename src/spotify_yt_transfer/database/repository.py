"""Repository pattern for database operations."""

import logging

from sqlalchemy.orm import Session

from spotify_yt_transfer.database.models import FailedTrack, MatchedTrack

logger = logging.getLogger(__name__)


class TrackRepository:
    """
    Repository for track-related database operations.

    Provides a clean abstraction layer over SQLAlchemy operations.
    """

    def __init__(self, db: Session):
        """
        Initialize repository with a database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    # ===== MatchedTrack Operations =====

    def get_matched_track(self, spotify_id: str) -> MatchedTrack | None:
        """
        Retrieve a matched track by Spotify ID.

        Args:
            spotify_id: Spotify track identifier

        Returns:
            MatchedTrack if found, None otherwise
        """
        return self.db.query(MatchedTrack).filter_by(spotify_id=spotify_id).first()

    def save_matched_track(
        self,
        spotify_id: str,
        song_name: str,
        artist: str,
        youtube_id: str,
        album: str | None = None,
    ) -> MatchedTrack:
        """
        Save or update a matched track.

        Args:
            spotify_id: Spotify track identifier
            song_name: Track name
            artist: Artist name
            youtube_id: YouTube video identifier
            album: Album name (optional)

        Returns:
            The saved MatchedTrack instance
        """
        existing = self.get_matched_track(spotify_id)

        if existing:
            # Update existing record
            existing.song_name = song_name
            existing.artist = artist
            existing.album = album
            existing.youtube_id = youtube_id
            track = existing
            logger.debug("Updated matched track: %s -> %s", spotify_id, youtube_id)
        else:
            # Create new record
            track = MatchedTrack(
                spotify_id=spotify_id,
                song_name=song_name,
                artist=artist,
                album=album,
                youtube_id=youtube_id,
            )
            self.db.add(track)
            logger.debug("Saved new matched track: %s -> %s", spotify_id, youtube_id)

        self.db.commit()
        self.db.refresh(track)
        return track

    def delete_all_matched_tracks(self) -> int:
        """
        Remove all cached matched tracks.

        Returns:
            Number of records removed
        """
        deleted = self.db.query(MatchedTrack).delete()
        self.db.commit()
        logger.info("Removed %s matched track cache entries", deleted)
        return deleted

    def get_all_matched_tracks(self) -> list[MatchedTrack]:
        """
        Retrieve all matched tracks from the database.

        Returns:
            List of all MatchedTrack instances
        """
        return self.db.query(MatchedTrack).all()

    # ===== FailedTrack Operations =====

    def get_failed_track(self, spotify_id: str) -> FailedTrack | None:
        """
        Retrieve a failed track by Spotify ID.

        Args:
            spotify_id: Spotify track identifier

        Returns:
            FailedTrack if found, None otherwise
        """
        return self.db.query(FailedTrack).filter_by(spotify_id=spotify_id).first()

    def record_failed_track(
        self,
        spotify_id: str,
        youtube_id: str | None = None,
        reason: str | None = None,
    ) -> FailedTrack:
        """
        Record a track that failed to be added to a playlist.

        Args:
            spotify_id: Spotify track identifier
            youtube_id: YouTube video identifier (if known)
            reason: Reason for failure

        Returns:
            The saved FailedTrack instance
        """
        existing = self.get_failed_track(spotify_id)

        if existing:
            existing.youtube_id = youtube_id
            existing.reason = reason
            track = existing
            logger.debug("Updated failed track: %s", spotify_id)
        else:
            track = FailedTrack(
                spotify_id=spotify_id,
                youtube_id=youtube_id,
                reason=reason,
            )
            self.db.add(track)
            logger.debug("Recorded new failed track: %s", spotify_id)

        self.db.commit()
        self.db.refresh(track)
        return track

    def clear_failed_track(self, spotify_id: str) -> bool:
        """
        Remove a track from the failed tracks table.

        Useful when a previously failed track succeeds on retry.

        Args:
            spotify_id: Spotify track identifier

        Returns:
            True if a record was deleted, False otherwise
        """
        failed = self.get_failed_track(spotify_id)
        if failed:
            self.db.delete(failed)
            self.db.commit()
            logger.debug("Cleared failed track: %s", spotify_id)
            return True
        return False

    def delete_all_failed_tracks(self) -> int:
        """
        Remove all failed track records.

        Returns:
            Number of records removed
        """
        deleted = self.db.query(FailedTrack).delete()
        self.db.commit()
        logger.info("Removed %s failed track records", deleted)
        return deleted

    def get_all_failed_tracks(self) -> list[FailedTrack]:
        """
        Retrieve all failed tracks from the database.

        Returns:
            List of all FailedTrack instances
        """
        return self.db.query(FailedTrack).all()
