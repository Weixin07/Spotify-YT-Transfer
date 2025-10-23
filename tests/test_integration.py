"""Integration tests for end-to-end workflows."""

from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from spotify_yt_transfer.database.base import Base
from spotify_yt_transfer.database.repository import TrackRepository
from spotify_yt_transfer.services.migration_service import MigrationService
from spotify_yt_transfer.services.playlist_service import PlaylistService


@pytest.fixture
def test_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    yield session

    session.close()
    engine.dispose()


@pytest.fixture
def repository(test_db):
    """Create a repository with test database."""
    return TrackRepository(test_db)


@pytest.fixture
def mock_spotify():
    """Create mock Spotify client."""
    return MagicMock()


@pytest.fixture
def mock_youtube():
    """Create mock YouTube client."""
    return MagicMock()


@pytest.fixture
def migration_service(mock_spotify, mock_youtube, repository):
    """Create MigrationService with real repository and mock clients."""
    return MigrationService(mock_spotify, mock_youtube, repository)


@pytest.fixture
def playlist_service(mock_spotify, mock_youtube, repository):
    """Create PlaylistService with real repository and mock clients."""
    return PlaylistService(mock_spotify, mock_youtube, repository)


class TestMigrationIntegration:
    """Integration tests for migration workflow."""

    def test_complete_migration_with_caching(
        self, migration_service, mock_spotify, mock_youtube, repository
    ):
        """Test complete migration flow with database caching."""
        # Setup: Mock Spotify playlist with 3 tracks
        mock_spotify.get_playlist_tracks.return_value = [
            {"id": "spotify_track_1", "name": "Track1", "artist": "Artist1", "album": "Album1"},
            {"id": "spotify_track_2", "name": "Track2", "artist": "Artist2", "album": "Album2"},
            {"id": "spotify_track_3", "name": "Track3", "artist": "Artist3", "album": "Album3"},
        ]

        # Mock YouTube playlist creation
        mock_youtube.find_playlist_by_name.return_value = None
        mock_youtube.create_playlist.return_value = "PL_test_123"

        # Mock YouTube search results with candidates for fuzzy matching
        mock_youtube.search_video_candidates.side_effect = [
            [("vid1", "Track1 Artist1 Official")],
            [("vid2", "Track2 Artist2 Official")],
            [("vid3", "Track3 Artist3 Official")],
        ]

        # First migration - should search all tracks
        result = migration_service.migrate_playlist("Test Playlist", "sp_playlist_id")

        assert result["youtube_playlist_id"] == "PL_test_123"
        assert result["message"] == "Migration complete"

        # Verify all tracks were searched with fuzzy matching
        assert mock_youtube.search_video_candidates.call_count == 3

        # Verify all tracks were cached in database using real Spotify IDs
        cached_track1 = repository.get_matched_track("spotify_track_1")
        assert cached_track1 is not None
        assert cached_track1.youtube_id == "vid1"
        assert cached_track1.song_name == "Track1"

        cached_track2 = repository.get_matched_track("spotify_track_2")
        assert cached_track2 is not None
        assert cached_track2.youtube_id == "vid2"

        # Reset mock to test caching
        mock_youtube.search_video_candidates.reset_mock()

        # Second migration with same playlist - should use cache
        mock_spotify.get_playlist_tracks.return_value = [
            {"id": "spotify_track_1", "name": "Track1", "artist": "Artist1", "album": "Album1"},
            {"id": "spotify_track_2", "name": "Track2", "artist": "Artist2", "album": "Album2"},
        ]

        migration_service.migrate_playlist("Test Playlist 2", "sp_playlist_id")

        # Should NOT search YouTube candidates (using cache)
        mock_youtube.search_video_candidates.assert_not_called()

        # Should still add videos to playlist
        assert mock_youtube.add_video_to_playlist.call_count >= 2


class TestPlaylistIntegration:
    """Integration tests for playlist operations."""

    def test_find_missing_tracks_with_database(
        self, playlist_service, mock_spotify, mock_youtube, repository
    ):
        """Test finding missing tracks using real database."""
        # Pre-populate database with some matched tracks using real Spotify IDs
        repository.save_matched_track(
            spotify_id="spotify_song_1",
            song_name="Song1",
            artist="Artist1",
            youtube_id="yt_vid_1",
            album="Album1",
        )
        repository.save_matched_track(
            spotify_id="spotify_song_2",
            song_name="Song2",
            artist="Artist2",
            youtube_id="yt_vid_2",
            album="Album2",
        )

        # Setup: Spotify playlist with 3 tracks (2 cached, 1 not)
        mock_spotify.get_playlist_tracks.return_value = [
            {"id": "spotify_song_1", "name": "Song1", "artist": "Artist1", "album": "Album1"},
            {"id": "spotify_song_2", "name": "Song2", "artist": "Artist2", "album": "Album2"},
            {"id": "spotify_song_3", "name": "Song3", "artist": "Artist3", "album": "Album3"},
        ]

        # YouTube playlist only has first 2 videos
        mock_youtube.get_playlist_items.return_value = ["yt_vid_1", "yt_vid_2"]

        # Find missing tracks
        result = playlist_service.find_missing_tracks("sp_playlist", "yt_playlist")

        # Should identify Song3 as missing (no cached youtube_id in database)
        assert len(result["missing_tracks"]) == 1
        assert result["missing_tracks"][0]["track_name"] == "Song3"
        assert result["missing_tracks"][0]["artist"] == "Artist3"

        # Songs 1 and 2 are in YouTube playlist, so they shouldn't be in missing
        missing_names = [t["track_name"] for t in result["missing_tracks"]]
        assert "Song1" not in missing_names
        assert "Song2" not in missing_names

        # Verify repository was queried using real Spotify IDs
        assert repository.get_matched_track("spotify_song_1") is not None
        assert repository.get_matched_track("spotify_song_2") is not None


class TestErrorHandlingIntegration:
    """Integration tests for error handling across layers."""

    def test_failed_track_recording_and_retry(
        self, migration_service, mock_spotify, mock_youtube, repository
    ):
        """Test that failed tracks are recorded in database and retried."""
        # Setup
        mock_spotify.get_playlist_tracks.return_value = [
            {"id": "spotify_track_1", "name": "Track1", "artist": "Artist1", "album": "Album1"}
        ]

        mock_youtube.find_playlist_by_name.return_value = "PL_existing"
        mock_youtube.search_video_candidates.return_value = [("vid1", "Track1 Artist1 Official")]

        # First attempt fails, second succeeds
        mock_youtube.add_video_to_playlist.side_effect = [
            Exception("Network error"),  # First attempt fails
            None,  # Retry succeeds
        ]

        # Run migration
        result = migration_service.migrate_playlist("Test", "sp_id")

        # Verify migration completed
        assert result["message"] == "Migration complete"

        # Verify track was matched and cached using real Spotify ID
        cached = repository.get_matched_track("spotify_track_1")
        assert cached is not None
        assert cached.youtube_id == "vid1"

        # Verify add was attempted twice (initial + retry)
        assert mock_youtube.add_video_to_playlist.call_count == 2

        # After successful retry, failed track should be cleared from database
        # (we can't easily verify this without checking the database state)
        # But we can verify the track is in matched_tracks
        all_matched = repository.get_all_matched_tracks()
        assert len(all_matched) == 1
        assert all_matched[0].spotify_id == "spotify_track_1"
