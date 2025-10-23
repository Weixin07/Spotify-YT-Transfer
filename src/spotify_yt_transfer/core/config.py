"""Application configuration with environment variable support."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass(frozen=True)
class SpotifyConfig:
    """Spotify API configuration."""

    client_id: str
    client_secret: str
    redirect_uri: str
    retry_attempts: int
    retry_multiplier: float
    retry_max: int


@dataclass(frozen=True)
class YouTubeConfig:
    """YouTube Data API configuration."""

    client_id: str
    client_secret: str
    redirect_uri: str
    retry_attempts: int
    retry_multiplier: float
    retry_max: int


@dataclass(frozen=True)
class DatabaseConfig:
    """Database configuration."""

    path: str
    url: str

    @property
    def directory(self) -> Path:
        """Get the directory containing the database file."""
        return Path(self.path).parent


@dataclass(frozen=True)
class LoggingConfig:
    """Logging configuration."""

    file_name: str
    max_bytes: int
    backup_count: int


@dataclass(frozen=True)
class MatchingConfig:
    """Track matching configuration."""

    fuzz_threshold: int


@dataclass(frozen=True)
class CoverConfig:
    """Cover image download configuration."""

    min_width: int
    min_height: int
    enhance_size: int
    http_timeout: int


@dataclass(frozen=True)
class Settings:
    """Application settings aggregating all configuration sections."""

    debug: bool
    environment: str
    spotify: SpotifyConfig
    youtube: YouTubeConfig
    database: DatabaseConfig
    logging: LoggingConfig
    matching: MatchingConfig
    cover: CoverConfig


def _get_env(key: str, default: str | None = None, required: bool = False) -> str:
    """Get environment variable with optional validation."""
    value = os.getenv(key, default)
    if required and not value:
        raise ValueError(f"Required environment variable {key} is not set")
    return value or ""


def _load_settings() -> Settings:
    """Load application settings from environment variables."""
    # Debug mode
    debug = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")
    environment = os.getenv("APP_ENV", "development")

    # Spotify configuration
    spotify = SpotifyConfig(
        client_id=_get_env("SPOTIFY_CLIENT_ID", required=True),
        client_secret=_get_env("SPOTIFY_CLIENT_SECRET", required=True),
        redirect_uri=_get_env("SPOTIFY_REDIRECT_URI", required=True),
        retry_attempts=int(_get_env("SPOTIFY_RETRY_ATTEMPTS", "3")),
        retry_multiplier=float(_get_env("SPOTIFY_RETRY_MULTIPLIER", "1.0")),
        retry_max=int(_get_env("SPOTIFY_RETRY_MAX", "10")),
    )

    # YouTube configuration
    youtube = YouTubeConfig(
        client_id=_get_env("YOUTUBE_CLIENT_ID", required=True),
        client_secret=_get_env("YOUTUBE_CLIENT_SECRET", required=True),
        redirect_uri=_get_env("YOUTUBE_REDIRECT_URI", required=True),
        retry_attempts=int(_get_env("YOUTUBE_RETRY_ATTEMPTS", "3")),
        retry_multiplier=float(_get_env("YOUTUBE_RETRY_MULTIPLIER", "1.0")),
        retry_max=int(_get_env("YOUTUBE_RETRY_MAX", "10")),
    )

    # Database configuration
    db_path = _get_env("DB_PATH", "data/matched_tracks.db")
    database = DatabaseConfig(
        path=db_path,
        url=f"sqlite:///{db_path}",
    )

    # Logging configuration
    logging_config = LoggingConfig(
        file_name=_get_env("LOG_FILE_NAME", "migration.log"),
        max_bytes=int(_get_env("LOG_MAX_BYTES", str(10 * 1024 * 1024))),
        backup_count=int(_get_env("LOG_BACKUP_COUNT", "5")),
    )

    # Matching configuration
    matching = MatchingConfig(
        fuzz_threshold=int(_get_env("MATCH_FUZZ_THRESHOLD", "70")),
    )

    # Cover configuration
    cover = CoverConfig(
        min_width=int(_get_env("COVER_MIN_WIDTH", "640")),
        min_height=int(_get_env("COVER_MIN_HEIGHT", "480")),
        enhance_size=int(_get_env("COVER_ENHANCE_SIZE", "640")),
        http_timeout=int(_get_env("HTTP_REQUEST_TIMEOUT", "10")),
    )

    return Settings(
        debug=debug,
        environment=environment,
        spotify=spotify,
        youtube=youtube,
        database=database,
        logging=logging_config,
        matching=matching,
        cover=cover,
    )


# Global settings instance
settings = _load_settings()
