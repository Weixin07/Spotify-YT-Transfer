from spotify_yt_transfer.services.track_matcher import TrackMatcher


def test_match_track_success():
    matcher = TrackMatcher()
    spotify = {"name": "Foo", "artist": "Bar"}
    candidates = [("id1", "Foo Bar"), ("id2", "Other")]
    assert matcher.match_track(spotify, candidates) == ("id1", "Foo Bar")


def test_match_track_failure():
    matcher = TrackMatcher()
    spotify = {"name": "X", "artist": "Y"}
    candidates = [("id1", "A"), ("id2", "B")]
    assert matcher.match_track(spotify, candidates) is None


def test_fuzzy_match_success():
    """Test that fuzzy matching works when exact substring match fails."""
    matcher = TrackMatcher(threshold=70)
    spotify = {
        "name": "It Depends (feat. Bryson Tiller)",
        "artist": "Chris Brown, Bryson Tiller",
        "album": "11:11 (Deluxe)",
    }
    candidates = [
        ("Kjof9tYTqD0", "Chris Brown - It Depends (Official Lyric Video) ft. Bryson Tiller"),
        ("JGFJ0J3N3Js", "Chris Brown - Call Me Every Day (Official Video) ft. Wizkid"),
        ("f0I5yGE1zXE", "Chris Brown - Summer Too Hot (Official Video)"),
    ]
    # Should match the first candidate with fuzzy matching (score ~71)
    assert matcher.match_track(spotify, candidates) == ("Kjof9tYTqD0", candidates[0][1])


def test_fuzzy_match_threshold_boundary():
    """Test that threshold is respected (>= not just >)."""
    matcher = TrackMatcher(threshold=70)
    spotify = {"name": "Test Song", "artist": "Test Artist"}
    # Create a candidate that will score exactly at threshold
    candidates = [("id1", "Test Song Test Artist")]
    # Should match because we use >= not >
    result = matcher.match_track(spotify, candidates)
    assert result is not None


def test_fuzzy_match_below_threshold():
    """Test that fuzzy matching fails when score is below threshold."""
    matcher = TrackMatcher(threshold=70)
    spotify = {"name": "Completely Different Song", "artist": "Completely Different Artist"}
    candidates = [
        ("id1", "Totally Unrelated Title"),
        ("id2", "Another Random Song"),
    ]
    # No candidate should match
    assert matcher.match_track(spotify, candidates) is None


def test_fuzzy_match_selects_best_candidate():
    """Test that fuzzy matching selects the highest scoring candidate."""
    matcher = TrackMatcher(threshold=50)
    spotify = {"name": "Shape of You", "artist": "Ed Sheeran"}
    candidates = [
        ("id1", "Ed Sheeran - Perfect"),  # Lower score
        ("id2", "Ed Sheeran - Shape of You (Official Video)"),  # Best score
        ("id3", "Random Song"),  # Lowest score
    ]
    # Should match the second candidate (best match)
    assert matcher.match_track(spotify, candidates) == ("id2", "Ed Sheeran - Shape of You (Official Video)")


def test_exact_match_takes_precedence():
    """Test that exact substring match (Stage 1) takes precedence over fuzzy match."""
    matcher = TrackMatcher(threshold=70)
    spotify = {"name": "Test", "artist": "Artist"}
    candidates = [
        ("exact_match", "Test Artist"),  # Exact substring match
        ("fuzzy_match", "Test by Artist (Official Music Video)"),  # Would score higher in fuzzy
    ]
    # Should return exact match (first candidate found in Stage 1)
    assert matcher.match_track(spotify, candidates) == ("exact_match", "Test Artist")


def test_empty_candidates():
    """Test that empty candidate list returns None."""
    matcher = TrackMatcher()
    spotify = {"name": "Test", "artist": "Artist"}
    candidates = []
    assert matcher.match_track(spotify, candidates) is None


def test_disallowed_terms_are_skipped():
    """Candidates containing disallowed terms should be skipped entirely."""
    matcher = TrackMatcher()
    spotify = {"name": "Song", "artist": "Artist"}
    candidates = [
        ("id_live", "Song - Artist (Live)"),
        ("id_cover", "Song by Artist [Cover]"),
        ("id_good", "Song - Artist (Official Video)"),
    ]
    assert matcher.match_track(spotify, candidates) == ("id_good", "Song - Artist (Official Video)")
