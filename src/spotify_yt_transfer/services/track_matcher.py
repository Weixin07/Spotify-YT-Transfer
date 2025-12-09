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
        logger.debug(f"Starting fuzzy matching for: {query}")

        # Extract titles for comparison and create mapping back to video IDs
        titles = [title for _, title in youtube_candidates]

        # Get top 3 matches for logging purposes
        top_matches = process.extract(
            query,
            titles,
            scorer=fuzz.token_sort_ratio,
            limit=min(3, len(titles)),
        )

        # Log top candidates and their scores
        logger.debug(f"Top {len(top_matches)} fuzzy match candidates:")
        for i, match in enumerate(top_matches, 1):
            title, score, idx = match
            video_id = youtube_candidates[idx][0]
            logger.debug(f"  {i}. [{score:.1f}] {video_id} - {title}")

        # Get the best match
        best_match = top_matches[0] if top_matches else None

        if best_match and best_match[1] >= self.threshold:
            # Get the index of the best matching title
            best_title_index = best_match[2]
            video_id = youtube_candidates[best_title_index][0]
            score = best_match[1]
            logger.info(f"Fuzzy match found: {video_id} (score: {score:.1f})")
            return video_id

        # Log failure with score information
        if best_match:
            best_score = best_match[1]
            logger.warning(
                f"No match found above threshold {self.threshold} for: {query} "
                f"(best score: {best_score:.1f}, need: {self.threshold})"
            )
        else:
            logger.warning(f"No match found above threshold {self.threshold} for: {query}")

        return None
