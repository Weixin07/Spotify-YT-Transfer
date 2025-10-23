# conftest.py
import importlib
import sys
from pathlib import Path

import pytest

# allow pytest to import your top-level modules
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))


@pytest.fixture(autouse=True)
def use_temp_db(tmp_path, monkeypatch):
    test_db = tmp_path / "test_tracks.db"
    monkeypatch.setenv("DB_PATH", str(test_db))

    # Import new modules
    from spotify_yt_transfer.core import config
    from spotify_yt_transfer.database import base, init_db, models, repository

    # Reload modules to pick up new DB_PATH
    importlib.reload(config)
    importlib.reload(base)
    importlib.reload(models)
    importlib.reload(repository)

    # Initialize database with new structure
    init_db()

    yield

    # Ensure engine is disposed so file can be removed
    from spotify_yt_transfer.database.base import engine

    engine.dispose()
