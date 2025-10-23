"""Centralized logging configuration."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from spotify_yt_transfer.core.config import settings


def setup_logging() -> None:
    """Configure application-wide logging with console and file handlers."""
    # Determine log level based on debug mode
    log_level = logging.DEBUG if settings.debug else logging.INFO

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    # Ensure log directory exists
    log_path = Path(settings.logging.file_name)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Rotating file handler
    file_handler = RotatingFileHandler(
        filename=settings.logging.file_name,
        maxBytes=settings.logging.max_bytes,
        backupCount=settings.logging.backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Suppress verbose Google API logging unless in debug mode
    if not settings.debug:
        logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.WARNING)
        logging.getLogger("googleapiclient.discovery").setLevel(logging.WARNING)
        logging.getLogger("google.auth").setLevel(logging.WARNING)

    logging.info(f"Logging initialized (level={logging.getLevelName(log_level)})")
