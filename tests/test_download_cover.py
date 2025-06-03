import pytest
from io import BytesIO
import os
from download_cover import download_playlist_cover


class DummyResp:
    def __init__(self, content, status=200):
        self.content = content
        self.status_code = status


@pytest.fixture(autouse=True)
def stub_requests_and_spotipy(monkeypatch):
    # stub HTTP
    monkeypatch.setattr("download_cover.SpotifyOAuth", lambda *args, **kwargs: None)

    # stub SpotifyOAuth + Spotify
    class DummySP:
        def playlist(self, pid):
            return {"images": [{"width": 800, "height": 800, "url": "u"}]}

    # avoid real OAuth flow
    monkeypatch.setattr(
        "download_cover.spotipy.Spotify", lambda *args, **kwargs: DummySP()
    )
    # stub the actual client factory


def test_download_cover(tmp_path):
    out = tmp_path / "cover.jpg"
    download_playlist_cover("pid", str(out))
    assert out.exists()
