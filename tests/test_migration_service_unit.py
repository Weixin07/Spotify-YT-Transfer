"""Unit tests for MigrationService covering caching, failure handling, and retries."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from spotify_yt_transfer.services.migration_service import MigrationService


@pytest.fixture
def spotify_client():
    return MagicMock()


@pytest.fixture
def youtube_client():
    client = MagicMock()
    client.find_playlist_by_name.return_value = "YT_EXISTING"
    return client


@pytest.fixture
def repository():
    return MagicMock()


@pytest.fixture
def matcher():
    mock_matcher = MagicMock()
    mock_matcher.threshold = 80
    mock_matcher.match_track.return_value = ("yt_video_from_matcher", "Title from matcher")
    return mock_matcher


def test_migrate_playlist_uses_cached_match_and_clears_failures(
    spotify_client, youtube_client, repository, matcher
):
    """Verify that cached matches bypass YouTube search and clear previous failures."""
    spotify_client.get_playlist_tracks.return_value = [
        {"id": "spotify_1", "name": "Song1", "artist": "Artist1", "album": "Album1"},
        {"id": None, "name": "Missing", "artist": "Artist2"},  # Should be skipped early
    ]
    repository.get_matched_track.return_value = SimpleNamespace(youtube_id="cached_vid")
    repository.get_failed_track.return_value = SimpleNamespace()

    service = MigrationService(spotify_client, youtube_client, repository, track_matcher=matcher)

    result = service.migrate_playlist("Existing Playlist", "spotify_playlist")

    assert result == {"message": "Migration complete", "youtube_playlist_id": "YT_EXISTING"}
    youtube_client.search_video_candidates.assert_not_called()
    youtube_client.add_video_to_playlist.assert_called_once_with("YT_EXISTING", "cached_vid")
    repository.clear_failed_track.assert_called_once_with("spotify_1")
    repository.record_failed_track.assert_not_called()


def test_migrate_playlist_records_failures_and_retries_successfully(
    spotify_client, youtube_client, repository, matcher
):
    """Ensure migration records initial failures and succeeds on retry."""
    youtube_client.find_playlist_by_name.return_value = None
    youtube_client.create_playlist.return_value = "YT_CREATED"

    spotify_client.get_playlist_tracks.return_value = [
        {"id": "spotify_1", "name": "Song1", "artist": "Artist1", "album": "Album1"}
    ]

    repository.get_matched_track.return_value = None
    repository.get_failed_track.return_value = None
    youtube_client.search_video_candidates.return_value = [("yt_candidate", "Song1 - Artist1")]
    matcher.match_track.return_value = ("yt_candidate", "Song1 - Artist1")

    youtube_client.add_video_to_playlist.side_effect = [Exception("first attempt"), None]

    service = MigrationService(spotify_client, youtube_client, repository, track_matcher=matcher)

    result = service.migrate_playlist("New Playlist", "spotify_playlist")

    assert result == {"message": "Migration complete", "youtube_playlist_id": "YT_CREATED"}
    youtube_client.create_playlist.assert_called_once_with(
        title="New Playlist", description="Migrated from Spotify"
    )
    assert youtube_client.add_video_to_playlist.call_count == 2
    repository.save_matched_track.assert_called_once_with(
        spotify_id="spotify_1",
        song_name="Song1",
        artist="Artist1",
        youtube_id="yt_candidate",
        album="Album1",
        youtube_title="Song1 - Artist1",
    )
    repository.record_failed_track.assert_called_once_with(
        "spotify_1", "yt_candidate", "unknown_error"
    )
    repository.clear_failed_track.assert_called_once_with("spotify_1")
