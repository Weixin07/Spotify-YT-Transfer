"""Comprehensive tests for MigrationService."""

from unittest.mock import MagicMock

import pytest
from googleapiclient.errors import HttpError

from spotify_yt_transfer.services.exceptions import QuotaExceededError
from spotify_yt_transfer.services.migration_service import MigrationService, _is_quota_exceeded


@pytest.fixture
def mock_clients():
    """Create mock clients for testing."""
    spotify = MagicMock()
    youtube = MagicMock()
    repo = MagicMock()
    return spotify, youtube, repo


@pytest.fixture
def migration_service(mock_clients):
    """Create MigrationService instance with mocked dependencies."""
    spotify, youtube, repo = mock_clients
    return MigrationService(spotify, youtube, repo)


class TestQuotaExceeded:
    """Test the quota exceeded detection helper."""

    def test_is_quota_exceeded_returns_true_for_quota_error(self):
        """Test that quota exceeded errors are correctly identified."""
        # Create a mock HttpError with quota exceeded
        mock_resp = MagicMock()
        mock_resp.status = 403

        error_content = b'{"error": {"errors": [{"reason": "quotaExceeded"}]}}'
        error = HttpError(resp=mock_resp, content=error_content)

        assert _is_quota_exceeded(error) is True

    def test_is_quota_exceeded_returns_false_for_other_errors(self):
        """Test that non-quota errors return False."""
        mock_resp = MagicMock()
        mock_resp.status = 404

        error_content = b'{"error": {"errors": [{"reason": "notFound"}]}}'
        error = HttpError(resp=mock_resp, content=error_content)

        assert _is_quota_exceeded(error) is False

    def test_is_quota_exceeded_handles_malformed_error(self):
        """Test that malformed errors don't crash."""
        mock_resp = MagicMock()
        mock_resp.status = 500

        error = HttpError(resp=mock_resp, content=b"bad json")

        assert _is_quota_exceeded(error) is False


class TestMigrationServiceInit:
    """Test MigrationService initialization."""

    def test_init_stores_clients(self, migration_service, mock_clients):
        """Test that initialization stores all clients."""
        spotify, youtube, repo = mock_clients
        assert migration_service.spotify is spotify
        assert migration_service.youtube is youtube
        assert migration_service.repo is repo


class TestMigratePlaylist:
    """Test the main migrate_playlist method."""

    def test_migrate_empty_playlist_returns_early(self, migration_service, mock_clients):
        """Test that empty playlists are handled gracefully."""
        spotify, youtube, repo = mock_clients

        # Mock empty playlist
        spotify.get_playlist_tracks.return_value = []

        result = migration_service.migrate_playlist("Test Playlist", "playlist_id")

        assert result["message"] == "No tracks to migrate"
        assert result["youtube_playlist_id"] == ""
        youtube.create_playlist.assert_not_called()

    def test_migrate_uses_liked_songs_when_no_id(self, migration_service, mock_clients):
        """Test that None playlist_id triggers liked songs fetch."""
        spotify, youtube, repo = mock_clients

        spotify.get_liked_tracks.return_value = []

        migration_service.migrate_playlist("Test Playlist", None)

        spotify.get_liked_tracks.assert_called_once()
        spotify.get_playlist_tracks.assert_not_called()

    def test_migrate_creates_new_playlist_when_not_exists(self, migration_service, mock_clients):
        """Test playlist creation when it doesn't exist."""
        spotify, youtube, repo = mock_clients

        # Mock Spotify tracks
        spotify.get_playlist_tracks.return_value = [
            {"name": "Song1", "artist": "Artist1", "album": "Album1"}
        ]

        # Mock YouTube playlist not found
        youtube.find_playlist_by_name.return_value = None
        youtube.create_playlist.return_value = "PL_new_123"

        # Mock search returns video
        youtube.search_video.return_value = "vid123"

        # Mock no cached track
        repo.get_matched_track.return_value = None
        repo.get_failed_track.return_value = None

        result = migration_service.migrate_playlist("Test Playlist", "sp_id")

        youtube.create_playlist.assert_called_once_with(
            title="Test Playlist", description="Migrated from Spotify"
        )
        assert result["youtube_playlist_id"] == "PL_new_123"

    def test_migrate_uses_existing_playlist_when_found(self, migration_service, mock_clients):
        """Test that existing playlist is reused."""
        spotify, youtube, repo = mock_clients

        spotify.get_playlist_tracks.return_value = [{"name": "Song1", "artist": "Artist1"}]

        # Mock existing playlist
        youtube.find_playlist_by_name.return_value = "PL_existing"
        youtube.search_video.return_value = "vid123"

        repo.get_matched_track.return_value = None
        repo.get_failed_track.return_value = None

        result = migration_service.migrate_playlist("Test Playlist", "sp_id")

        youtube.create_playlist.assert_not_called()
        assert result["youtube_playlist_id"] == "PL_existing"

    def test_migrate_uses_cached_track_when_available(self, migration_service, mock_clients):
        """Test that cached tracks are used instead of searching."""
        spotify, youtube, repo = mock_clients

        spotify.get_playlist_tracks.return_value = [
            {"id": "spotify_track_1", "name": "Song1", "artist": "Artist1"}
        ]

        youtube.find_playlist_by_name.return_value = "PL_test"

        # Mock cached track
        cached_track = MagicMock()
        cached_track.youtube_id = "cached_vid_123"
        repo.get_matched_track.return_value = cached_track
        repo.get_failed_track.return_value = None

        migration_service.migrate_playlist("Test Playlist", "sp_id")

        # Should NOT search YouTube candidates when using cache
        youtube.search_video_candidates.assert_not_called()

        # Should add the cached video
        youtube.add_video_to_playlist.assert_called_once_with("PL_test", "cached_vid_123")

    def test_migrate_searches_and_caches_new_track(self, migration_service, mock_clients):
        """Test that new tracks are searched with fuzzy matching and cached."""
        spotify, youtube, repo = mock_clients

        spotify.get_playlist_tracks.return_value = [
            {"id": "spotify_new", "name": "NewSong", "artist": "NewArtist", "album": "NewAlbum"}
        ]

        youtube.find_playlist_by_name.return_value = "PL_test"
        # Mock candidates for fuzzy matching (exact substring match will work)
        youtube.search_video_candidates.return_value = [
            ("found_vid_456", "NewSong NewArtist Official Video"),  # Contains exact substring
            ("other_vid", "NewSong Cover by Someone"),
        ]

        repo.get_matched_track.return_value = None
        repo.get_failed_track.return_value = None

        migration_service.migrate_playlist("Test Playlist", "sp_id")

        # Should search YouTube candidates
        youtube.search_video_candidates.assert_called_once_with("NewSong NewArtist", max_results=10)

        # Should cache the fuzzy-matched result using real Spotify ID
        repo.save_matched_track.assert_called_once_with(
            spotify_id="spotify_new",  # Real Spotify ID
            song_name="NewSong",
            artist="NewArtist",
            youtube_id="found_vid_456",  # Fuzzy matcher picks the best match
            album="NewAlbum",
            youtube_title="NewSong NewArtist Official Video",
        )

    def test_migrate_skips_tracks_without_name_or_artist(self, migration_service, mock_clients):
        """Test that tracks with missing metadata are skipped."""
        spotify, youtube, repo = mock_clients

        spotify.get_playlist_tracks.return_value = [
            {"id": "spotify_1", "name": None, "artist": "Artist1"},  # Missing name
            {"id": "spotify_2", "name": "Song2", "artist": None},  # Missing artist
            {"id": "spotify_3", "name": "Song3", "artist": "Artist3"},  # Valid
        ]

        youtube.find_playlist_by_name.return_value = "PL_test"
        youtube.search_video_candidates.return_value = [("vid3", "Song3 - Artist3")]

        repo.get_matched_track.return_value = None
        repo.get_failed_track.return_value = None

        migration_service.migrate_playlist("Test Playlist", "sp_id")

        # Should only search for the valid track
        youtube.search_video_candidates.assert_called_once_with("Song3 Artist3", max_results=10)

    def test_migrate_handles_quota_exceeded_during_search(self, migration_service, mock_clients):
        """Test that quota exceeded during search raises exception."""
        spotify, youtube, repo = mock_clients

        spotify.get_playlist_tracks.return_value = [
            {"id": "spotify_1", "name": "Song1", "artist": "Artist1"}
        ]

        youtube.find_playlist_by_name.return_value = "PL_test"

        # Mock quota exceeded error
        mock_resp = MagicMock()
        mock_resp.status = 403
        error_content = b'{"error": {"errors": [{"reason": "quotaExceeded"}]}}'
        quota_error = HttpError(resp=mock_resp, content=error_content)

        youtube.search_video_candidates.side_effect = quota_error
        repo.get_matched_track.return_value = None
        repo.get_failed_track.return_value = None

        with pytest.raises(QuotaExceededError, match="YouTube API quota exceeded"):
            migration_service.migrate_playlist("Test Playlist", "sp_id")

    def test_migrate_retries_failed_tracks(self, migration_service, mock_clients):
        """Test that failed tracks are retried."""
        spotify, youtube, repo = mock_clients

        spotify.get_playlist_tracks.return_value = [
            {"id": "spotify_1", "name": "Song1", "artist": "Artist1"}
        ]

        youtube.find_playlist_by_name.return_value = "PL_test"
        youtube.search_video_candidates.return_value = [
            ("vid1", "Song1 Artist1 Official")
        ]  # Exact substring match

        repo.get_matched_track.return_value = None
        repo.get_failed_track.return_value = None

        # First add fails, retry succeeds
        youtube.add_video_to_playlist.side_effect = [
            Exception("Network error"),  # First attempt fails
            None,  # Retry succeeds
        ]

        migration_service.migrate_playlist("Test Playlist", "sp_id")

        # Should be called twice (initial + retry)
        assert youtube.add_video_to_playlist.call_count == 2

        # Should record and then clear the failure
        repo.record_failed_track.assert_called_once()
        repo.clear_failed_track.assert_called_once()

    def test_migrate_clears_previously_failed_track_on_success(
        self, migration_service, mock_clients
    ):
        """Test that previously failed tracks are cleared on success."""
        spotify, youtube, repo = mock_clients

        spotify.get_playlist_tracks.return_value = [
            {"id": "spotify_1", "name": "Song1", "artist": "Artist1"}
        ]

        youtube.find_playlist_by_name.return_value = "PL_test"
        # No need to mock search_video_candidates since we're using cached track

        # Mock previously failed track
        cached = MagicMock()
        cached.youtube_id = "vid1"
        failed = MagicMock()

        repo.get_matched_track.return_value = cached
        repo.get_failed_track.return_value = failed

        migration_service.migrate_playlist("Test Playlist", "sp_id")

        # Should clear the old failure using real Spotify ID
        repo.clear_failed_track.assert_called_once_with("spotify_1")


class TestIntegrationScenarios:
    """Test complete migration scenarios."""

    def test_full_migration_workflow(self, migration_service, mock_clients):
        """Test a complete successful migration with fuzzy matching."""
        spotify, youtube, repo = mock_clients

        # Setup: 3 tracks with real Spotify IDs
        spotify.get_playlist_tracks.return_value = [
            {"id": "spotify_track_1", "name": "Track1", "artist": "Artist1", "album": "Album1"},
            {"id": "spotify_track_2", "name": "Track2", "artist": "Artist2", "album": "Album2"},
            {"id": "spotify_track_3", "name": "Track3", "artist": "Artist3", "album": "Album3"},
        ]

        # Playlist doesn't exist
        youtube.find_playlist_by_name.return_value = None
        youtube.create_playlist.return_value = "PL_new"

        # Return candidates for fuzzy matching (each track gets matching candidates)
        # Use exact substring matches for TrackMatcher's Stage 1 matching
        youtube.search_video_candidates.side_effect = [
            [("vid1", "Track1 Artist1 Official"), ("other1", "Track1 Cover")],
            [("vid2", "Track2 Artist2 Music Video"), ("other2", "Track2 Remix")],
            [("vid3", "Track3 Artist3 Official Music Video"), ("other3", "Track3 Live")],
        ]

        # No cached tracks
        repo.get_matched_track.return_value = None
        repo.get_failed_track.return_value = None

        result = migration_service.migrate_playlist("New Playlist", "sp_id")

        # Assertions
        assert result["youtube_playlist_id"] == "PL_new"
        assert result["message"] == "Migration complete"

        # All tracks should be searched with candidates
        assert youtube.search_video_candidates.call_count == 3

        # All tracks should be cached (fuzzy matcher picks best match)
        assert repo.save_matched_track.call_count == 3

        # All videos should be added to playlist
        assert youtube.add_video_to_playlist.call_count == 3
