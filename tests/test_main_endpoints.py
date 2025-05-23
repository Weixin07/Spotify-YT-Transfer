from fastapi.testclient import TestClient
import pytest
from main import app

client = TestClient(app)


def test_read_root():
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["message"].startswith("Welcome")


def test_check_missing_endpoint(monkeypatch):
    monkeypatch.setattr(
        "main.find_missing_tracks",
        lambda s, y: {
            "missing_tracks": [],
            "duplicate_tracks": [],
            "unavailable_tracks": [],
        },
    )
    r = client.get(
        "/check_missing",
        params={"spotify_playlist_id": "s", "youtube_playlist_id": "y"},
    )
    assert r.status_code == 200
    assert r.json()["missing_tracks"] == []


def test_youtube_playlist_not_found(monkeypatch):
    # stub a dummy YouTubeClient into app.state so get_youtube_client() works
    from main import app

    class DummyYT:
        def find_playlist_by_name(self, name):
            return None

    app.state.youtube = DummyYT()
    r = client.get("/youtube/playlist", params={"playlist_name": "foo"})
    assert r.status_code == 404
