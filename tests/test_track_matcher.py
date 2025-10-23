from spotify_yt_transfer.services.track_matcher import TrackMatcher


def test_match_track_success():
    matcher = TrackMatcher()
    spotify = {"name": "Foo", "artist": "Bar"}
    candidates = [("id1", "Foo Bar"), ("id2", "Other")]
    assert matcher.match_track(spotify, candidates) == "id1"


def test_match_track_failure():
    matcher = TrackMatcher()
    spotify = {"name": "X", "artist": "Y"}
    candidates = [("id1", "A"), ("id2", "B")]
    assert matcher.match_track(spotify, candidates) is None
