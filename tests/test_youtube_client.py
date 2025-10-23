from unittest.mock import MagicMock

import pytest

from spotify_yt_transfer.clients.errors import OAuthCredentialsMissing
from spotify_yt_transfer.clients.youtube_client import YouTubeClient


def test_youtube_client_requires_credentials(monkeypatch):
    mock_storage = MagicMock()
    mock_storage.get_credentials.return_value = None
    monkeypatch.setattr(
        "spotify_yt_transfer.clients.youtube_client.YouTubeTokenStorage",
        lambda *args, **kwargs: mock_storage,
    )

    with pytest.raises(OAuthCredentialsMissing):
        YouTubeClient()


def test_youtube_client_refreshes_expired_credentials(monkeypatch):
    refreshed = {"called": False}

    class DummyCred:
        valid = False
        expired = True
        refresh_token = "refresh"

        def refresh(self, _request):
            refreshed["called"] = True

    mock_storage = MagicMock()
    mock_storage.get_credentials.return_value = DummyCred()

    monkeypatch.setattr(
        "spotify_yt_transfer.clients.youtube_client.YouTubeTokenStorage",
        lambda *args, **kwargs: mock_storage,
    )

    monkeypatch.setattr(
        "spotify_yt_transfer.clients.youtube_client.build",
        lambda *args, **kwargs: MagicMock(),
    )

    YouTubeClient()

    assert refreshed["called"] is True
    mock_storage.save_credentials.assert_called_once()


def test_youtube_client_uses_valid_credentials(monkeypatch):
    mock_cred = MagicMock()
    mock_cred.valid = True
    mock_cred.expired = False

    mock_storage = MagicMock()
    mock_storage.get_credentials.return_value = mock_cred

    monkeypatch.setattr(
        "spotify_yt_transfer.clients.youtube_client.YouTubeTokenStorage",
        lambda *args, **kwargs: mock_storage,
    )

    expected_service = MagicMock()
    monkeypatch.setattr(
        "spotify_yt_transfer.clients.youtube_client.build",
        lambda *args, **kwargs: expected_service,
    )

    client = YouTubeClient()

    assert client.service is expected_service
    assert client.creds is mock_cred
    mock_storage.get_credentials.assert_called_once()
