import pytest
from youtube_client import YouTubeClient


def test_youtube_client_init(monkeypatch):
    # stub token flow and build
    monkeypatch.setattr("youtube_client.os.path.exists", lambda p: False)

    class DummyCred:
        pass

    class Flow:
        def run_local_server(self, port):
            return DummyCred()

    monkeypatch.setattr(
        "youtube_client.InstalledAppFlow",
        type("F", (), {"from_client_config": lambda *a, **k: Flow()}),
    )
    monkeypatch.setattr("youtube_client.build", lambda *a, **k: object())
    # avoid pickle.dump trying to pickle a local DummyCred class
    monkeypatch.setattr("youtube_client.pickle.dump", lambda obj, file: None)
    client = YouTubeClient()
    assert client.service is not None
