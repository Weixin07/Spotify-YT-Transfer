"""Database session management and initialization."""

import logging
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from spotify_yt_transfer.core.config import settings

logger = logging.getLogger(__name__)

# Create declarative base
Base = declarative_base()

# Create engine with configuration
engine = create_engine(
    settings.database.url,
    connect_args={"check_same_thread": False},
    echo=settings.debug,
    pool_pre_ping=True,  # Verify connections before using
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency function that yields a database session.

    Automatically commits on success and rolls back on exception.
    Always closes the session when done.

    Yields:
        Session: SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """
    Initialize the database by creating all tables.

    Creates the database directory if it doesn't exist.
    """
    # Ensure database directory exists
    db_dir = settings.database.directory
    db_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Database directory ensured: {db_dir}")

    # Import all models to register them with Base
    from spotify_yt_transfer.database import models  # noqa: F401

    # Create all tables
    Base.metadata.create_all(bind=engine)
    logger.info(f"Database initialized at: {settings.database.path}")
