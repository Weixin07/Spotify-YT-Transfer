import os
from dotenv import load_dotenv

# SQLAlchemy setup for same SQLite file
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Load environment variables from .env file
load_dotenv()

# Spotify Configurations
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")

# YouTube Configurations
YOUTUBE_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET")
YOUTUBE_REDIRECT_URI = os.getenv("YOUTUBE_REDIRECT_URI")

DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")

# Retry settings (centralize magic numbers)
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


# Point SQLAlchemy at the existing SQLite DB file
DB_PATH = os.getenv("DB_PATH", "data/matched_tracks.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

# Create engine and session factory
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# Base class for ORM models
Base = declarative_base()
