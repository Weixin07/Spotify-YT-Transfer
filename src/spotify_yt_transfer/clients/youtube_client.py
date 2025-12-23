"""YouTube Data API client with OAuth2 authentication and caching."""

# mypy: ignore-errors

import json
import logging
from typing import Any

from cachetools import TTLCache, cached  # type: ignore[import-untyped]
from google.auth.transport.requests import Request as GoogleAuthRequest
from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_random_exponential,
)

from spotify_yt_transfer.clients.errors import OAuthCredentialsMissing
from spotify_yt_transfer.core.config import settings
from spotify_yt_transfer.core.token_storage import YouTubeTokenStorage

logger = logging.getLogger(__name__)

# YouTube API scopes
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]

# Dedicated 15 minute TTL caches by data type to avoid key collisions across methods
_playlist_name_cache: TTLCache = TTLCache(maxsize=100, ttl=15 * 60)
_playlist_items_cache: TTLCache = TTLCache(maxsize=100, ttl=15 * 60)
_video_candidates_cache: TTLCache = TTLCache(maxsize=1000, ttl=15 * 60)
_video_search_cache: TTLCache = TTLCache(maxsize=1000, ttl=15 * 60)
_video_title_cache: TTLCache = TTLCache(maxsize=2000, ttl=15 * 60)
_video_title_cache: TTLCache = TTLCache(maxsize=2000, ttl=15 * 60)


def _is_quota_exceeded(error: HttpError) -> bool:
    """
    Determine if the HttpError is due to YouTube API quota exhaustion.

    Args:
        error: Exception raised by the YouTube API client

    Returns:
        True if the error reason equals 'quotaExceeded', False otherwise
    """
    try:
        status = error.resp.status
        body = error.content.decode()
        payload = json.loads(body)
        reason = payload.get("error", {}).get("errors", [{}])[0].get("reason", "")
        return status == 403 and reason == "quotaExceeded"
    except Exception:
        return False


class YouTubeClient:
    """
    Client for interacting with the YouTube Data API v3.

    Handles authentication, playlist management, and video search
    with automatic retry logic and caching.
    """

    def __init__(self, token_path: str | None = None) -> None:
        """
        Initialize the YouTubeClient by authenticating and configuring the service.

        Uses secure OS keyring for token storage. Automatically migrates
        existing token.pickle file to keyring on first run.

        Args:
            token_path: Path to legacy pickle file for migration (default: "token.pickle")

        Raises:
            Exception: If authentication fails
        """
        logger.info("Initializing YouTubeClient with secure keyring storage")

        token_storage_path = token_path or settings.token_storage.youtube_token_path
        self.token_storage = YouTubeTokenStorage(
            username=settings.token_storage.username,
            token_path=token_storage_path,
        )
        self.creds: Any | None = None
        self.service: Resource = self._authenticate()

        logger.info("YouTubeClient initialized successfully with keyring token storage")

    def _authenticate(self) -> Resource:
        """
        Authenticate with the YouTube API, refreshing or generating credentials as needed.

        Returns:
            Authorized YouTube API client resource

        Side Effects:
            Writes new credentials to OS keyring if generated
        """
        logger.info("Authenticating with YouTube API")

        # Try to load credentials from keyring
        self.creds = self.token_storage.get_credentials()

        if self.creds:
            logger.info("Loaded existing credentials from keyring")
        else:
            logger.warning("YouTubeClient initialization aborted: no credentials found in keyring")
            raise OAuthCredentialsMissing(
                "YouTube credentials not found. Complete the OAuth flow via /v1/auth/youtube/authorize."
            )

        if not self.creds.valid:
            if self.creds.expired and self.creds.refresh_token:
                logger.info("YouTube credentials expired. Refreshing token")
                self.creds.refresh(GoogleAuthRequest())
                self.token_storage.save_credentials(self.creds)
            else:
                logger.warning("YouTube credentials invalid and cannot be refreshed")
                raise OAuthCredentialsMissing(
                    "YouTube credentials invalid. Re-authorize via /v1/auth/youtube/authorize."
                )
        else:
            logger.info("Using valid YouTube credentials from keyring")

        return build("youtube", "v3", credentials=self.creds)

    @cached(cache=_playlist_name_cache, key=lambda _self, playlist_name: playlist_name)
    @retry(
        stop=stop_after_attempt(settings.youtube.retry_attempts),
        wait=wait_random_exponential(
            multiplier=settings.youtube.retry_multiplier,
            max=settings.youtube.retry_max,
        ),
        retry=retry_if_exception(lambda e: isinstance(e, HttpError) and not _is_quota_exceeded(e)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def find_playlist_by_name(self, playlist_name: str) -> str | None:
        """
        Check if a playlist with the given name exists in the user's account.

        Args:
            playlist_name: Name of the playlist to search for

        Returns:
            Playlist ID if found, None otherwise

        Raises:
            HttpError: If the YouTube API request fails (except quota errors)
        """
        logger.info(f"Searching for existing playlist with name: '{playlist_name}'")

        page_token: str | None = None
        page = 1

        while True:
            response = (
                self.service.playlists()
                .list(part="snippet", mine=True, maxResults=50, pageToken=page_token)
                .execute()
            )

            items = response.get("items", [])
            logger.info(f"Processing page {page} of playlists. Items found: {len(items)}")

            for item in items:
                title = item["snippet"]["title"]
                logger.debug(f"Found playlist: '{title}'")
                if title.lower() == playlist_name.lower():
                    playlist_id = item["id"]
                    logger.info(f"Match found. Playlist ID: {playlist_id}")
                    return playlist_id

            page_token = response.get("nextPageToken")
            if not page_token:
                break
            page += 1

        logger.info("No matching playlist found")
        return None

    @cached(cache=_playlist_items_cache, key=lambda _self, playlist_id: playlist_id)
    @retry(
        stop=stop_after_attempt(settings.youtube.retry_attempts),
        wait=wait_random_exponential(
            multiplier=settings.youtube.retry_multiplier,
            max=settings.youtube.retry_max,
        ),
        retry=retry_if_exception(lambda e: isinstance(e, HttpError) and not _is_quota_exceeded(e)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def get_playlist_items(self, playlist_id: str) -> list[str]:
        """
        Retrieve all video IDs currently in the specified playlist.

        Args:
            playlist_id: YouTube playlist ID

        Returns:
            List of video IDs in the playlist

        Raises:
            HttpError: If the YouTube API request fails (except quota errors)
        """
        logger.info(f"Retrieving videos from playlist ID: {playlist_id}")

        page_token: str | None = None
        video_ids: list[str] = []
        page = 1

        while True:
            response = (
                self.service.playlistItems()
                .list(
                    part="snippet",
                    playlistId=playlist_id,
                    maxResults=50,
                    pageToken=page_token,
                )
                .execute()
            )

            items = response.get("items", [])
            logger.info(f"Page {page}: Retrieved {len(items)} items")

            for idx, item in enumerate(items, start=1):
                resource = item["snippet"]["resourceId"]
                if resource["kind"] == "youtube#video":
                    video_id = resource["videoId"]
                    video_ids.append(video_id)
                    logger.debug(f"Page {page} - Video {idx}: {video_id}")

            page_token = response.get("nextPageToken")
            if not page_token:
                break
            page += 1

        logger.info(f"Total videos retrieved: {len(video_ids)}")
        return video_ids

    @cached(
        cache=_video_candidates_cache, key=lambda _self, query, max_results=10: (query, max_results)
    )
    @retry(
        stop=stop_after_attempt(settings.youtube.retry_attempts),
        wait=wait_random_exponential(
            multiplier=settings.youtube.retry_multiplier,
            max=settings.youtube.retry_max,
        ),
        retry=retry_if_exception(lambda e: isinstance(e, HttpError) and not _is_quota_exceeded(e)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def search_video_candidates(self, query: str, max_results: int = 10) -> list[tuple[str, str]]:
        """
        Search YouTube and return multiple candidate videos for fuzzy matching.

        Args:
            query: Combined track name and artist string
            max_results: Maximum number of candidates to return (default: 10)

        Returns:
            List of tuples [(video_id, video_title), ...] for fuzzy matching

        Raises:
            HttpError: If the YouTube API request fails (except quota errors)
        """
        logger.info(f"Searching YouTube candidates for query: '{query}' (max: {max_results})")

        candidates: list[tuple[str, str]] = []
        page_token: str | None = None

        while len(candidates) < max_results:
            request = self.service.search().list(
                part="snippet",
                q=query,
                type="video",
                videoCategoryId="10",  # Filter to Music category only
                maxResults=min(5, max_results - len(candidates)),
                pageToken=page_token,
            )
            response = request.execute()
            items = response.get("items", [])

            if not items:
                logger.info("No more search results available")
                break

            # Collect all valid video candidates with their titles
            for item in items:
                video_id = item.get("id", {}).get("videoId")
                title = item.get("snippet", {}).get("title", "")

                if video_id and title:
                    candidates.append((video_id, title))
                    logger.debug(f"Candidate {len(candidates)}: {video_id} - {title}")
                else:
                    logger.warning("Candidate item missing 'videoId' or 'title'")

                if len(candidates) >= max_results:
                    break

            # Check if there are more pages
            page_token = response.get("nextPageToken")
            if not page_token:
                logger.info("Reached end of search results")
                break

        logger.info(f"Found {len(candidates)} candidates for query: '{query}'")
        return candidates

    @cached(cache=_video_title_cache, key=lambda _self, video_id: video_id)
    @retry(
        stop=stop_after_attempt(settings.youtube.retry_attempts),
        wait=wait_random_exponential(
            multiplier=settings.youtube.retry_multiplier,
            max=settings.youtube.retry_max,
        ),
        retry=retry_if_exception(lambda e: isinstance(e, HttpError) and not _is_quota_exceeded(e)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def get_video_title(self, video_id: str) -> str | None:
        """
        Fetch the title for a single YouTube video.

        Args:
            video_id: YouTube video identifier

        Returns:
            The video title, or None if not found

        Raises:
            HttpError: If the YouTube API request fails (except quota errors)
        """
        logger.debug("Fetching YouTube title for %s", video_id)

        response = (
            self.service.videos()
            .list(part="snippet", id=video_id, maxResults=1)
            .execute()
        )

        items = response.get("items", [])
        if not items:
            logger.info("Video %s not found when retrieving title", video_id)
            return None

        snippet = items[0].get("snippet", {})
        title = snippet.get("title")

        if not title:
            logger.info("Video %s is missing a title in snippet", video_id)
            return None

        return title

    @cached(cache=_video_search_cache, key=lambda _self, query: query)
    @retry(
        stop=stop_after_attempt(settings.youtube.retry_attempts),
        wait=wait_random_exponential(
            multiplier=settings.youtube.retry_multiplier,
            max=settings.youtube.retry_max,
        ),
        retry=retry_if_exception(lambda e: isinstance(e, HttpError) and not _is_quota_exceeded(e)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def search_video(self, query: str) -> str | None:
        """
        Search YouTube for the best matching music video for the given query.

        NOTE: This is the legacy method that returns only the first result.
        For better matching, use search_video_candidates() with TrackMatcher.

        Args:
            query: Combined track name and artist string

        Returns:
            Video ID of the best matching music video, or None if none found

        Raises:
            HttpError: If the YouTube API request fails (except quota errors)
        """
        logger.info(f"Searching YouTube for query: '{query}'")

        page_token: str | None = None

        while True:
            request = self.service.search().list(
                part="snippet",
                q=query,
                type="video",
                videoCategoryId="10",  # Filter to Music category only
                maxResults=5,  # Get multiple results at once to reduce pagination
                pageToken=page_token,
            )
            response = request.execute()
            items = response.get("items", [])

            if not items:
                logger.info("No more search results available")
                break

            # Since we filtered by videoCategoryId=10, all results are Music videos
            # Return the first valid video ID found
            for candidate in items:
                video_id = candidate.get("id", {}).get("videoId")
                if video_id:
                    logger.info(f"Found Music video: {video_id}")
                    return video_id
                else:
                    logger.warning("Candidate item missing 'videoId', checking next result")

            # If no valid video ID in current page, try next page
            page_token = response.get("nextPageToken")
            if not page_token:
                logger.info("Reached end of search results without finding a valid video")
                break

        return None

    @retry(
        stop=stop_after_attempt(settings.youtube.retry_attempts),
        wait=wait_random_exponential(
            multiplier=settings.youtube.retry_multiplier,
            max=settings.youtube.retry_max,
        ),
        retry=retry_if_exception(lambda e: isinstance(e, HttpError) and not _is_quota_exceeded(e)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def create_playlist(self, title: str, description: str = "") -> str:
        """
        Create a new private YouTube playlist.

        Args:
            title: Title for the new playlist
            description: Optional description text

        Returns:
            The newly created playlist ID

        Raises:
            HttpError: If the YouTube API request fails (except quota errors)
        """
        logger.info(f"Creating YouTube playlist: '{title}' with description: '{description}'")

        request = self.service.playlists().insert(
            part="snippet,status",
            body={
                "snippet": {"title": title, "description": description},
                "status": {"privacyStatus": "private"},
            },
        )
        response = request.execute()
        playlist_id = response.get("id")

        logger.info(f"Playlist created with ID: {playlist_id}")
        return playlist_id

    @retry(
        stop=stop_after_attempt(settings.youtube.retry_attempts),
        wait=wait_random_exponential(
            multiplier=settings.youtube.retry_multiplier,
            max=settings.youtube.retry_max,
        ),
        retry=retry_if_exception(lambda e: isinstance(e, HttpError) and not _is_quota_exceeded(e)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def add_video_to_playlist(self, playlist_id: str, video_id: str) -> dict[str, Any]:
        """
        Add a video to a specified YouTube playlist.

        Args:
            playlist_id: ID of the target playlist
            video_id: ID of the video to be added

        Returns:
            The API response for the insert operation

        Raises:
            HttpError: If the YouTube API request fails (except quota errors)
        """
        logger.info(f"Adding video ID: {video_id} to playlist ID: {playlist_id}")

        request = self.service.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {"kind": "youtube#video", "videoId": video_id},
                }
            },
        )
        response = request.execute()

        logger.info(f"Video {video_id} added to playlist {playlist_id} successfully")

        # Playlist contents changed; drop cached copy so next read is fresh
        _playlist_items_cache.pop(playlist_id, None)
        logger.debug(f"Invalidated playlist cache for {playlist_id}")

        return response

    def clear_search_cache(self) -> None:
        """Clear in-memory YouTube search results caches."""
        _video_candidates_cache.clear()
        _video_search_cache.clear()
        _video_title_cache.clear()
        logger.debug("YouTube search caches cleared")

    def is_video_available(self, video_id: str) -> bool:
        """
        Check whether a YouTube video is playable/available.

        Returns False for deleted/blocked/private/unprocessed videos.
        """
        try:
            response = (
                self.service.videos()
                .list(part="status,contentDetails", id=video_id, maxResults=1)
                .execute()
            )
            items = response.get("items", [])
            if not items:
                logger.warning("Video %s not found when checking availability", video_id)
                return False

            item = items[0]
            status = item.get("status", {})
            upload_status = status.get("uploadStatus")
            privacy_status = status.get("privacyStatus")
            content_details = item.get("contentDetails", {})
            region_restriction = content_details.get("regionRestriction", {})

            if upload_status != "processed":
                logger.info("Video %s unavailable due to uploadStatus=%s", video_id, upload_status)
                return False

            if privacy_status not in {"public", "unlisted"}:
                logger.info(
                    "Video %s unavailable due to privacyStatus=%s", video_id, privacy_status
                )
                return False

            if region_restriction.get("blocked"):
                logger.info("Video %s is region-blocked", video_id)
                return False

            return True

        except HttpError as e:
            if _is_quota_exceeded(e):
                raise
            logger.warning("Failed to validate availability for %s: %s", video_id, e)
            return False
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Unexpected error validating availability for %s: %s", video_id, exc)
            return False
