import os
from dotenv import load_dotenv
from dataclasses import dataclass

# Load environment variables from .env file
load_dotenv()

# DEBUG flag
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")

# Retry settings
SPOTIFY_RETRY_ATTEMPTS = int(os.getenv("SPOTIFY_RETRY_ATTEMPTS", "3"))
SPOTIFY_RETRY_MULTIPLIER = float(os.getenv("SPOTIFY_RETRY_MULTIPLIER", "1"))
SPOTIFY_RETRY_MAX = int(os.getenv("SPOTIFY_RETRY_MAX", "10"))

YOUTUBE_RETRY_ATTEMPTS = int(os.getenv("YOUTUBE_RETRY_ATTEMPTS", "3"))
YOUTUBE_RETRY_MULTIPLIER = float(os.getenv("YOUTUBE_RETRY_MULTIPLIER", "1"))
YOUTUBE_RETRY_MAX = int(os.getenv("YOUTUBE_RETRY_MAX", "10"))

# Fuzzy-match threshold
MATCH_FUZZ_THRESHOLD = int(os.getenv("MATCH_FUZZ_THRESHOLD", "70"))

# Cover download defaults
COVER_MIN_WIDTH = int(os.getenv("COVER_MIN_WIDTH", "640"))
COVER_MIN_HEIGHT = int(os.getenv("COVER_MIN_HEIGHT", "480"))
COVER_ENHANCE_SIZE = int(os.getenv("COVER_ENHANCE_SIZE", "640"))
HTTP_REQUEST_TIMEOUT = int(os.getenv("HTTP_REQUEST_TIMEOUT", "10"))

# Logging rotation defaults
LOG_FILE_NAME = os.getenv("LOG_FILE_NAME", "migration.log")
LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024)))
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))

# Database path and URL
DB_PATH = os.getenv("DB_PATH", "data/matched_tracks.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"


# ----- Typed configs -----
@dataclass(frozen=True)
class SpotifyConfig:
    client_id: str
    client_secret: str
    redirect_uri: str
    retry_attempts: int
    retry_multiplier: float
    retry_max: int


@dataclass(frozen=True)
class YouTubeConfig:
    client_id: str
    client_secret: str
    redirect_uri: str
    retry_attempts: int
    retry_multiplier: float
    retry_max: int


@dataclass(frozen=True)
class DBConfig:
    path: str
    url: str


@dataclass(frozen=True)
class LoggingConfig:
    file_name: str
    max_bytes: int
    backup_count: int


# Instantiate grouped configs
SPOTIFY_CONFIG = SpotifyConfig(
    client_id=os.getenv("SPOTIFY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
    redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI"),
    retry_attempts=SPOTIFY_RETRY_ATTEMPTS,
    retry_multiplier=SPOTIFY_RETRY_MULTIPLIER,
    retry_max=SPOTIFY_RETRY_MAX,
)

YOUTUBE_CONFIG = YouTubeConfig(
    client_id=os.getenv("YOUTUBE_CLIENT_ID"),
    client_secret=os.getenv("YOUTUBE_CLIENT_SECRET"),
    redirect_uri=os.getenv("YOUTUBE_REDIRECT_URI"),
    retry_attempts=YOUTUBE_RETRY_ATTEMPTS,
    retry_multiplier=YOUTUBE_RETRY_MULTIPLIER,
    retry_max=YOUTUBE_RETRY_MAX,
)

DB_CONFIG = DBConfig(path=DB_PATH, url=SQLALCHEMY_DATABASE_URL)

LOGGING_CONFIG = LoggingConfig(
    file_name=LOG_FILE_NAME,
    max_bytes=LOG_MAX_BYTES,
    backup_count=LOG_BACKUP_COUNT,
)

# Backward-compatible constants
SPOTIFY_CLIENT_ID = SPOTIFY_CONFIG.client_id
SPOTIFY_CLIENT_SECRET = SPOTIFY_CONFIG.client_secret
SPOTIFY_REDIRECT_URI = SPOTIFY_CONFIG.redirect_uri

YOUTUBE_CLIENT_ID = YOUTUBE_CONFIG.client_id
YOUTUBE_CLIENT_SECRET = YOUTUBE_CONFIG.client_secret
YOUTUBE_REDIRECT_URI = YOUTUBE_CONFIG.redirect_uri

# SQLAlchemy setup (echo tied to DEBUG)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

engine = create_engine(
    DB_CONFIG.url,
    connect_args={"check_same_thread": False},
    echo=DEBUG,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
