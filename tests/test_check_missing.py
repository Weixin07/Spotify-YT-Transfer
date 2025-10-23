from unittest.mock import MagicMock

from spotify_yt_transfer.services.playlist_service import PlaylistService


def test_find_missing_tracks():
    # Mock clients
    mock_spotify = MagicMock()
    mock_spotify.get_playlist_tracks.return_value = [
        {"name": "A", "artist": "X", "album": "Z"},
        {"name": None, "artist": None},
        {"name": "A", "artist": "X", "album": "Z"},
    ]

    mock_youtube = MagicMock()
    mock_youtube.get_playlist_items.return_value = ["yt1"]

    # Mock repository
    mock_repo = MagicMock()
    mock_repo.get_matched_track.side_effect = lambda uid: (
        MagicMock(youtube_id="yt1") if uid == "A|X" else None
    )

    # Create service instance
    service = PlaylistService(mock_spotify, mock_youtube, mock_repo)

    # Test find_missing_tracks
    res = service.find_missing_tracks("s", "y")
    assert isinstance(res, dict)
    assert "missing_tracks" in res
    assert "duplicate_tracks" in res
    assert "unavailable_tracks" in res
