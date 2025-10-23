import pytest

from spotify_yt_transfer.clients.errors import OAuthCredentialsMissing
from spotify_yt_transfer.clients.spotify_client import SpotifyClient


def test_spotify_client_requires_cached_credentials(monkeypatch):
    class DummyHandler:
        def __init__(self, *args, **kwargs):
            pass

        def get_cached_token(self):
            return None

    monkeypatch.setattr(
        "spotify_yt_transfer.clients.spotify_client.KeyringCacheHandler",
        DummyHandler,
    )

    with pytest.raises(OAuthCredentialsMissing):
        SpotifyClient()


def test_spotify_client_initializes_with_cached_token(monkeypatch):
    class DummyHandler:
        def __init__(self, *args, **kwargs):
            pass

        def get_cached_token(self):
            return {"access_token": "token", "refresh_token": "refresh"}

    monkeypatch.setattr(
        "spotify_yt_transfer.clients.spotify_client.KeyringCacheHandler",
        DummyHandler,
    )
    monkeypatch.setattr(
        "spotify_yt_transfer.clients.spotify_client.SpotifyOAuth",
        lambda *args, **kwargs: object(),
    )
    created = {}

    def _mock_spotify(*args, **kwargs):
        created["client"] = object()
        return created["client"]

    monkeypatch.setattr(
        "spotify_yt_transfer.clients.spotify_client.spotipy.Spotify",
        _mock_spotify,
    )

    client = SpotifyClient()
    assert client.sp is created["client"]
