"""Database session management and initialization."""

import logging
from collections.abc import Generator
from pathlib import Path

from alembic import command
from alembic.config import Config
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


def _get_alembic_config() -> Config:
    """Build an Alembic configuration object using runtime settings."""
    config_dir = Path(__file__).resolve().parent
    alembic_cfg = Config(str(config_dir / "alembic.ini"))

    # Ensure Alembic points to the runtime database and migrations directory
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database.url)
    alembic_cfg.set_main_option("script_location", str((config_dir / "migrations").resolve()))
    alembic_cfg.set_main_option("prepend_sys_path", str(config_dir.resolve()))
    return alembic_cfg


def _run_migrations() -> None:
    """Upgrade database schema to the latest revision."""
    logger.info("Applying database migrations")
    alembic_cfg = _get_alembic_config()
    command.upgrade(alembic_cfg, "head")
    logger.info("Database schema is up to date")


def init_db() -> None:
    """
    Initialize the database by applying Alembic migrations.

    Ensures the database directory exists before running migrations.
    """
    # Ensure database directory exists
    db_dir = settings.database.directory
    db_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Database directory ensured: %s", db_dir)

    # Import models so Alembic env has metadata when autogenerating revisions
    from spotify_yt_transfer.database import models  # noqa: F401

    _run_migrations()

