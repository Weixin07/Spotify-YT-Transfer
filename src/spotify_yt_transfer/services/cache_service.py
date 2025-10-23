"""Cache management utilities."""

import logging
from dataclasses import dataclass
from typing import Any

from spotify_yt_transfer.clients import YouTubeClient
from spotify_yt_transfer.database.repository import TrackRepository

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
