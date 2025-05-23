# conftest.py
import os, importlib, pytest, sys
from pathlib import Path

# allow pytest to import your top-level modules
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))


@pytest.fixture(autouse=True)
def use_temp_db(tmp_path, monkeypatch):
    test_db = tmp_path / "test_tracks.db"
    monkeypatch.setenv("DB_PATH", str(test_db))
    import config, models, data_storage

    # reload config so it picks up DB_PATH
    importlib.reload(config)
    # reload your ORM definitions before data_storage so metadata is populated
    importlib.reload(models)
    # now reload data_storage so init_db() will call create_all() on a metadata that includes your tables
    importlib.reload(data_storage)
    yield
    # ensure engine is disposed so file can be removed
    from config import engine

    engine.dispose()
