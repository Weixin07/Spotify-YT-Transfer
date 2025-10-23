"""Fuzzy matching algorithm for finding YouTube videos from Spotify tracks."""

import logging

from rapidfuzz import fuzz, process

from spotify_yt_transfer.core.config import settings

logger = logging.getLogger(__name__)


class TrackMatcher:
    """
    Service for matching Spotify tracks to YouTube videos using fuzzy string matching.

    Uses a two-stage approach:
    1. Exact substring matching for high confidence matches
    2. Fuzzy matching with configurable threshold for approximate matches
    """

    def __init__(self, threshold: int | None = None) -> None:
        """
        Initialize the TrackMatcher.

        Args:
            threshold: Minimum fuzzy match score (0-100).
                      Defaults to MATCH_FUZZ_THRESHOLD from config.
        """
        self.threshold = threshold or settings.matching.fuzz_threshold
        logger.debug(f"TrackMatcher initialized with threshold: {self.threshold}")

    def match_track(
        self,
        spotify_track: dict[str, str | None],
        youtube_candidates: list[tuple[str, str]],
    ) -> str | None:
        """
        Find the best matching YouTube video ID for a Spotify track.

        Uses a two-stage matching strategy:
        1. Exact substring match of "track_name artist" in video title
        2. Fuzzy matching using token_sort_ratio scorer

        Args:
            spotify_track: Dictionary containing 'name', 'artist', 'album' keys
            youtube_candidates: List of tuples [(video_id, video_title), ...]

        Returns:
            The video_id of the best match, or None if no good match is found
        """
        if not youtube_candidates:
            logger.warning("No YouTube candidates provided for matching")
            return None

        # Stage 1: Try exact substring match
        target = f"{spotify_track['name']} {spotify_track['artist']}".lower()
        for vid, title in youtube_candidates:
            if target in title.lower():
                logger.info(f"Exact substring match found: {vid}")
                return vid

        # Stage 2: Fuzzy matching
        query = f"{spotify_track['name']} {spotify_track['artist']}"
        candidates_dict = dict(youtube_candidates)

        best_match = process.extractOne(
            query,
            candidates_dict.items(),
            scorer=fuzz.token_sort_ratio,
        )

        if best_match and best_match[1] > self.threshold:
            video_id = best_match[0][0]
            score = best_match[1]
            logger.info(f"Fuzzy match found: {video_id} (score: {score})")
            return video_id

        logger.warning(f"No match found above threshold {self.threshold} for: {query}")
        return None
