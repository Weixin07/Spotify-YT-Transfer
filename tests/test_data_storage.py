import pytest


def test_save_and_get_matched_track():
    # import inside test so we get the module reloaded by conftest
    import data_storage

    data_storage.init_db()
    data_storage.save_matched_track("sid1", "Song", "Artist", "Album", "yt1")
    rec = data_storage.get_matched_track("sid1")
    assert rec["youtube_id"] == "yt1"


def test_record_and_clear_failed_track():
    import data_storage

    data_storage.init_db()
    data_storage.record_failed_track("sid2", "yt2", "reason")
    rec = data_storage.get_failed_track("sid2")
    assert rec == ("sid2", "yt2", "reason")
    data_storage.clear_failed_track("sid2")
    assert data_storage.get_failed_track("sid2") is None
