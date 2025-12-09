from unittest.mock import MagicMock

from spotify_yt_transfer.services.playlist_service import PlaylistService


class DummyResp:
    def __init__(self, content, status=200):
        self.content = content
        self.status_code = status

    def raise_for_status(self):
        """Mock method for requests.Response compatibility."""
        pass


def test_download_cover(monkeypatch):
    # Mock Spotify client
    mock_spotify = MagicMock()
    mock_spotify.sp.playlist.return_value = {
        "images": [{"width": 800, "height": 800, "url": "http://example.com/image.jpg"}]
    }

    # Mock requests.get
    mock_get = MagicMock(return_value=DummyResp(b"fake_image_data"))
    monkeypatch.setattr("spotify_yt_transfer.services.playlist_service.requests.get", mock_get)

    # Create PlaylistService instance with mock clients
    service = PlaylistService(mock_spotify, MagicMock(), MagicMock())

    # Test download
    result = service.download_playlist_cover("pid")
    assert result == b"fake_image_data"
