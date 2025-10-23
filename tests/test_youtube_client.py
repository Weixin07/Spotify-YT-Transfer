from unittest.mock import MagicMock, mock_open

from spotify_yt_transfer.clients.youtube_client import YouTubeClient


def test_youtube_client_init(monkeypatch):
    # Mock pickle.load to return a fake credential
    mock_cred = MagicMock()
    mock_cred.valid = True
    mock_cred.expired = False

    # Mock the Path.exists() method
    from pathlib import Path

    monkeypatch.setattr(Path, "exists", lambda self: True)

    # Mock pickle.load
    monkeypatch.setattr(
        "spotify_yt_transfer.clients.youtube_client.pickle.load", lambda f: mock_cred
    )

    # Mock build function
    mock_service = MagicMock()
    monkeypatch.setattr(
        "spotify_yt_transfer.clients.youtube_client.build", lambda *a, **k: mock_service
    )

    # Mock open for token.pickle
    mock_file = mock_open()
    monkeypatch.setattr("builtins.open", mock_file)

    client = YouTubeClient()
    assert client.service is not None
