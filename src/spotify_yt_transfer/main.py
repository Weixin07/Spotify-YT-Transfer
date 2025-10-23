"""FastAPI application entry point."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from spotify_yt_transfer.api import dependencies
from spotify_yt_transfer.api.v1.routes import auth, health, migration, utilities
from spotify_yt_transfer.core import setup_logging
from spotify_yt_transfer.database import init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.

    Handles startup and shutdown events.

    Args:
        app: FastAPI application instance

    Yields:
        None during application runtime
    """
    # Startup
    setup_logging()
    logger.info("Starting up: Initializing database")
    init_db()

    logger.info("Initializing API clients")
    dependencies.init_clients()

    logger.info("Application startup complete")

    yield

    # Shutdown
    logger.info("Shutting down application")


# Create FastAPI application
app = FastAPI(
    title="Spotify to YouTube Music Playlist Migrator",
    description=(
        "Migrate Spotify playlists to YouTube Music with intelligent track matching. "
        "Supports playlist migration, liked songs splitting, missing track detection, "
        "and playlist cover downloads."
    ),
    version="1.0.0",
    contact={
        "name": "Developer",
        "email": "faithlin07@gmail.com",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
    lifespan=lifespan,
    openapi_tags=[
        {"name": "Health", "description": "Health check and monitoring endpoints"},
        {"name": "Auth", "description": "OAuth authentication callbacks"},
        {"name": "Migration", "description": "Playlist migration operations"},
        {"name": "Utilities", "description": "Utility operations for playlists"},
    ],
    swagger_ui_parameters={
        "docExpansion": "none",
        "defaultModelsExpandDepth": -1,
    },
    redoc_ui_parameters={
        "hideHostname": True,
    },
)

# Rate limiting: 10 requests per minute per IP
limiter = Limiter(key_func=get_remote_address, default_limits=["10/minute"])
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Prometheus metrics
instrumentator = Instrumentator()
instrumentator.instrument(app).expose(app)

# Include API routers
app.include_router(health.router, tags=["Health"])
app.include_router(auth.router, prefix="/v1", tags=["Auth"])
app.include_router(migration.router, prefix="/v1", tags=["Migration"])
app.include_router(utilities.router, prefix="/v1", tags=["Utilities"])

logger.info("FastAPI application created successfully")


def cli() -> None:
    """
    CLI entry point for running the application.

    Used by the console_scripts entry point defined in pyproject.toml.
    """
    import uvicorn

    logger.info("Starting application via CLI")
    uvicorn.run(
        "spotify_yt_transfer.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    cli()
