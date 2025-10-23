"""FastAPI dependency injection functions."""

import logging

from fastapi import Depends
from sqlalchemy.orm import Session

from spotify_yt_transfer.clients import SpotifyClient, YouTubeClient
from spotify_yt_transfer.database import TrackRepository, get_db
from spotify_yt_transfer.services import MigrationService, PlaylistService

logger = logging.getLogger(__name__)

# Singleton clients (initialized at startup)
_spotify_client: SpotifyClient | None = None
_youtube_client: YouTubeClient | None = None


def init_clients() -> None:
    """
    Initialize client singletons.

    Call this in the FastAPI lifespan startup event.
    """
    global _spotify_client, _youtube_client

    logger.info("Initializing API clients")
    _spotify_client = SpotifyClient()
    _youtube_client = YouTubeClient()
    logger.info("API clients initialized successfully")


def get_spotify_client() -> SpotifyClient:
    """
    FastAPI dependency for Spotify client.

    Returns:
        SpotifyClient singleton instance

    Raises:
        RuntimeError: If client not initialized
    """
    if _spotify_client is None:
        raise RuntimeError("Spotify client not initialized. Call init_clients() first.")
    return _spotify_client


def get_youtube_client() -> YouTubeClient:
    """
    FastAPI dependency for YouTube client.

    Returns:
        YouTubeClient singleton instance

    Raises:
        RuntimeError: If client not initialized
    """
    if _youtube_client is None:
        raise RuntimeError("YouTube client not initialized. Call init_clients() first.")
    return _youtube_client


def get_track_repository(db: Session = Depends(get_db)) -> TrackRepository:
    """
    FastAPI dependency for track repository.

    Args:
        db: Database session from get_db dependency

    Returns:
        TrackRepository instance
    """
    return TrackRepository(db)


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
