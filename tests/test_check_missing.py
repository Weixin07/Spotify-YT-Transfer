from check_missing import find_missing_tracks

def test_find_missing_tracks(monkeypatch):
    # stub clients & storage
    class SP:
        def get_playlist_tracks(self, _): 
            return [
                {"name": "A", "artist": "X", "album": "Z"},
                {"name": None, "artist": None},
                {"name": "A", "artist": "X", "album": "Z"},
            ]
    class YT:
        def get_playlist_items(self, _): return ["yt1"]
    monkeypatch.setattr("check_missing.SpotifyClient", lambda: SP())
    monkeypatch.setattr("check_missing.YouTubeClient", lambda: YT())
    monkeypatch.setattr("check_missing.get_matched_track", lambda uid: {"youtube_id":"yt1"} if uid=="A|X" else None)
    res = find_missing_tracks("s", "y")
    assert isinstance(res, dict)
    assert "missing_tracks" in res
    assert "duplicate_tracks" in res
    assert "unavailable_tracks" in res
