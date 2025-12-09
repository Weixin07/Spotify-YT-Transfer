from unittest.mock import MagicMock

import pytest

from spotify_yt_transfer.clients.errors import OAuthCredentialsMissing
from spotify_yt_transfer.clients.youtube_client import YouTubeClient


def test_youtube_client_requires_credentials(monkeypatch):
    mock_storage = MagicMock()
    mock_storage.get_credentials.return_value = None
    monkeypatch.setattr(
        "spotify_yt_transfer.clients.youtube_client.YouTubeTokenStorage",
        lambda *_args, **_kwargs: mock_storage,
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
        lambda *_args, **_kwargs: mock_storage,
    )

    monkeypatch.setattr(
        "spotify_yt_transfer.clients.youtube_client.build",
        lambda *_args, **_kwargs: MagicMock(),
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
        lambda *_args, **_kwargs: mock_storage,
    )

    expected_service = MagicMock()
    monkeypatch.setattr(
        "spotify_yt_transfer.clients.youtube_client.build",
        lambda *_args, **_kwargs: expected_service,
    )

    client = YouTubeClient()

    assert client.service is expected_service
    assert client.creds is mock_cred
    mock_storage.get_credentials.assert_called_once()


def test_cache_collision_prevention(monkeypatch):
    class DummyCred:
        valid = True
        expired = False

    mock_storage = MagicMock()
    mock_storage.get_credentials.return_value = DummyCred()

    monkeypatch.setattr(
        "spotify_yt_transfer.clients.youtube_client.YouTubeTokenStorage",
        lambda *_args, **_kwargs: mock_storage,
    )

    responses = [
        {
            "items": [
                {"id": {"videoId": "candidate1"}, "snippet": {"title": "Candidate 1"}},
            ],
        },
        {"items": [{"id": {"videoId": "video123"}}]},
    ]

    class FakeRequest:
        def __init__(self, response):
            self._response = response

        def execute(self):
            return self._response

    class FakeSearchService:
        def __init__(self, response_queue):
            self._response_queue = list(response_queue)
            self.calls = 0

        def list(self, **_kwargs):
            self.calls += 1
            if not self._response_queue:
                raise AssertionError("No more responses available for fake search service")
            return FakeRequest(self._response_queue.pop(0))

    class FakeYouTubeService:
        def __init__(self, response_queue):
            self.search_service = FakeSearchService(response_queue)

        def search(self):
            return self.search_service

    fake_service = FakeYouTubeService(responses)

    monkeypatch.setattr(
        "spotify_yt_transfer.clients.youtube_client.build",
        lambda *_args, **_kwargs: fake_service,
    )

    client = YouTubeClient()
    client.clear_search_cache()

    candidates = client.search_video_candidates("test query")
    video_id = client.search_video("test query")

    assert isinstance(candidates, list)
    assert candidates and all(isinstance(item, tuple) for item in candidates)
    assert isinstance(video_id, str) or video_id is None
    assert fake_service.search_service.calls == 2
    assert video_id == "video123"

    client.clear_search_cache()
