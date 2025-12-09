"""Integration-style tests for API routes ensuring structured error handling."""

from contextlib import contextmanager
from typing import Any

import pytest
from fastapi.testclient import TestClient
from requests import RequestException
from spotipy.client import SpotifyException

from spotify_yt_transfer.api import dependencies
from spotify_yt_transfer.clients.errors import OAuthCredentialsMissing
from spotify_yt_transfer.main import app
from spotify_yt_transfer.services import (
    CacheService,
    MigrationService,
    PlaylistService,
    QuotaExceededError,
    ServiceError,
    ValidationServiceError,
)
from spotify_yt_transfer.services.cache_service import CacheInvalidationResult


@contextmanager
def override_dependency(provider, replacement):
    app.dependency_overrides[provider] = lambda: replacement
    try:
        yield
    finally:
        app.dependency_overrides.pop(provider, None)


@pytest.fixture(autouse=True)
def patch_startup(monkeypatch):
    monkeypatch.setattr("spotify_yt_transfer.main.init_db", lambda: None)
    monkeypatch.setattr("spotify_yt_transfer.main.setup_logging", lambda: None)


class StubMigrationService(MigrationService):
    def __init__(self, behavior: str):
        self.behavior = behavior

    def migrate_playlist(
        self, youtube_playlist_title: str, spotify_playlist_id: str | None = None
    ) -> dict[str, Any]:
        if self.behavior == "success":
            return {"message": "ok", "youtube_playlist_id": "yt123"}
        if self.behavior == "quota":
            raise QuotaExceededError("quota hit", service="youtube")
        if self.behavior == "oauth":
            raise OAuthCredentialsMissing("missing creds")
        if self.behavior == "spotify":
            raise SpotifyException(500, -1, "spotify down")
        if self.behavior == "service":
            raise ServiceError("service issue", code="service_error", details={"ctx": "migration"})
        raise RuntimeError("boom")

    def __getattr__(self, item):
        raise AttributeError(item)


class StubPlaylistService(PlaylistService):
    def __init__(self, behavior: str, response: Any = None):
        self.behavior = behavior
        self.response = response or {}

    def find_missing_tracks(
        self, spotify_playlist_id: str, youtube_playlist_id: str
    ) -> dict[str, Any]:
        if self.behavior == "missing-success":
            return {"missing_tracks": [], "duplicate_tracks": [], "unavailable_tracks": []}
        if self.behavior == "missing-error":
            raise ServiceError("missing failed", code="service_error")
        raise NotImplementedError

    def split_liked_songs(self, *args, **kwargs) -> dict[str, Any]:
        if self.behavior == "split-success":
            return {"message": "ok", "total_tracks": 10, "playlists_created": []}
        if self.behavior == "split-validate":
            raise ValidationServiceError("bad params", details={"field": "tracks_per_playlist"})
        if self.behavior == "split-spotify":
            raise SpotifyException(500, -1, "spotify down")
        if self.behavior == "split-service":
            raise ServiceError("split failed")
        raise NotImplementedError

    def download_playlist_cover(self, *args, **kwargs) -> bytes:
        if self.behavior == "cover-success":
            return b"bytes"
        if self.behavior == "cover-missing":
            raise ValueError("not found")
        if self.behavior == "cover-http":
            raise RequestException("timeout")
        if self.behavior == "cover-service":
            raise ServiceError("cover failed")
        raise NotImplementedError


class MockRepository:
    """Mock repository for testing."""

    def commit(self):
        pass


class StubCacheService(CacheService):
    def __init__(self, behavior: str):
        self.behavior = behavior
        # Mock repository with commit method for route handler
        self.repository = MockRepository()

    def invalidate(self, youtube: bool, matched: bool, failed: bool):
        if self.behavior == "invalidate-success":
            return CacheInvalidationResult(
                youtube_cache_cleared=youtube,
                matched_tracks_removed=int(matched),
                failed_tracks_removed=int(failed),
            )
        if self.behavior == "invalidate-validate":
            raise ValidationServiceError("invalid combo")
        if self.behavior == "invalidate-service":
            raise ServiceError("cache fail")
        raise NotImplementedError


def test_migrate_playlist_success():
    service = StubMigrationService("success")
    with (
        override_dependency(dependencies.get_migration_service, service),
        TestClient(app) as client,
    ):
        resp = client.post(
            "/v1/migrate", json={"spotify_playlist_id": "abc", "youtube_playlist_title": "foo"}
        )
    assert resp.status_code == 200
    assert resp.json()["youtube_playlist_id"] == "yt123"


@pytest.mark.parametrize(
    "behavior,status,code",
    [
        ("quota", 429, "quota_exceeded"),
        ("oauth", 401, "oauth_credentials_missing"),
        ("spotify", 502, "external_service_error"),
        ("service", 500, "service_error"),
    ],
)
def test_migrate_playlist_error_branches(behavior, status, code):
    service = StubMigrationService(behavior)
    with (
        override_dependency(dependencies.get_migration_service, service),
        TestClient(app) as client,
    ):
        resp = client.post(
            "/v1/migrate", json={"spotify_playlist_id": "abc", "youtube_playlist_title": "foo"}
        )
    assert resp.status_code == status
    payload = resp.json()
    assert payload["detail"]["code"] == code


def test_migrate_playlist_unexpected_error():
    service = StubMigrationService("unexpected")
    with (
        override_dependency(dependencies.get_migration_service, service),
        TestClient(app) as client,
    ):
        resp = client.post(
            "/v1/migrate", json={"spotify_playlist_id": "abc", "youtube_playlist_title": "foo"}
        )
    assert resp.status_code == 500
    assert resp.json()["detail"]["code"] == "unexpected_error"


def test_check_missing_tracks_success():
    service = StubPlaylistService("missing-success")
    with override_dependency(dependencies.get_playlist_service, service), TestClient(app) as client:
        resp = client.get(
            "/v1/check-missing", params={"spotify_playlist_id": "sp", "youtube_playlist_id": "yt"}
        )
    assert resp.status_code == 200
    assert resp.json()["missing_tracks"] == []


def test_check_missing_tracks_error():
    service = StubPlaylistService("missing-error")
    with override_dependency(dependencies.get_playlist_service, service), TestClient(app) as client:
        resp = client.get(
            "/v1/check-missing", params={"spotify_playlist_id": "sp", "youtube_playlist_id": "yt"}
        )
    assert resp.status_code == 500
    payload = resp.json()
    assert "detail" in payload
    # Verify structured error response
    assert payload["detail"]["code"] == "service_error"
    assert payload["detail"]["message"] == "missing failed"


@pytest.mark.parametrize(
    "behavior,status,code",
    [
        ("split-success", 200, None),
        ("split-validate", 422, "validation_error"),
        ("split-spotify", 502, "external_service_error"),
        ("split-service", 500, "service_error"),
    ],
)
def test_split_liked_songs_branches(behavior, status, code):
    service = StubPlaylistService(behavior)
    with override_dependency(dependencies.get_playlist_service, service), TestClient(app) as client:
        resp = client.post(
            "/v1/split-liked-songs", json={"playlist_base_name": "Base", "tracks_per_playlist": 100}
        )
    assert resp.status_code == status
    if code:
        assert resp.json()["detail"]["code"] == code


@pytest.mark.parametrize(
    "behavior,status,code",
    [
        ("cover-success", 200, None),
        ("cover-missing", 404, "cover_not_found"),
        ("cover-http", 502, "external_service_error"),
        ("cover-service", 500, "service_error"),
    ],
)
def test_download_cover_branches(behavior, status, code):
    service = StubPlaylistService(behavior)
    with override_dependency(dependencies.get_playlist_service, service), TestClient(app) as client:
        resp = client.get("/v1/download-cover", params={"playlist_id": "sp"})
    assert resp.status_code == status
    if code:
        assert resp.json()["detail"]["code"] == code


@pytest.mark.parametrize(
    "behavior,status,code",
    [
        ("invalidate-success", 200, None),
        ("invalidate-validate", 422, "validation_error"),
        ("invalidate-service", 500, "service_error"),
    ],
)
def test_cache_invalidate_branches(behavior, status, code):
    service = StubCacheService(behavior)
    with override_dependency(dependencies.get_cache_service, service), TestClient(app) as client:
        payload = {
            "matched_tracks": True,
            "failed_tracks": True,
            "youtube_search": True,
        }
        resp = client.post("/v1/cache/invalidate", json=payload)
    assert resp.status_code == status
    if code:
        assert resp.json()["detail"]["code"] == code
