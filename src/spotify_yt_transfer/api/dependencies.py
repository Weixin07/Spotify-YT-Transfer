"""FastAPI dependency injection functions."""

import logging

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from spotify_yt_transfer.clients import SpotifyClient, YouTubeClient
from spotify_yt_transfer.clients.errors import OAuthCredentialsMissing
from spotify_yt_transfer.database import TrackRepository, get_db
from spotify_yt_transfer.services import MigrationService, OAuthService, OAuthStateStore, PlaylistService

logger = logging.getLogger(__name__)

# Singleton clients (initialized lazily)
_spotify_client: SpotifyClient | None = None
_youtube_client: YouTubeClient | None = None


def init_clients() -> None:
    """
    Attempt to initialize API client singletons.

    In headless environments, the initialization can fail if OAuth tokens
    are not yet provisioned. Failures are logged and clients are created
    lazily on demand once credentials become available.
    """
    global _spotify_client, _youtube_client

    logger.info("Attempting to initialize Spotify and YouTube clients")

    try:
        _spotify_client = SpotifyClient()
    except OAuthCredentialsMissing as exc:
        logger.warning("Spotify client not ready: %s", exc)
        _spotify_client = None

    try:
        _youtube_client = YouTubeClient()
    except OAuthCredentialsMissing as exc:
        logger.warning("YouTube client not ready: %s", exc)
        _youtube_client = None


def _ensure_spotify_client() -> SpotifyClient:
    global _spotify_client

    if _spotify_client is None:
        try:
            _spotify_client = SpotifyClient()
        except OAuthCredentialsMissing as exc:
            logger.debug("Spotify client initialization blocked: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc

    return _spotify_client


def _ensure_youtube_client() -> YouTubeClient:
    global _youtube_client

    if _youtube_client is None:
        try:
            _youtube_client = YouTubeClient()
        except OAuthCredentialsMissing as exc:
            logger.debug("YouTube client initialization blocked: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc

    return _youtube_client


def get_spotify_client() -> SpotifyClient:
    """
    FastAPI dependency for the Spotify client.

    Returns:
        SpotifyClient singleton instance
    """
    return _ensure_spotify_client()


def get_youtube_client() -> YouTubeClient:
    """
    FastAPI dependency for the YouTube client.

    Returns:
        YouTubeClient singleton instance
    """
    return _ensure_youtube_client()


def get_track_repository(db: Session = Depends(get_db)) -> TrackRepository:
    """
    FastAPI dependency for track repository.

    Args:
        db: Database session from get_db dependency

    Returns:
        TrackRepository instance
    """
    return TrackRepository(db)


def get_oauth_service(db: Session = Depends(get_db)) -> OAuthService:
    """
    FastAPI dependency for OAuth service orchestration.

    Args:
        db: Database session from get_db dependency

    Returns:
        OAuthService instance
    """
    return OAuthService(OAuthStateStore(db))


def get_migration_service(
    spotify: SpotifyClient = Depends(get_spotify_client),
    youtube: YouTubeClient = Depends(get_youtube_client),
    repo: TrackRepository = Depends(get_track_repository),
) -> MigrationService:
    """
    FastAPI dependency for migration service.

    Args:
        spotify: Spotify client from dependency
        youtube: YouTube client from dependency
        repo: Track repository from dependency

    Returns:
        MigrationService instance
    """
    return MigrationService(spotify, youtube, repo)


def get_playlist_service(
    spotify: SpotifyClient = Depends(get_spotify_client),
    youtube: YouTubeClient = Depends(get_youtube_client),
    repo: TrackRepository = Depends(get_track_repository),
) -> PlaylistService:
    """
    FastAPI dependency for playlist service.

    Args:
        spotify: Spotify client from dependency
        youtube: YouTube client from dependency
        repo: Track repository from dependency

    Returns:
        PlaylistService instance
    """
    return PlaylistService(spotify, youtube, repo)
