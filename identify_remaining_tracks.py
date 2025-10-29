"""
Script to identify which playlists the remaining old format cache entries belong to.
"""

import logging
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from spotify_yt_transfer.clients import SpotifyClient
from spotify_yt_transfer.database.base import SessionLocal
from spotify_yt_transfer.database.models import MatchedTrack

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def identify_remaining_tracks():
    """Identify which playlists contain the remaining old format tracks."""

    # Get all old format entries
    db = SessionLocal()
    try:
        old_entries = db.query(MatchedTrack).filter(
            MatchedTrack.spotify_id.like("%|%")
        ).all()

        logger.info(f"Found {len(old_entries)} old format entries")

        if not old_entries:
            logger.info("No old format entries remaining!")
            return

        # Create a set of old track signatures for quick lookup
        old_tracks_set = {
            (entry.song_name.lower().strip(), entry.artist.lower().strip())
            for entry in old_entries
        }

        logger.info(f"Created lookup set with {len(old_tracks_set)} unique tracks")

    finally:
        db.close()

    # Initialize Spotify client
    try:
        spotify_client = SpotifyClient()
    except Exception as e:
        logger.error(f"Failed to initialize Spotify client: {e}")
        return

    # Get user's playlists
    logger.info("Fetching user playlists...")
    try:
        # Get user info
        import spotipy
        sp = spotify_client.sp
        user_id = sp.current_user()['id']

        # Get all user playlists
        playlists = []
        offset = 0
        while True:
            response = sp.user_playlists(user_id, limit=50, offset=offset)
            playlists.extend(response['items'])
            if not response['next']:
                break
            offset += 50

        logger.info(f"Found {len(playlists)} playlists")

    except Exception as e:
        logger.error(f"Failed to fetch playlists: {e}")
        return

    # Check each playlist for matches
    playlist_matches = defaultdict(int)

    for idx, playlist in enumerate(playlists, start=1):
        playlist_id = playlist['id']
        playlist_name = playlist['name']

        logger.info(f"Checking playlist {idx}/{len(playlists)}: {playlist_name} ({playlist_id})")

        try:
            tracks = spotify_client.get_playlist_tracks(playlist_id)

            match_count = 0
            for track in tracks:
                track_name = track.get('name', '').lower().strip()
                artist = track.get('artist', '').lower().strip()

                if (track_name, artist) in old_tracks_set:
                    match_count += 1

            if match_count > 0:
                playlist_matches[playlist_id] = {
                    'name': playlist_name,
                    'count': match_count,
                }
                logger.info(f"  -> Found {match_count} old format tracks")

        except Exception as e:
            logger.warning(f"  -> Error checking playlist: {e}")
            continue

    # Print summary
    print("\n" + "="*80)
    print("REMAINING OLD FORMAT TRACKS BY PLAYLIST")
    print("="*80)

    if playlist_matches:
        # Sort by count descending
        sorted_matches = sorted(
            playlist_matches.items(),
            key=lambda x: x[1]['count'],
            reverse=True
        )

        total_matched = sum(info['count'] for _, info in sorted_matches)

        for playlist_id, info in sorted_matches:
            print(f"{info['name']:<50} | {playlist_id} | {info['count']} tracks")

        print("="*80)
        print(f"Total old format tracks found in playlists: {total_matched}")
        print(f"Total old format tracks in database:       {len(old_entries)}")

        if total_matched < len(old_entries):
            print(f"\nUnmatched tracks: {len(old_entries) - total_matched}")
            print("(These may be from deleted playlists or liked songs)")
    else:
        print("No playlists found with old format tracks!")
        print(f"\nAll {len(old_entries)} old format entries may be from:")
        print("  - Deleted playlists")
        print("  - Liked songs (try: python migrate_cache_format.py --liked-songs)")
        print("  - Private/collaborative playlists not owned by you")

    print("="*80)


if __name__ == "__main__":
    identify_remaining_tracks()
