"""Secure token storage using OS keyring with migration support."""

import json
import logging
import pickle
from pathlib import Path
from typing import Any

import keyring
from spotipy.cache_handler import CacheHandler

logger = logging.getLogger(__name__)

# Service name for keyring entries
SERVICE_NAME = "spotify_yt_transfer"


class KeyringCacheHandler(CacheHandler):
    """
    Spotipy cache handler that stores tokens securely in OS keyring.

    Implements Spotipy's CacheHandler interface to integrate with
    SpotifyOAuth token management. Automatically migrates existing
    file-based cache to keyring on first use.
    """

    def __init__(self, username: str = "default", cache_path: str = ".cache") -> None:
        """
        Initialize keyring cache handler.

        Args:
            username: Username/identifier for keyring entry (default: "default")
            cache_path: Path to legacy cache file for migration (default: ".cache")
        """
        self.username = username
        self.cache_path = Path(cache_path)
        self.keyring_key = f"spotify_token_{username}"

        # Attempt migration on initialization
        self._migrate_from_file()

    def get_cached_token(self) -> dict[str, Any] | None:
        """
        Retrieve cached Spotify token from keyring.

        Returns:
            Token info dictionary if found, None otherwise
        """
        try:
            token_json = keyring.get_password(SERVICE_NAME, self.keyring_key)
            if token_json:
                logger.debug(f"Retrieved Spotify token from keyring for user '{self.username}'")
                return json.loads(token_json)
            logger.debug(f"No Spotify token found in keyring for user '{self.username}'")
            return None
        except Exception as e:
            logger.error(f"Failed to retrieve Spotify token from keyring: {e}")
            return None

    def save_token_to_cache(self, token_info: dict[str, Any] | None) -> None:
        """
        Save Spotify token to keyring.

        Args:
            token_info: Token dictionary to store
        """
        if not token_info:
            logger.warning("Attempted to save None token to keyring")
            return

        try:
            token_json = json.dumps(token_info)
            keyring.set_password(SERVICE_NAME, self.keyring_key, token_json)
            logger.info(f"Saved Spotify token to keyring for user '{self.username}'")

            # Remove legacy cache file if it exists
            if self.cache_path.exists():
                logger.info(f"Removing legacy cache file: {self.cache_path}")
                self.cache_path.unlink()
        except Exception as e:
            logger.error(f"Failed to save Spotify token to keyring: {e}")
            raise

    def _migrate_from_file(self) -> None:
        """
        Migrate existing file-based cache to keyring.

        Checks for legacy .cache file and moves token to keyring if found.
        Deletes the file after successful migration.
        """
        if not self.cache_path.exists():
            return

        try:
            logger.info(f"Found legacy Spotify cache file: {self.cache_path}")
            with self.cache_path.open("r") as f:
                token_info = json.load(f)

            # Save to keyring
            self.save_token_to_cache(token_info)
            logger.info("Successfully migrated Spotify token from file to keyring")
        except Exception as e:
            logger.warning(f"Failed to migrate Spotify token from file: {e}")


class YouTubeTokenStorage:
    """
    Secure storage for YouTube OAuth2 credentials using OS keyring.

    Replaces pickle-based file storage with encrypted keyring storage.
    Automatically migrates existing token.pickle files.
    """

    def __init__(self, username: str = "default", token_path: str = "token.pickle") -> None:
        """
        Initialize YouTube token storage.

        Args:
            username: Username/identifier for keyring entry (default: "default")
            token_path: Path to legacy pickle file for migration (default: "token.pickle")
        """
        self.username = username
        self.token_path = Path(token_path)
        self.keyring_key = f"youtube_token_{username}"

        # Attempt migration on initialization
        self._migrate_from_pickle()

    def get_credentials(self) -> Any | None:
        """
        Retrieve YouTube credentials from keyring.

        Returns:
            Credentials object if found, None otherwise
        """
        try:
            creds_json = keyring.get_password(SERVICE_NAME, self.keyring_key)
            if creds_json:
                logger.debug(f"Retrieved YouTube credentials from keyring for user '{self.username}'")
                # Deserialize credentials from JSON
                creds_dict = json.loads(creds_json)
                return self._dict_to_credentials(creds_dict)
            logger.debug(f"No YouTube credentials found in keyring for user '{self.username}'")
            return None
        except Exception as e:
            logger.error(f"Failed to retrieve YouTube credentials from keyring: {e}")
            return None

    def save_credentials(self, credentials: Any) -> None:
        """
        Save YouTube credentials to keyring.

        Args:
            credentials: Google OAuth2 credentials object
        """
        if not credentials:
            logger.warning("Attempted to save None credentials to keyring")
            return

        try:
            # Serialize credentials to JSON (avoiding pickle security issues)
            creds_dict = self._credentials_to_dict(credentials)
            creds_json = json.dumps(creds_dict)
            keyring.set_password(SERVICE_NAME, self.keyring_key, creds_json)
            logger.info(f"Saved YouTube credentials to keyring for user '{self.username}'")

            # Remove legacy pickle file if it exists
            if self.token_path.exists():
                logger.info(f"Removing legacy pickle file: {self.token_path}")
                self.token_path.unlink()
        except Exception as e:
            logger.error(f"Failed to save YouTube credentials to keyring: {e}")
            raise

    def _credentials_to_dict(self, credentials: Any) -> dict[str, Any]:
        """
        Convert credentials object to JSON-serializable dictionary.

        Args:
            credentials: Google OAuth2 credentials object

        Returns:
            Dictionary representation of credentials
        """
        return {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": credentials.scopes,
            "expiry": credentials.expiry.isoformat() if credentials.expiry else None,
        }

    def _dict_to_credentials(self, creds_dict: dict[str, Any]) -> Any:
        """
        Convert dictionary back to credentials object.

        Args:
            creds_dict: Dictionary representation of credentials

        Returns:
            Google OAuth2 credentials object
        """
        from google.oauth2.credentials import Credentials
        from datetime import datetime

        expiry = None
        if creds_dict.get("expiry"):
            expiry = datetime.fromisoformat(creds_dict["expiry"])

        return Credentials(
            token=creds_dict["token"],
            refresh_token=creds_dict.get("refresh_token"),
            token_uri=creds_dict["token_uri"],
            client_id=creds_dict["client_id"],
            client_secret=creds_dict["client_secret"],
            scopes=creds_dict.get("scopes"),
            expiry=expiry,
        )

    def _migrate_from_pickle(self) -> None:
        """
        Migrate existing pickle-based credentials to keyring.

        Checks for legacy token.pickle file and moves credentials to keyring.
        Deletes the pickle file after successful migration.
        """
        if not self.token_path.exists():
            return

        try:
            logger.info(f"Found legacy YouTube pickle file: {self.token_path}")
            with self.token_path.open("rb") as f:
                credentials = pickle.load(f)

            # Save to keyring
            self.save_credentials(credentials)
            logger.info("Successfully migrated YouTube credentials from pickle to keyring")
        except Exception as e:
            logger.warning(f"Failed to migrate YouTube credentials from pickle: {e}")


def clear_all_tokens(username: str = "default") -> None:
    """
    Clear all stored tokens from keyring (useful for logout/reset).

    Args:
        username: Username/identifier for keyring entries
    """
    try:
        keyring.delete_password(SERVICE_NAME, f"spotify_token_{username}")
        logger.info(f"Cleared Spotify token for user '{username}'")
    except keyring.errors.PasswordDeleteError:
        logger.debug(f"No Spotify token to clear for user '{username}'")

    try:
        keyring.delete_password(SERVICE_NAME, f"youtube_token_{username}")
        logger.info(f"Cleared YouTube token for user '{username}'")
    except keyring.errors.PasswordDeleteError:
        logger.debug(f"No YouTube token to clear for user '{username}'")
