from spotify_yt_transfer.database import get_db, init_db
from spotify_yt_transfer.database.repository import TrackRepository


def test_save_and_get_matched_track():
    init_db()
    db = next(get_db())
    repo = TrackRepository(db)

    # Save a matched track
    repo.save_matched_track("sid1", "Song", "Artist", "yt1", "Album", "Title")

    # Retrieve it
    rec = repo.get_matched_track("sid1")
    assert rec is not None
    assert rec.youtube_id == "yt1"
    assert rec.song_name == "Song"
    assert rec.artist == "Artist"
    assert rec.youtube_title == "Title"


def test_record_and_clear_failed_track():
    init_db()
    db = next(get_db())
    repo = TrackRepository(db)

    # Record a failed track
    repo.record_failed_track("sid2", "yt2", "reason")

    # Retrieve it
    rec = repo.get_failed_track("sid2")
    assert rec is not None
    assert rec.spotify_id == "sid2"
    assert rec.youtube_id == "yt2"
    assert rec.reason == "reason"

    # Clear it
    repo.clear_failed_track("sid2")
    assert repo.get_failed_track("sid2") is None
