from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from spotify_yt_transfer.api import dependencies
from spotify_yt_transfer.main import app
from spotify_yt_transfer.services import CacheInvalidationResult

# Create test client with lifespan context disabled for testing
client = TestClient(app, raise_server_exceptions=False)


def test_health_endpoint():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


def test_check_missing_endpoint():
    # Mock the dependency using FastAPI's override mechanism
    mock_service = MagicMock()
    mock_service.find_missing_tracks.return_value = {
        "missing_tracks": [],
        "duplicate_tracks": [],
        "unavailable_tracks": [],
    }

    app.dependency_overrides[dependencies.get_playlist_service] = lambda: mock_service

    try:
        r = client.get(
            "/v1/check-missing",
            params={"spotify_playlist_id": "s", "youtube_playlist_id": "y"},
        )
        assert r.status_code == 200
        assert r.json()["missing_tracks"] == []
    finally:
        # Clean up override
        app.dependency_overrides.clear()


def test_cache_invalidation_endpoint_invokes_service():
    class StubCacheService:
        def __init__(self):
            self.repository = MagicMock()

        def invalidate(self, clear_youtube_cache, purge_matched, purge_failed):
            assert clear_youtube_cache is False
            assert purge_matched is True
            assert purge_failed is True
            return CacheInvalidationResult(
                matched_tracks_removed=3, failed_tracks_removed=1, youtube_cache_cleared=False
            )

    app.dependency_overrides[dependencies.get_cache_service] = lambda: StubCacheService()

    try:
        response = client.post(
            "/v1/cache/invalidate",
            json={
                "matched_tracks": True,
                "failed_tracks": True,
                "youtube_search": False,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["matched_tracks_removed"] == 3
    assert payload["failed_tracks_removed"] == 1
    assert payload["youtube_cache_cleared"] is False


def test_migrate_endpoint_accepts_post_body():
    mock_service = MagicMock()
    mock_service.migrate_playlist.return_value = {
        "message": "Migration complete",
        "youtube_playlist_id": "YT123",
    }

    app.dependency_overrides[dependencies.get_migration_service] = lambda: mock_service

    try:
        r = client.post(
            "/v1/migrate",
            json={"spotify_playlist_id": "SP123", "youtube_playlist_title": "Test Playlist"},
        )
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    payload = r.json()
    assert payload["youtube_playlist_id"] == "YT123"
    mock_service.migrate_playlist.assert_called_once_with("Test Playlist", "SP123")


def test_youtube_playlist_not_found():
    # Mock the YouTube client dependency
    mock_yt = MagicMock()
    mock_yt.find_playlist_by_name.return_value = None

    app.dependency_overrides[dependencies.get_youtube_client] = lambda: mock_yt

    try:
        r = client.get("/v1/youtube/playlist", params={"playlist_name": "foo"})
        assert r.status_code == 404
    finally:
        # Clean up override
        app.dependency_overrides.clear()
