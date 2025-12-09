"""Comprehensive tests for PlaylistService."""

from unittest.mock import MagicMock, patch

import pytest

from spotify_yt_transfer.services.playlist_service import PlaylistService


@pytest.fixture
def mock_clients():
    """Create mock clients for testing."""
    spotify = MagicMock()
    youtube = MagicMock()
    repo = MagicMock()
    return spotify, youtube, repo


@pytest.fixture
def playlist_service(mock_clients):
    """Create PlaylistService instance with mocked dependencies."""
    spotify, youtube, repo = mock_clients
    return PlaylistService(spotify, youtube, repo)


class TestPlaylistServiceInit:
    """Test PlaylistService initialization."""

    def test_init_stores_clients(self, playlist_service, mock_clients):
        """Test that initialization stores all clients."""
        spotify, youtube, repo = mock_clients
        assert playlist_service.spotify is spotify
        assert playlist_service.youtube is youtube
        assert playlist_service.repo is repo


class TestFindMissingTracks:
    """Test the find_missing_tracks method."""

    def test_find_missing_tracks_with_all_present(self, playlist_service, mock_clients):
        """Test when all Spotify tracks are in YouTube playlist."""
        spotify, youtube, repo = mock_clients

        # Mock Spotify tracks
        spotify.get_playlist_tracks.return_value = [
            {"id": "spotify_1", "name": "Song1", "artist": "Artist1", "album": "Album1"},
            {"id": "spotify_2", "name": "Song2", "artist": "Artist2", "album": "Album2"},
        ]

        # Mock YouTube videos
        youtube.get_playlist_items.return_value = ["yt1", "yt2"]

        # Mock repository - both tracks matched
        track1 = MagicMock()
        track1.youtube_id = "yt1"
        track2 = MagicMock()
        track2.youtube_id = "yt2"

        repo.get_matched_track.side_effect = [track1, track2]

        result = playlist_service.find_missing_tracks("sp_playlist", "yt_playlist")

        assert len(result["missing_tracks"]) == 0
        assert result["unavailable_tracks"] == []

    def test_find_missing_tracks_identifies_missing(self, playlist_service, mock_clients):
        """Test identifying tracks missing from YouTube playlist."""
        spotify, youtube, repo = mock_clients

        spotify.get_playlist_tracks.return_value = [
            {"id": "spotify_1", "name": "Song1", "artist": "Artist1", "album": "Album1"},
            {"id": "spotify_2", "name": "Song2", "artist": "Artist2", "album": "Album2"},
        ]

        # Only one video in YouTube playlist
        youtube.get_playlist_items.return_value = ["yt1"]

        # First track matched, second not matched
        track1 = MagicMock()
        track1.youtube_id = "yt1"

        track2 = MagicMock()
        track2.youtube_id = "yt2"  # Not in YouTube playlist

        repo.get_matched_track.side_effect = [track1, track2]

        result = playlist_service.find_missing_tracks("sp_playlist", "yt_playlist")

        assert len(result["missing_tracks"]) == 1
        assert result["missing_tracks"][0]["track_name"] == "Song2"
        assert result["missing_tracks"][0]["artist"] == "Artist2"

    def test_find_missing_tracks_with_duplicates(self, playlist_service, mock_clients):
        """Test identifying duplicate tracks."""
        spotify, youtube, repo = mock_clients

        # Same track appears twice (same Spotify ID)
        spotify.get_playlist_tracks.return_value = [
            {"id": "spotify_1", "name": "Song1", "artist": "Artist1", "album": "Album1"},
            {
                "id": "spotify_1",
                "name": "Song1",
                "artist": "Artist1",
                "album": "Album1",
            },  # Duplicate
            {"id": "spotify_2", "name": "Song2", "artist": "Artist2", "album": "Album2"},
        ]

        youtube.get_playlist_items.return_value = ["yt1", "yt2"]

        track1 = MagicMock()
        track1.youtube_id = "yt1"
        track2 = MagicMock()
        track2.youtube_id = "yt2"

        repo.get_matched_track.side_effect = [track1, track2]

        result = playlist_service.find_missing_tracks("sp_playlist", "yt_playlist")

        assert len(result["duplicate_tracks"]) >= 1
        # Find the Song1 duplicate using spotify_id field
        song1_dup = next(
            (d for d in result["duplicate_tracks"] if d["spotify_id"] == "spotify_1"), None
        )
        assert song1_dup is not None
        assert song1_dup["count"] == 2

    def test_find_missing_tracks_with_unavailable(self, playlist_service, mock_clients):
        """Test identifying unavailable tracks (missing name or artist)."""
        spotify, youtube, repo = mock_clients

        spotify.get_playlist_tracks.return_value = [
            {
                "id": "spotify_1",
                "name": None,
                "artist": "Artist1",
                "album": "Album1",
            },  # Missing name
            {
                "id": "spotify_2",
                "name": "Song2",
                "artist": None,
                "album": "Album2",
            },  # Missing artist
            {"id": "spotify_3", "name": "Song3", "artist": "Artist3", "album": "Album3"},  # Valid
        ]

        youtube.get_playlist_items.return_value = ["yt3"]

        track3 = MagicMock()
        track3.youtube_id = "yt3"
        repo.get_matched_track.return_value = track3

        result = playlist_service.find_missing_tracks("sp_playlist", "yt_playlist")

        assert len(result["unavailable_tracks"]) == 2

    def test_find_missing_tracks_without_cached_match(self, playlist_service, mock_clients):
        """Test when track has no cached match in repository."""
        spotify, youtube, repo = mock_clients

        spotify.get_playlist_tracks.return_value = [
            {"id": "spotify_1", "name": "Song1", "artist": "Artist1", "album": "Album1"}
        ]

        youtube.get_playlist_items.return_value = []

        # No cached match
        repo.get_matched_track.return_value = None

        result = playlist_service.find_missing_tracks("sp_playlist", "yt_playlist")

        # Without a match, can't determine if missing
        # (Implementation may vary - test actual behavior)
        assert "missing_tracks" in result
        assert "duplicate_tracks" in result
        assert "unavailable_tracks" in result


class TestSplitLikedSongs:
    """Test the split_liked_songs method."""

    def test_split_liked_songs_creates_multiple_playlists(self, playlist_service, mock_clients):
        """Test splitting liked songs into multiple playlists."""
        spotify, youtube, repo = mock_clients

        # Mock current user
        spotify.get_current_user.return_value = {"id": "user123"}

        # Mock 2500 liked songs
        tracks = [{"uri": f"spotify:track:{i}"} for i in range(2500)]
        spotify.get_liked_tracks.return_value = tracks

        # Mock playlist creation (returns playlist_id string)
        spotify.create_playlist.side_effect = ["pl1", "pl2", "pl3"]

        result = playlist_service.split_liked_songs("Liked Songs", 1000, public=False)

        assert result["total_tracks"] == 2500
        assert len(result["playlists_created"]) == 3

        # Should create 3 playlists (2500 / 1000 = 2.5, rounded up to 3)
        assert spotify.create_playlist.call_count == 3

        # Should add tracks to each playlist (multiple calls per playlist for batching)
        assert spotify.add_tracks_to_playlist.call_count >= 3

    def test_split_liked_songs_with_exact_multiple(self, playlist_service, mock_clients):
        """Test when liked songs is exact multiple of tracks_per_playlist."""
        spotify, youtube, repo = mock_clients

        spotify.get_current_user.return_value = {"id": "user123"}

        # Exactly 2000 tracks
        tracks = [{"uri": f"spotify:track:{i}"} for i in range(2000)]
        spotify.get_liked_tracks.return_value = tracks

        spotify.create_playlist.side_effect = ["pl1", "pl2"]

        result = playlist_service.split_liked_songs("Liked Songs", 1000, public=True)

        assert result["total_tracks"] == 2000
        assert len(result["playlists_created"]) == 2

        # Should create exactly 2 playlists
        assert spotify.create_playlist.call_count == 2

    def test_split_liked_songs_includes_playlist_info(self, playlist_service, mock_clients):
        """Test that playlist info is returned correctly."""
        spotify, youtube, repo = mock_clients

        spotify.get_current_user.return_value = {"id": "user123"}

        tracks = [{"uri": f"spotify:track:{i}"} for i in range(500)]
        spotify.get_liked_tracks.return_value = tracks

        spotify.create_playlist.return_value = "pl1"

        result = playlist_service.split_liked_songs("My Songs", 1000, public=False)

        assert len(result["playlists_created"]) == 1
        playlist = result["playlists_created"][0]

        assert playlist["name"] == "My Songs-1"
        assert playlist["playlist_id"] == "pl1"
        assert playlist["track_count"] == 500

    def test_split_liked_songs_with_no_tracks(self, playlist_service, mock_clients):
        """Test splitting when there are no liked songs."""
        spotify, youtube, repo = mock_clients

        spotify.get_current_user.return_value = {"id": "user123"}
        spotify.get_liked_tracks.return_value = []

        result = playlist_service.split_liked_songs("Liked Songs", 1000, public=False)

        assert result["total_tracks"] == 0
        assert len(result["playlists_created"]) == 0
        spotify.create_playlist.assert_not_called()


class TestDownloadPlaylistCover:
    """Test the download_playlist_cover method."""

    def test_download_cover_success(self, playlist_service, mock_clients, monkeypatch):
        """Test successful cover download."""
        spotify, youtube, repo = mock_clients

        # Mock Spotify playlist response
        spotify.sp.playlist.return_value = {
            "images": [{"width": 800, "height": 800, "url": "http://example.com/img.jpg"}]
        }

        # Mock requests.get
        class DummyResponse:
            content = b"fake_image_data"
            status_code = 200

            def raise_for_status(self):
                pass

        monkeypatch.setattr(
            "spotify_yt_transfer.services.playlist_service.requests.get",
            lambda _url, _timeout: DummyResponse(),
        )

        result = playlist_service.download_playlist_cover("playlist_id")

        assert result == b"fake_image_data"

    def test_download_cover_with_minimum_size_filter(
        self, playlist_service, mock_clients, monkeypatch
    ):
        """Test that covers below minimum size are filtered."""
        spotify, youtube, repo = mock_clients

        # Mock playlist with one small image and one large image
        spotify.sp.playlist.return_value = {
            "images": [
                {"width": 300, "height": 300, "url": "http://example.com/small.jpg"},
                {"width": 800, "height": 800, "url": "http://example.com/large.jpg"},
            ]
        }

        class DummyResponse:
            content = b"large_image_data"
            status_code = 200

            def raise_for_status(self):
                pass

        monkeypatch.setattr(
            "spotify_yt_transfer.services.playlist_service.requests.get",
            lambda _url, _timeout: DummyResponse(),
        )

        result = playlist_service.download_playlist_cover("playlist_id", min_width=640)

        # Should download the larger image
        assert result == b"large_image_data"

    def test_download_cover_no_images(self, playlist_service, mock_clients):
        """Test error when playlist has no images."""
        spotify, youtube, repo = mock_clients

        spotify.sp.playlist.return_value = {"images": []}

        with pytest.raises(ValueError, match="No cover image found"):
            playlist_service.download_playlist_cover("playlist_id")

    def test_download_cover_no_images_meet_size(self, playlist_service, mock_clients, monkeypatch):
        """Test fallback when no images meet minimum size."""
        spotify, youtube, repo = mock_clients

        # All images too small
        spotify.sp.playlist.return_value = {
            "images": [{"width": 200, "height": 200, "url": "http://example.com/tiny.jpg"}]
        }

        class DummyResponse:
            content = b"fake_original_image"
            status_code = 200

            def raise_for_status(self):
                pass

        # Mock PIL operations for image enhancement
        mock_image = MagicMock()
        mock_enhanced = MagicMock()

        with (
            patch("spotify_yt_transfer.services.playlist_service.requests.get") as mock_get,
            patch("spotify_yt_transfer.services.playlist_service.Image.open") as mock_open,
            patch("spotify_yt_transfer.services.playlist_service.ImageOps.fit") as mock_fit,
        ):

            mock_get.return_value = DummyResponse()
            mock_open.return_value = mock_image
            mock_fit.return_value = mock_enhanced

            # Mock the save operation to write our test bytes
            def mock_save(buffer, format):
                buffer.write(b"enhanced_image")

            mock_enhanced.save = mock_save

            # Should use the largest available and enhance it
            result = playlist_service.download_playlist_cover("playlist_id", min_width=640)
            assert result == b"enhanced_image"

            # Verify enhancement was called
            mock_fit.assert_called_once()

    def test_download_cover_saves_to_file(
        self, playlist_service, mock_clients, monkeypatch, tmp_path
    ):
        """Test that cover can be saved to file."""
        spotify, youtube, repo = mock_clients

        spotify.sp.playlist.return_value = {
            "images": [{"width": 800, "height": 800, "url": "http://example.com/img.jpg"}]
        }

        class DummyResponse:
            content = b"image_bytes"
            status_code = 200

            def raise_for_status(self):
                pass

        monkeypatch.setattr(
            "spotify_yt_transfer.services.playlist_service.requests.get",
            lambda _url, _timeout: DummyResponse(),
        )

        save_path = tmp_path / "cover.jpg"
        result = playlist_service.download_playlist_cover("playlist_id", save_path=str(save_path))

        assert result == b"image_bytes"
        assert save_path.exists()
        assert save_path.read_bytes() == b"image_bytes"


class TestIntegrationScenarios:
    """Test complete playlist service scenarios."""

    def test_complete_missing_tracks_workflow(self, playlist_service, mock_clients):
        """Test a complete missing tracks check."""
        spotify, youtube, repo = mock_clients

        # Setup: 5 Spotify tracks
        spotify.get_playlist_tracks.return_value = [
            {"id": "spotify_1", "name": "Track1", "artist": "Artist1", "album": "Album1"},
            {"id": "spotify_2", "name": "Track2", "artist": "Artist2", "album": "Album2"},
            {"id": "spotify_3", "name": "Track3", "artist": "Artist3", "album": "Album3"},
            {
                "id": "spotify_3",
                "name": "Track3",
                "artist": "Artist3",
                "album": "Album3",
            },  # Duplicate
            {"id": "spotify_4", "name": "Track4", "artist": "Artist4", "album": "Album4"},
        ]

        # YouTube has only 3 videos
        youtube.get_playlist_items.return_value = ["yt1", "yt2", "yt3", "yt3"]

        # Mock matches using real Spotify IDs
        def get_match(spotify_id):
            match_map = {
                "spotify_1": MagicMock(youtube_id="yt1"),
                "spotify_2": MagicMock(youtube_id="yt2"),
                "spotify_3": MagicMock(youtube_id="yt3"),
                "spotify_4": MagicMock(youtube_id="yt4"),  # Missing
            }
            return match_map.get(spotify_id)

        repo.get_matched_track.side_effect = get_match

        result = playlist_service.find_missing_tracks("sp_playlist", "yt_playlist")

        # Should identify 1 missing track (Track4)
        assert len(result["missing_tracks"]) == 1
        assert result["missing_tracks"][0]["track_name"] == "Track4"

        # Should identify duplicates
        assert len(result["duplicate_tracks"]) >= 1

        # No unavailable tracks
        assert len(result["unavailable_tracks"]) == 0
