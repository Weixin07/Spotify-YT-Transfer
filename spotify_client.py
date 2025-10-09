import logging
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.client import SpotifyException
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
from config import (
    SPOTIFY_CLIENT_ID,
    SPOTIFY_CLIENT_SECRET,
    SPOTIFY_REDIRECT_URI,
    SPOTIFY_RETRY_ATTEMPTS,
    SPOTIFY_RETRY_MULTIPLIER,
    SPOTIFY_RETRY_MAX,
)

# Use centralized logging; get module logger
logger = logging.getLogger(__name__)


class SpotifyClient:
    def __init__(self):
        """Initialize the SpotifyClient with OAuth2 authentication.

        Side Effects:
            - Configures the Spotipy client with OAuth2 credentials.
        """
        logger.info("Initializing SpotifyClient.")

        self.sp = spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                client_id=SPOTIFY_CLIENT_ID,
                client_secret=SPOTIFY_CLIENT_SECRET,
                redirect_uri=SPOTIFY_REDIRECT_URI,
                scope="playlist-read-private user-library-read playlist-modify-private",
            )
        )
        logger.info("Spotify client initialized successfully.")

    @retry(
        stop=stop_after_attempt(SPOTIFY_RETRY_ATTEMPTS),
        wait=wait_random_exponential(
            multiplier=SPOTIFY_RETRY_MULTIPLIER, max=SPOTIFY_RETRY_MAX
        ),
        retry=retry_if_exception_type(SpotifyException),
        before_sleep=before_sleep_log(logging.getLogger(__name__), logger.warning),
    )
    def get_playlist_tracks(self, playlist_id: str) -> list:
        """Retrieve all tracks from a Spotify playlist.

        Args:
            playlist_id (str): The Spotify playlist ID to fetch tracks from.

        Returns:
            list of dict: Each dict contains 'name', 'artist', 'album', 'duration_ms'.

        Raises:
            SpotifyException: If the Spotify API request fails.
        """
        logger.info(f"Retrieving tracks for Spotify playlist ID: {playlist_id}")

        results = self.sp.playlist_items(playlist_id)
        tracks = []
        page = 1
        while results:
            items = results.get("items", [])
            logger.info(f"Processing page {page} with {len(items)} items.")
            for idx, item in enumerate(items, start=1):
                track = item.get("track", {})
                if track:
                    track_info = {
                        "name": track.get("name"),
                        "artist": ", ".join(
                            [artist["name"] for artist in track.get("artists", [])]
                        ),
                        "album": track.get("album", {}).get("name"),
                        "duration_ms": track.get("duration_ms"),
                    }
                    tracks.append(track_info)
                    logger.info(
                        f"Added track {idx} on page {page}: '{track_info['name']}' by {track_info['artist']}."
                    )
                else:
                    logger.warning(
                        f"Item {idx} on page {page} has no track information."
                    )
            results = self.sp.next(results) if self.sp.next(results) else None
            page += 1
        logger.info(f"Total tracks retrieved: {len(tracks)}")
        return tracks

    @retry(
        stop=stop_after_attempt(SPOTIFY_RETRY_ATTEMPTS),
        wait=wait_random_exponential(
            multiplier=SPOTIFY_RETRY_MULTIPLIER, max=SPOTIFY_RETRY_MAX
        ),
        retry=retry_if_exception_type(SpotifyException),
        before_sleep=before_sleep_log(logging.getLogger(__name__), logger.warning),
    )
    def get_liked_tracks(self, include_uri: bool = False) -> list:
        """Retrieve all of the user's saved (liked) Spotify tracks.

        Args:
            include_uri (bool): If True, includes the Spotify track URI in the returned data.

        Returns:
            list of dict: Each dict contains 'name', 'artist', 'album', 'duration_ms', and optionally 'uri'.

        Raises:
            SpotifyException: If the Spotify API request fails.
        """
        logger.info("Retrieving user's liked songs")
        ...

        results = self.sp.current_user_saved_tracks()
        tracks = []
        page = 1
        while results:
            items = results.get("items", [])
            logger.info(f"Processing liked songs page {page} with {len(items)} items.")
            for idx, item in enumerate(items, start=1):
                track = item.get("track", {})
                if track:
                    track_info = {
                        "name": track.get("name"),
                        "artist": ", ".join(
                            a["name"] for a in track.get("artists", [])
                        ),
                        "album": track.get("album", {}).get("name"),
                        "duration_ms": track.get("duration_ms"),
                    }
                    if include_uri:
                        track_info["uri"] = track.get("uri")
                    tracks.append(track_info)
                    logger.info(
                        f"Added liked song {idx} on page {page}: '{track_info['name']}' by {track_info['artist']}."
                    )
                else:
                    logger.warning(
                        f"Item {idx} on liked songs page {page} has no track information."
                    )
            results = self.sp.next(results) if self.sp.next(results) else None
            page += 1
        logger.info(f"Total liked songs retrieved: {len(tracks)}")
        return tracks

    @retry(
        stop=stop_after_attempt(SPOTIFY_RETRY_ATTEMPTS),
        wait=wait_random_exponential(
            multiplier=SPOTIFY_RETRY_MULTIPLIER, max=SPOTIFY_RETRY_MAX
        ),
        retry=retry_if_exception_type(SpotifyException),
        before_sleep=before_sleep_log(logging.getLogger(__name__), logger.warning),
    )
    def get_current_user(self) -> dict:
        """Retrieve the current user's Spotify profile information.

        Returns:
            dict: User profile information including 'id', 'display_name', etc.

        Raises:
            SpotifyException: If the Spotify API request fails.
        """
        logger.info("Retrieving current user profile.")
        user = self.sp.current_user()
        logger.info(f"Current user: {user.get('display_name')} (ID: {user.get('id')})")
        return user

    @retry(
        stop=stop_after_attempt(SPOTIFY_RETRY_ATTEMPTS),
        wait=wait_random_exponential(
            multiplier=SPOTIFY_RETRY_MULTIPLIER, max=SPOTIFY_RETRY_MAX
        ),
        retry=retry_if_exception_type(SpotifyException),
        before_sleep=before_sleep_log(logging.getLogger(__name__), logger.warning),
    )
    def create_playlist(self, user_id: str, name: str, description: str = "", public: bool = False) -> str:
        """Create a new Spotify playlist for the user.

        Args:
            user_id (str): The Spotify user ID.
            name (str): The name of the playlist to create.
            description (str): Optional description for the playlist.
            public (bool): Whether the playlist should be public (default: False).

        Returns:
            str: The created playlist's ID.

        Raises:
            SpotifyException: If the Spotify API request fails.
        """
        logger.info(f"Creating playlist '{name}' for user {user_id}.")
        playlist = self.sp.user_playlist_create(
            user=user_id,
            name=name,
            public=public,
            description=description
        )
        playlist_id = playlist.get('id')
        logger.info(f"Created playlist '{name}' with ID: {playlist_id}")
        return playlist_id

    @retry(
        stop=stop_after_attempt(SPOTIFY_RETRY_ATTEMPTS),
        wait=wait_random_exponential(
            multiplier=SPOTIFY_RETRY_MULTIPLIER, max=SPOTIFY_RETRY_MAX
        ),
        retry=retry_if_exception_type(SpotifyException),
        before_sleep=before_sleep_log(logging.getLogger(__name__), logger.warning),
    )
    def add_tracks_to_playlist(self, playlist_id: str, track_uris: list) -> None:
        """Add tracks to a Spotify playlist.

        Args:
            playlist_id (str): The Spotify playlist ID to add tracks to.
            track_uris (list of str): List of Spotify track URIs to add (max 100 per call).

        Raises:
            SpotifyException: If the Spotify API request fails.
            ValueError: If more than 100 track URIs are provided.
        """
        if len(track_uris) > 100:
            raise ValueError("Cannot add more than 100 tracks at once. Please batch the requests.")

        logger.info(f"Adding {len(track_uris)} tracks to playlist {playlist_id}.")
        self.sp.playlist_add_items(playlist_id, track_uris)
        logger.info(f"Successfully added {len(track_uris)} tracks to playlist {playlist_id}.")
