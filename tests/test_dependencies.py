import pytest
from fastapi import HTTPException

from spotify_yt_transfer.api import dependencies
from spotify_yt_transfer.clients.errors import OAuthCredentialsMissing


def test_get_spotify_client_raises_when_credentials_missing(monkeypatch):
    dependencies._spotify_client = None

    def _failing_client():
        raise OAuthCredentialsMissing("Missing Spotify credentials")

    monkeypatch.setattr("spotify_yt_transfer.api.dependencies.SpotifyClient", _failing_client)

    with pytest.raises(HTTPException) as excinfo:
        dependencies.get_spotify_client()

    assert excinfo.value.status_code == 503


def test_get_spotify_client_caches_instance(monkeypatch):
    dependencies._spotify_client = None
    instance = object()

    monkeypatch.setattr("spotify_yt_transfer.api.dependencies.SpotifyClient", lambda: instance)

    first = dependencies.get_spotify_client()
    second = dependencies.get_spotify_client()

    assert first is instance
    assert second is instance
    dependencies._spotify_client = None


def test_get_youtube_client_raises_when_credentials_missing(monkeypatch):
    dependencies._youtube_client = None

    def _failing_client():
        raise OAuthCredentialsMissing("Missing YouTube credentials")

    monkeypatch.setattr("spotify_yt_transfer.api.dependencies.YouTubeClient", _failing_client)

    with pytest.raises(HTTPException) as excinfo:
        dependencies.get_youtube_client()

    assert excinfo.value.status_code == 503


def test_get_youtube_client_caches_instance(monkeypatch):
    dependencies._youtube_client = None
    instance = object()

    monkeypatch.setattr("spotify_yt_transfer.api.dependencies.YouTubeClient", lambda: instance)

    first = dependencies.get_youtube_client()
    second = dependencies.get_youtube_client()

    assert first is instance
    assert second is instance
    dependencies._youtube_client = None
