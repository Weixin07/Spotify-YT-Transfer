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
                scope="playlist-read-private user-library-read",
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
    def get_liked_tracks(self) -> list:
        """Retrieve all of the user's saved (liked) Spotify tracks.

        Returns:
            list of dict: Each dict contains 'name', 'artist', 'album', 'duration_ms'.

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
