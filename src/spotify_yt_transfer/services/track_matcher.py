"""Fuzzy matching algorithm for finding YouTube videos from Spotify tracks."""

import logging
import re
import string

from rapidfuzz import fuzz, process

from spotify_yt_transfer.core.config import settings

logger = logging.getLogger(__name__)

# Terms that should cause a candidate video to be skipped entirely
DISALLOWED_TERMS: tuple[str, ...] = (
    # Versions / performances
    "live",
    "acoustic",
    "unplugged",
    "session",
    "rehearsal",
    "demo",
    "leak",
    "fanmade",
    "cover",
    "karaoke",
    "instrumental",
    "backing track",
    "tribute",
    "mashup",
    "bootleg",
    # Edits / remixes
    "remix",
    "mix",
    "extended mix",
    "radio edit",
    "club mix",
    "vip",
    "edit",
    "refix",
    "rework",
    # Tempo / processing
    "sped up",
    "speed up",
)


_PUNCTUATION_TABLE = str.maketrans(dict.fromkeys(string.punctuation, " "))


def _normalize_for_filter(text: str) -> str:
    """Lowercase, remove punctuation (but keep bracketed content), and collapse whitespace."""
    text = text.translate(_PUNCTUATION_TABLE).lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _normalize_text(text: str) -> str:
    """Lowercase, strip bracketed tags, remove punctuation, and collapse whitespace."""
    # Remove bracketed segments like "(Official Video)" or "[Lyrics]"
    text = re.sub(r"[\(\[\{][^\)\]\}]*[\)\]\}]", " ", text)
    # Replace punctuation with spaces, lowercase, and collapse whitespace
    text = text.translate(_PUNCTUATION_TABLE).lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _contains_disallowed_terms(normalized_title: str) -> bool:
    """Return True if a normalized title contains any disallowed term as a whole token/phrase."""
    padded_title = f" {normalized_title} "
    return any(f" {term} " in padded_title for term in DISALLOWED_TERMS)


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

        # Normalize and filter out unwanted candidates (e.g., live, cover, remix versions)
        filtered_candidates: list[tuple[str, str, str]] = []
        for vid, title in youtube_candidates:
            normalized_for_filter = _normalize_for_filter(title)
            if not normalized_for_filter:
                logger.debug("Skipping candidate with empty normalized title: %s", title)
                continue

            if _contains_disallowed_terms(normalized_for_filter):
                logger.info("Skipping candidate with disallowed terms: %s", title)
                continue

            normalized_title = _normalize_text(title)
            filtered_candidates.append((vid, title, normalized_title))

        if not filtered_candidates:
            logger.warning("All YouTube candidates were filtered out by disallowed terms")
            return None

        # Stage 1: Try exact substring match
        target = _normalize_text(f"{spotify_track['name']} {spotify_track['artist']}")
        for vid, _title, normalized_title in filtered_candidates:
            if target and target in normalized_title:
                logger.info(f"Exact substring match found: {vid}")
                return vid

        # Stage 2: Fuzzy matching
        query = f"{spotify_track['name']} {spotify_track['artist']}"
        logger.debug(f"Starting fuzzy matching for: {query}")

        # Extract titles for comparison and create mapping back to video IDs
        titles = [normalized_title for _, _, normalized_title in filtered_candidates]

        # Get top 3 matches for logging purposes
        top_matches = process.extract(
            _normalize_text(query),
            titles,
            scorer=fuzz.token_sort_ratio,
            limit=min(3, len(titles)),
        )

        # Log top candidates and their scores
        logger.debug(f"Top {len(top_matches)} fuzzy match candidates:")
        for i, match in enumerate(top_matches, 1):
            title, score, idx = match
            video_id = filtered_candidates[idx][0]
            logger.debug(f"  {i}. [{score:.1f}] {video_id} - {filtered_candidates[idx][1]}")

        # Get the best match
        best_match = top_matches[0] if top_matches else None

        if best_match and best_match[1] >= self.threshold:
            # Get the index of the best matching title
            best_title_index = best_match[2]
            video_id = filtered_candidates[best_title_index][0]
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
