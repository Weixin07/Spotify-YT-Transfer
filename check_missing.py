import logging
from collections import Counter
from spotify_client import SpotifyClient
from youtube_client import YouTubeClient
from data_storage import get_matched_track
from config import DEBUG

# Use centralized logger.error; get module logger
logger = logging.getLogger(__name__)


def find_missing_tracks(spotify_playlist_id: str, youtube_playlist_id: str) -> dict:
    """
    Compares Spotify playlist tracks with YouTube playlist videos.
    Returns a dictionary with:
      - missing_tracks: tracks whose cached YouTube video is missing in the YouTube playlist.
      - duplicate_tracks: list of unique IDs (and count) that occur more than once.
      - unavailable_tracks: tracks that are missing essential metadata (indicating they may not be available anymore).
    """
    spotify = SpotifyClient()
    yt = YouTubeClient()

    # Retrieve Spotify tracks
    spotify_tracks = spotify.get_playlist_tracks(spotify_playlist_id)
    logger.info(f"Total Spotify tracks retrieved: {len(spotify_tracks)}")

    # Create a list of unique keys and track mapping.
    unique_ids = []
    track_mapping = {}
    unavailable_tracks = []
    for track in spotify_tracks:
        # Use a combination of name and artist as a unique identifier.
        # If essential metadata is missing, consider the track unavailable.
        if not track.get("name") or not track.get("artist"):
            unavailable_tracks.append(track)
            continue
        unique_id = f"{track['name']}|{track['artist']}"
        unique_ids.append(unique_id)
        # For duplicates, we keep the first occurrence.
        if unique_id not in track_mapping:
            track_mapping[unique_id] = track

    # Identify duplicates
    counter = Counter(unique_ids)
    duplicate_tracks = [
        {"unique_id": uid, "count": cnt} for uid, cnt in counter.items() if cnt > 1
    ]

    # Retrieve YouTube playlist video IDs (set for fast lookup)
    youtube_video_ids = set(yt.get_playlist_items(youtube_playlist_id))
    logger.info(f"Total YouTube videos retrieved: {len(youtube_video_ids)}")

    missing_tracks = []
    # Check each Spotify track (by unique_id) to see if its cached match is in the YouTube playlist.
    for unique_id, track in track_mapping.items():
        matched_record = get_matched_track(unique_id)
        if matched_record:
            youtube_id = matched_record["youtube_id"]
            if youtube_id not in youtube_video_ids:
                missing_tracks.append(
                    {
                        "unique_id": unique_id,
                        "track_name": track["name"],
                        "artist": track["artist"],
                        "album": track.get("album", ""),
                        "cached_youtube_id": youtube_id,
                    }
                )
        else:
            # If no match exists, consider it missing.
            missing_tracks.append(
                {
                    "unique_id": unique_id,
                    "track_name": track["name"],
                    "artist": track["artist"],
                    "album": track.get("album", ""),
                    "cached_youtube_id": None,
                }
            )

    return {
        "missing_tracks": missing_tracks,
        "duplicate_tracks": duplicate_tracks,
        "unavailable_tracks": unavailable_tracks,
    }


if __name__ == "__main__":
    # Replace with your actual playlist IDs for testing.
    SPOTIFY_PLAYLIST_ID = "YOUR_SPOTIFY_PLAYLIST_ID"
    YOUTUBE_PLAYLIST_ID = "YOUR_YOUTUBE_PLAYLIST_ID"
    results = find_missing_tracks(SPOTIFY_PLAYLIST_ID, YOUTUBE_PLAYLIST_ID)
    logger.info("Missing Tracks:")
    for track in results["missing_tracks"]:
        logger.info(f"{track}")
    logger.info("Duplicate Tracks:")
    for dup in results["duplicate_tracks"]:
        logger.info(f"{dup}")
    logger.info("Unavailable Tracks:")
    for unavail in results["unavailable_tracks"]:
        logger.info(f"{unavail}")
