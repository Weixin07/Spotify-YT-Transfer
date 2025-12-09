"""OAuth service utilities for managing headless authorization flows."""

import logging
import secrets
from dataclasses import dataclass
from typing import Any, Protocol, cast

from google_auth_oauthlib.flow import Flow
from spotipy.oauth2 import SpotifyOAuth
from sqlalchemy.orm import Session

from spotify_yt_transfer.core.config import settings
from spotify_yt_transfer.core.token_storage import KeyringCacheHandler, YouTubeTokenStorage
from spotify_yt_transfer.database.models import OAuthState

logger = logging.getLogger(__name__)


class OAuthStateError(RuntimeError):
    """Raised when OAuth state validation fails."""


class AuthorizeUrl(Protocol):
    """Protocol for authorization URL responses."""

    authorize_url: str
    state: str


@dataclass(frozen=True)
class OAuthAuthorizeResponse:
    """Value object representing an authorization URL and associated state."""

    authorize_url: str
    state: str


class OAuthStateStore:
    """
    Manage persistence and validation of OAuth states.

    Stores state tokens in the database to enable stateless API servers.
    """

    def __init__(self, db: Session):
        self.db = db

    def create(self, provider: str, state: str) -> None:
        """
        Persist a new OAuth state for the specified provider.

        Args:
            provider: OAuth provider identifier (e.g., 'spotify')
            state: Randomly generated state string
        """
        OAuthState.purge_expired(self.db)
        entity = OAuthState(state=state, provider=provider)
        self.db.merge(entity)  # upsert to avoid duplicates for retries
        logger.debug("Stored OAuth state for provider=%s", provider)

    def consume(self, provider: str, state: str) -> None:
        """
        Validate and remove an OAuth state.

        Args:
            provider: OAuth provider identifier
            state: State string received in callback

        Raises:
            OAuthStateError: If the state is missing or expired
        """
        if not state:
            raise OAuthStateError("Missing state parameter")

        if not OAuthState.exists(self.db, state, provider):
            raise OAuthStateError("Invalid or expired OAuth state")

        self.db.query(OAuthState).filter_by(state=state, provider=provider).delete()
        logger.debug("Consumed OAuth state for provider=%s", provider)


class OAuthService:
    """Service orchestrating Spotify and YouTube OAuth flows for headless deployments."""

    def __init__(self, state_store: OAuthStateStore):
        self.state_store = state_store
        self.spotify_cache_handler = KeyringCacheHandler(
            username=settings.token_storage.username,
            cache_path=settings.token_storage.spotify_cache_path,
        )
        self.youtube_token_storage = YouTubeTokenStorage(
            username=settings.token_storage.username,
            token_path=settings.token_storage.youtube_token_path,
        )

    # ===== Spotify =====

    def build_spotify_authorize_url(self) -> OAuthAuthorizeResponse:
        """
        Generate a Spotify authorization URL suitable for headless environments.

        Returns:
            OAuthAuthorizeResponse containing the URL and state string
        """
        state = secrets.token_urlsafe(32)
        spotify_oauth = SpotifyOAuth(
            client_id=settings.spotify.client_id,
            client_secret=settings.spotify.client_secret,
            redirect_uri=settings.spotify.redirect_uri,
            scope="playlist-read-private user-library-read playlist-modify-private playlist-modify-public",
            cache_handler=self.spotify_cache_handler,
            open_browser=False,
        )

        authorize_url = spotify_oauth.get_authorize_url(state=state)
        self.state_store.create("spotify", state)
        self.state_store.db.commit()
        logger.info("Generated Spotify authorize URL for state=%s", state)
        return OAuthAuthorizeResponse(authorize_url=authorize_url, state=state)

    def exchange_spotify_code(self, code: str, state: str) -> dict[str, Any]:
        """
        Exchange Spotify authorization code for tokens after validating state.

        Args:
            code: Authorization code received from Spotify
            state: State string returned in the callback

        Returns:
            Token information dictionary provided by Spotipy

        Raises:
            OAuthStateError: If state validation fails
        """
        self.state_store.consume("spotify", state)
        self.state_store.db.commit()

        spotify_oauth = SpotifyOAuth(
            client_id=settings.spotify.client_id,
            client_secret=settings.spotify.client_secret,
            redirect_uri=settings.spotify.redirect_uri,
            scope="playlist-read-private user-library-read playlist-modify-private playlist-modify-public",
            cache_handler=self.spotify_cache_handler,
            open_browser=False,
        )

        token_info = cast("dict[str, Any]", spotify_oauth.get_access_token(code, check_cache=False))
        logger.info("Spotify token exchange succeeded")
        return token_info

    # ===== YouTube =====

    def _build_youtube_flow(self, state: str | None = None) -> Flow:
        """Create a Google OAuth flow configured for YouTube."""
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": settings.youtube.client_id,
                    "client_secret": settings.youtube.client_secret,
                    "redirect_uris": [settings.youtube.redirect_uri],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=["https://www.googleapis.com/auth/youtube.force-ssl"],
            state=state,
        )
        flow.redirect_uri = settings.youtube.redirect_uri
        return flow

    def build_youtube_authorize_url(self) -> OAuthAuthorizeResponse:
        """
        Generate a YouTube authorization URL suitable for headless environments.

        Returns:
            OAuthAuthorizeResponse containing the URL and state string
        """
        state = secrets.token_urlsafe(32)
        flow = self._build_youtube_flow(state=state)
        authorize_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            state=state,
        )
        self.state_store.create("youtube", state)
        self.state_store.db.commit()
        logger.info("Generated YouTube authorize URL for state=%s", state)
        return OAuthAuthorizeResponse(authorize_url=authorize_url, state=state)

    def exchange_youtube_code(self, code: str, state: str) -> dict[str, Any]:
        """
        Exchange YouTube authorization code for tokens after validating state.

        Args:
            code: Authorization code from YouTube
            state: State value returned in the callback

        Returns:
            Dictionary representation of stored credentials
        """
        self.state_store.consume("youtube", state)
        self.state_store.db.commit()

        flow = self._build_youtube_flow(state=state)
        flow.fetch_token(code=code)

        credentials = flow.credentials
        self.youtube_token_storage.save_credentials(credentials)
        logger.info("YouTube token exchange succeeded")

        return {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "scopes": list(credentials.scopes or []),
            "expiry": credentials.expiry.isoformat() if credentials.expiry else None,
        }
