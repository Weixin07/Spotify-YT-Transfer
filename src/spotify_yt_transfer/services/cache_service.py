"""Cache management utilities."""

import logging
from dataclasses import dataclass
from typing import Any

from googleapiclient.errors import HttpError

from spotify_yt_transfer.clients import YouTubeClient
from spotify_yt_transfer.clients.youtube_client import _is_quota_exceeded
from spotify_yt_transfer.database.repository import TrackRepository
from spotify_yt_transfer.services.exceptions import QuotaExceededError
from spotify_yt_transfer.services.track_matcher import (
    _contains_disallowed_terms,
    _normalize_for_filter,
)

logger = logging.getLogger(__name__)


@dataclass
class CacheInvalidationResult:
    """Summary of cache invalidation operations."""

    matched_tracks_removed: int = 0
    failed_tracks_removed: int = 0
    youtube_cache_cleared: bool = False

    def as_dict(self) -> dict[str, Any]:
        """Return result as plain dictionary."""
        return {
            "matched_tracks_removed": self.matched_tracks_removed,
            "failed_tracks_removed": self.failed_tracks_removed,
            "youtube_cache_cleared": self.youtube_cache_cleared,
        }


@dataclass
class MatchedTrackAudit:
    """Track flagged for containing disallowed terms."""

    spotify_id: str
    youtube_id: str
    title: str
    song_name: str
    artist: str


@dataclass
class MatchedTrackAuditResult:
    """Summary of auditing matched tracks for disallowed terms."""

    total_checked: int
    flagged: list[MatchedTrackAudit]
    removed: int = 0


class CacheService:
    """Service for invalidating cached data across the application."""

    def __init__(self, repository: TrackRepository, youtube_client: YouTubeClient):
        self.repository = repository
        self.youtube_client = youtube_client

    def clear_youtube_cache(self) -> None:
        """Clear in-memory YouTube search cache."""
        self.youtube_client.clear_search_cache()
        logger.info("Cleared YouTube search cache")

    def delete_all_matched_tracks(self) -> int:
        """Delete all cached Spotify-to-YouTube matches."""
        removed = self.repository.delete_all_matched_tracks()
        logger.info("Removed %s matched track cache entries", removed)
        return removed

    def delete_all_failed_tracks(self) -> int:
        """Delete all failed-track retry records."""
        removed = self.repository.delete_all_failed_tracks()
        logger.info("Removed %s failed track records", removed)
        return removed

    def audit_matched_tracks(self, remove_flagged: bool = False) -> MatchedTrackAuditResult:
        """
        Check cached matched tracks for disallowed terms and optionally delete them.

        Args:
            remove_flagged: When True, delete any flagged matched track records.

        Returns:
            MatchedTrackAuditResult with flagged entries and removal count.

        Raises:
            QuotaExceededError: If YouTube quota is exhausted while fetching titles.
        """
        matches = self.repository.get_all_matched_tracks()
        flagged: list[MatchedTrackAudit] = []
        removed = 0

        for track in matches:
            youtube_title: str | None = track.youtube_title

            if youtube_title is None:
                try:
                    youtube_title = self.youtube_client.get_video_title(track.youtube_id)
                except HttpError as exc:
                    if _is_quota_exceeded(exc):
                        raise QuotaExceededError(
                            "YouTube API quota exceeded while auditing matched tracks",
                            service="youtube",
                            details={"stage": "audit_matched_tracks"},
                        ) from exc
                    logger.warning("Failed to fetch title for %s: %s", track.youtube_id, exc)
                    continue

            if not youtube_title:
                # Skip entries that no longer exist or have no title
                continue

            normalized = _normalize_for_filter(youtube_title)
            if not normalized:
                continue

            if not _contains_disallowed_terms(normalized):
                continue

            flagged.append(
                MatchedTrackAudit(
                    spotify_id=track.spotify_id,
                    youtube_id=track.youtube_id,
                    title=youtube_title,
                    song_name=track.song_name,
                    artist=track.artist,
                )
            )

            if remove_flagged:
                if self.repository.delete_matched_track(track.spotify_id):
                    removed += 1

        return MatchedTrackAuditResult(
            total_checked=len(matches),
            flagged=flagged,
            removed=removed,
        )

    def invalidate(
        self,
        clear_youtube_cache: bool,
        delete_matched: bool,
        delete_failed: bool,
    ) -> CacheInvalidationResult:
        """
        Invalidate caches according to the provided options.

        Args:
            clear_youtube_cache: Whether to clear in-memory YouTube search cache
            delete_matched: Whether to delete persisted matched track cache
            delete_failed: Whether to delete failed track entries

        Returns:
            CacheInvalidationResult summarising changes
        """
        result = CacheInvalidationResult()

        if delete_matched:
            result.matched_tracks_removed = self.delete_all_matched_tracks()

        if delete_failed:
            result.failed_tracks_removed = self.delete_all_failed_tracks()

        if clear_youtube_cache:
            self.clear_youtube_cache()
            result.youtube_cache_cleared = True

        return result
