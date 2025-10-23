"""Spotify API client with OAuth2 authentication and retry logic."""

import logging
from typing import Any

import spotipy
from spotipy.client import SpotifyException
from spotipy.oauth2 import SpotifyOAuth
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from spotify_yt_transfer.core.config import settings
from spotify_yt_transfer.core.token_storage import KeyringCacheHandler

logger = logging.getLogger(__name__)

# Type alias for track information
TrackInfo = dict[str, Any | None]


class SpotifyClient:
    """
    Client for interacting with the Spotify Web API.

    Handles authentication, playlist operations, and track retrieval
    with automatic retry logic for transient failures.
    """

    def __init__(self) -> None:
        """
        Initialize the SpotifyClient with OAuth2 authentication.

        Uses secure OS keyring for token storage. Automatically migrates
        existing .cache file to keyring on first run.

        Raises:
            SpotifyException: If authentication fails
        """
        logger.info("Initializing SpotifyClient with secure keyring storage")

        # Create cache handler with keyring backend
        cache_handler = KeyringCacheHandler(
            username=settings.token_storage.username,
            cache_path=settings.token_storage.spotify_cache_path,
        )

        self.sp = spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                client_id=settings.spotify.client_id,
                client_secret=settings.spotify.client_secret,
                redirect_uri=settings.spotify.redirect_uri,
                scope="playlist-read-private user-library-read playlist-modify-private playlist-modify-public",
                cache_handler=cache_handler,
            )
        )
        logger.info("Spotify client initialized successfully with keyring token storage")

    @retry(
        stop=stop_after_attempt(settings.spotify.retry_attempts),
        wait=wait_random_exponential(
            multiplier=settings.spotify.retry_multiplier,
            max=settings.spotify.retry_max,
        ),
        retry=retry_if_exception_type(SpotifyException),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def get_playlist_tracks(self, playlist_id: str) -> list[TrackInfo]:
        """
        Retrieve all tracks from a Spotify playlist.

        Args:
            playlist_id: The Spotify playlist ID to fetch tracks from

        Returns:
            List of track dictionaries containing name, artist, album, and duration_ms

        Raises:
            SpotifyException: If the Spotify API request fails
        """
        logger.info(f"Retrieving tracks for Spotify playlist ID: {playlist_id}")

        results = self.sp.playlist_items(playlist_id)
        tracks: list[TrackInfo] = []
        page = 1

        while results:
            items = results.get("items", [])
            logger.info(f"Processing page {page} with {len(items)} items")

            for idx, item in enumerate(items, start=1):
                track = item.get("track", {})
                if track:
                    track_info: TrackInfo = {
                        "id": track.get("id"),  # Actual Spotify track ID
                        "name": track.get("name"),
                        "artist": ", ".join(artist["name"] for artist in track.get("artists", [])),
                        "album": track.get("album", {}).get("name"),
                        "duration_ms": track.get("duration_ms"),
                    }
                    tracks.append(track_info)
                    logger.debug(
                        f"Added track {idx} on page {page}: '{track_info['name']}' by {track_info['artist']} (ID: {track_info['id']})"
                    )
                else:
                    logger.warning(f"Item {idx} on page {page} has no track information")

            results = self.sp.next(results) if results.get("next") else None
            page += 1

        logger.info(f"Total tracks retrieved: {len(tracks)}")
        return tracks

    @retry(
        stop=stop_after_attempt(settings.spotify.retry_attempts),
        wait=wait_random_exponential(
            multiplier=settings.spotify.retry_multiplier,
            max=settings.spotify.retry_max,
        ),
        retry=retry_if_exception_type(SpotifyException),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def get_liked_tracks(self, include_uri: bool = False) -> list[TrackInfo]:
        """
        Retrieve all of the user's saved (liked) Spotify tracks.

        Args:
            include_uri: If True, includes the Spotify track URI in the returned data

        Returns:
            List of track dictionaries containing name, artist, album, duration_ms,
            and optionally uri

        Raises:
            SpotifyException: If the Spotify API request fails
        """
        logger.info("Retrieving user's liked songs")

        results = self.sp.current_user_saved_tracks()
        tracks: list[TrackInfo] = []
        page = 1

        while results:
            items = results.get("items", [])
            logger.info(f"Processing liked songs page {page} with {len(items)} items")

            for idx, item in enumerate(items, start=1):
                track = item.get("track", {})
                if track:
                    track_info: TrackInfo = {
                        "id": track.get("id"),  # Actual Spotify track ID
                        "name": track.get("name"),
                        "artist": ", ".join(a["name"] for a in track.get("artists", [])),
                        "album": track.get("album", {}).get("name"),
                        "duration_ms": track.get("duration_ms"),
                    }
                    if include_uri:
                        track_info["uri"] = track.get("uri")
                    tracks.append(track_info)
                    logger.debug(
                        f"Added liked song {idx} on page {page}: '{track_info['name']}' by {track_info['artist']} (ID: {track_info['id']})"
                    )
                else:
                    logger.warning(
                        f"Item {idx} on liked songs page {page} has no track information"
                    )

            results = self.sp.next(results) if results.get("next") else None
            page += 1

        logger.info(f"Total liked songs retrieved: {len(tracks)}")
        return tracks

    @retry(
        stop=stop_after_attempt(settings.spotify.retry_attempts),
        wait=wait_random_exponential(
            multiplier=settings.spotify.retry_multiplier,
            max=settings.spotify.retry_max,
        ),
        retry=retry_if_exception_type(SpotifyException),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def get_current_user(self) -> dict[str, Any]:
        """
        Retrieve the current user's Spotify profile information.

        Returns:
            User profile dictionary including id, display_name, etc.

        Raises:
            SpotifyException: If the Spotify API request fails
        """
        logger.info("Retrieving current user profile")
        user = self.sp.current_user()
        logger.info(f"Current user: {user.get('display_name')} (ID: {user.get('id')})")
        return user

    @retry(
        stop=stop_after_attempt(settings.spotify.retry_attempts),
        wait=wait_random_exponential(
            multiplier=settings.spotify.retry_multiplier,
            max=settings.spotify.retry_max,
        ),
        retry=retry_if_exception_type(SpotifyException),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def create_playlist(
        self,
        user_id: str,
        name: str,
        description: str = "",
        public: bool = False,
    ) -> str:
        """
        Create a new Spotify playlist for the user.

        Args:
            user_id: The Spotify user ID
            name: The name of the playlist to create
            description: Optional description for the playlist
            public: Whether the playlist should be public (default: False)

        Returns:
            The created playlist's ID

        Raises:
            SpotifyException: If the Spotify API request fails
        """
        logger.info(f"Creating playlist '{name}' for user {user_id}")
        playlist = self.sp.user_playlist_create(
            user=user_id,
            name=name,
            public=public,
            description=description,
        )
        playlist_id = playlist.get("id")
        logger.info(f"Created playlist '{name}' with ID: {playlist_id}")
        return playlist_id

    @retry(
        stop=stop_after_attempt(settings.spotify.retry_attempts),
        wait=wait_random_exponential(
            multiplier=settings.spotify.retry_multiplier,
            max=settings.spotify.retry_max,
        ),
        retry=retry_if_exception_type(SpotifyException),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def add_tracks_to_playlist(self, playlist_id: str, track_uris: list[str]) -> None:
        """
        Add tracks to a Spotify playlist.

        Args:
            playlist_id: The Spotify playlist ID to add tracks to
            track_uris: List of Spotify track URIs to add (max 100 per call)

        Raises:
            SpotifyException: If the Spotify API request fails
            ValueError: If more than 100 track URIs are provided
        """
        if len(track_uris) > 100:
            raise ValueError("Cannot add more than 100 tracks at once. Please batch the requests.")

        logger.info(f"Adding {len(track_uris)} tracks to playlist {playlist_id}")
        self.sp.playlist_add_items(playlist_id, track_uris)
        logger.info(f"Successfully added {len(track_uris)} tracks to playlist {playlist_id}")
