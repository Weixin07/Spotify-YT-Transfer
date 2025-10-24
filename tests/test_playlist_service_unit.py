"""Unit tests for PlaylistService covering comparison, splitting, and cover downloads."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from spotify_yt_transfer.services.playlist_service import PlaylistService


@pytest.fixture
def spotify_client():
    client = MagicMock()
    client.sp = MagicMock()
    return client


@pytest.fixture
def youtube_client():
    return MagicMock()


@pytest.fixture
def repository():
    return MagicMock()


@pytest.fixture
def service(spotify_client, youtube_client, repository):
    return PlaylistService(spotify_client, youtube_client, repository)


def test_find_missing_tracks_detects_missing_duplicates_and_unavailable(
    service, spotify_client, youtube_client, repository
):
    spotify_client.get_playlist_tracks.return_value = [
        {"id": "spotify_1", "name": "Song1", "artist": "Artist1", "album": "Album1"},
        {"id": "spotify_1", "name": "Song1", "artist": "Artist1", "album": "Album1"},  # duplicate
        {"id": "spotify_2", "name": "Song2", "artist": "Artist2", "album": "Album2"},
        {"id": None, "name": None, "artist": "Artist3"},  # unavailable
    ]
    repository.get_matched_track.side_effect = [
        SimpleNamespace(youtube_id="vid_missing"),
        None,
    ]
    youtube_client.get_playlist_items.return_value = ["vid_present"]

    result = service.find_missing_tracks("spotify_playlist", "youtube_playlist")

    missing = result["missing_tracks"]
    duplicates = result["duplicate_tracks"]
    unavailable = result["unavailable_tracks"]

    assert len(missing) == 2
    assert missing[0]["spotify_id"] == "spotify_1"
    assert missing[0]["cached_youtube_id"] == "vid_missing"
    assert missing[1]["spotify_id"] == "spotify_2"
    assert missing[1]["cached_youtube_id"] is None

    assert duplicates == [{"spotify_id": "spotify_1", "count": 2}]
    assert len(unavailable) == 1


def test_split_liked_songs_creates_chunked_playlists(service, spotify_client):
    spotify_client.get_current_user.return_value = {"id": "user123"}
    spotify_client.get_liked_tracks.return_value = [
        {"id": "spotify_1", "uri": "uri1"},
        {"id": "spotify_2", "uri": "uri2"},
        {"id": "spotify_3", "uri": "uri3"},
    ]
    spotify_client.create_playlist.side_effect = ["pl1", "pl2"]

    result = service.split_liked_songs(
        playlist_base_name="Liked Songs",
        tracks_per_playlist=2,
        public=True,
    )

    assert result["total_tracks"] == 3
    assert [p["track_count"] for p in result["playlists_created"]] == [2, 1]

    spotify_client.create_playlist.assert_any_call(
        user_id="user123",
        name="Liked Songs-1",
        description="Liked Songs split 1/2 (tracks 1-2)",
        public=True,
    )
    spotify_client.create_playlist.assert_any_call(
        user_id="user123",
        name="Liked Songs-2",
        description="Liked Songs split 2/2 (tracks 3-3)",
        public=True,
    )
    add_calls = spotify_client.add_tracks_to_playlist.call_args_list
    assert add_calls[0].args == ("pl1", ["uri1", "uri2"])
    assert add_calls[1].args == ("pl2", ["uri3"])


def test_download_playlist_cover_returns_image_bytes_for_valid_image(
    service, spotify_client, monkeypatch
):
    spotify_client.sp.playlist.return_value = {
        "images": [{"width": 640, "height": 640, "url": "https://example.com/image.jpg"}]
    }

    mock_response = MagicMock()
    mock_response.content = b"jpeg-data"
    mock_response.raise_for_status.return_value = None
    monkeypatch.setattr("spotify_yt_transfer.services.playlist_service.requests.get", lambda *_, **__: mock_response)

    result = service.download_playlist_cover("playlist123")

    assert result == b"jpeg-data"


def test_download_playlist_cover_enhances_low_resolution_image(
    service, spotify_client, monkeypatch
):
    spotify_client.sp.playlist.return_value = {
        "images": [
            {"width": 100, "height": 100, "url": "https://example.com/small.jpg"},
            {"width": 50, "height": 50, "url": "https://example.com/smaller.jpg"},
        ]
    }

    mock_response = MagicMock()
    mock_response.content = b"raw-image"
    mock_response.raise_for_status.return_value = None
    monkeypatch.setattr(
        "spotify_yt_transfer.services.playlist_service.requests.get",
        lambda *_, **__: mock_response,
    )

    class DummyImage:
        def save(self, buffer, format):
            buffer.write(b"enhanced-jpeg")

    monkeypatch.setattr(
        "spotify_yt_transfer.services.playlist_service.Image.open",
        lambda *_args, **_kwargs: MagicMock(),
    )
    monkeypatch.setattr(
        "spotify_yt_transfer.services.playlist_service.ImageOps.fit",
        lambda *_args, **_kwargs: DummyImage(),
    )

    result = service.download_playlist_cover("playlist123")

    assert result == b"enhanced-jpeg"
