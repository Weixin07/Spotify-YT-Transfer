from rapidfuzz import fuzz, process


def match_track(spotify_track: dict, youtube_candidates: list) -> str:
    """
    Given a Spotify track and a list of YouTube candidate titles, return the best matching YouTube video ID.
    :param spotify_track: Dictionary containing track details (name, artist, album).
    :param youtube_candidates: List of tuples [(video_id, video_title), ...].
    :return: The video_id of the best match, or None if no good match is found.
    """
    query = f"{spotify_track['name']} {spotify_track['artist']}"
    best_match = process.extractOne(
        query,
        {vid: title for vid, title in youtube_candidates}.items(),
        scorer=fuzz.token_sort_ratio,
    )
    if best_match and best_match[1] > 70:  # Threshold can be adjusted based on testing
        return best_match[0][0]
    return None
