from track_matcher import match_track

def test_match_track_success():
    spotify = {"name": "Foo", "artist": "Bar"}
    candidates = [("id1", "Foo Bar"), ("id2", "Other")]
    assert match_track(spotify, candidates) == "id1"

def test_match_track_failure():
    spotify = {"name": "X", "artist": "Y"}
    candidates = [("id1", "A"), ("id2", "B")]
    assert match_track(spotify, candidates) is None
