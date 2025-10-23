"""Health check and monitoring endpoints."""

import logging

from fastapi import APIRouter, status

from spotify_yt_transfer.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Health check",
    description="Returns the health status of the service",
    response_description="Service is healthy",
)
async def health_check() -> dict[str, str]:
    """
    Health check endpoint.

    Returns:
        Dictionary with status message
    """
    return {"status": "healthy", "service": "spotify-yt-transfer"}


@router.get(
    "/ready",
    status_code=status.HTTP_200_OK,
    summary="Readiness check",
    description="Returns readiness status indicating if service can accept requests",
    response_description="Service is ready",
)
async def readiness_check() -> dict[str, str]:
    """
    Readiness check endpoint.

    Returns:
        Dictionary with readiness status
    """
    # Could add checks for database connectivity, API availability, etc.
    return {
        "status": "ready",
        "environment": settings.environment,
        "database": settings.database.path,
    }


@router.get(
    "/",
    summary="Root endpoint",
    description="Returns welcome message",
    response_description="Welcome message",
)
async def root() -> dict[str, str]:
    """
    Root endpoint.

    Returns:
        Welcome message dictionary
    """
    return {
        "message": "Welcome to Spotify-YT-Transfer API",
        "version": "1.0.0",
        "docs": "/docs",
    }
