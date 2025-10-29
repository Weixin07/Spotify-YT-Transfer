"""
Migration script to convert old cache format to new format.

OLD FORMAT: spotify_id = "Track Name|Artist"
NEW FORMAT: spotify_id = "actual_spotify_track_id"

Usage:
    python migrate_cache_format.py <spotify_playlist_id>

    Or for liked songs:
    python migrate_cache_format.py --liked-songs
"""

import argparse
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from spotify_yt_transfer.clients import SpotifyClient
from spotify_yt_transfer.core.config import settings
from spotify_yt_transfer.database.base import SessionLocal
from spotify_yt_transfer.database.models import MatchedTrack

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def migrate_cache_for_playlist(spotify_playlist_id: str | None = None) -> dict[str, int]:
    """
    Migrate cache entries from old format to new format.

    Args:
        spotify_playlist_id: Spotify playlist ID, or None for liked songs

    Returns:
        Dictionary with migration statistics
    """
    logger.info("Starting cache format migration")

    # Initialize Spotify client
    try:
        spotify_client = SpotifyClient()
    except Exception as e:
        logger.error(f"Failed to initialize Spotify client: {e}")
        logger.error("Make sure you've completed Spotify OAuth authorization")
        return {"error": "spotify_auth_failed", "migrated": 0, "already_new": 0, "not_found": 0}

    # Get tracks from Spotify
    logger.info(f"Fetching tracks from Spotify...")
    if spotify_playlist_id:
        tracks = spotify_client.get_playlist_tracks(spotify_playlist_id)
        logger.info(f"Retrieved {len(tracks)} tracks from playlist {spotify_playlist_id}")
    else:
        tracks = spotify_client.get_liked_tracks()
        logger.info(f"Retrieved {len(tracks)} liked songs")

    if not tracks:
        logger.warning("No tracks found")
        return {"migrated": 0, "already_new": 0, "not_found": 0}

    # Initialize database session
    db = SessionLocal()

    stats = {
        "migrated": 0,
        "already_new": 0,
        "not_found": 0,
        "skipped": 0,
    }

    try:
        for idx, track in enumerate(tracks, start=1):
            spotify_id = track.get("id")
            track_name = track.get("name")
            artist = track.get("artist")
            album = track.get("album")

            if not spotify_id or not track_name or not artist:
                logger.warning(f"Track {idx} missing required fields, skipping")
                stats["skipped"] += 1
                continue

            # Check if new format entry already exists
            existing_new = db.query(MatchedTrack).filter(
                MatchedTrack.spotify_id == spotify_id
            ).first()

            if existing_new:
                logger.debug(f"Track {idx}/{len(tracks)}: '{track_name}' already in new format")
                stats["already_new"] += 1
                continue

            # Look for old format entry
            old_format_id = f"{track_name}|{artist}"
            old_entry = db.query(MatchedTrack).filter(
                MatchedTrack.spotify_id == old_format_id
            ).first()

            if old_entry:
                # Create new entry with correct Spotify ID
                new_entry = MatchedTrack(
                    spotify_id=spotify_id,
                    song_name=track_name,
                    artist=artist,
                    album=album,
                    youtube_id=old_entry.youtube_id,
                )
                db.add(new_entry)

                # Delete old entry
                db.delete(old_entry)

                stats["migrated"] += 1
                logger.info(
                    f"Track {idx}/{len(tracks)}: Migrated '{track_name}' by {artist} "
                    f"({old_format_id} → {spotify_id}) → YouTube: {old_entry.youtube_id}"
                )
            else:
                stats["not_found"] += 1
                logger.debug(
                    f"Track {idx}/{len(tracks)}: No old cache entry found for '{track_name}' by {artist}"
                )

        # Commit all changes
        db.commit()
        logger.info("Migration completed successfully")
        logger.info(f"Statistics: {stats}")

    except Exception as e:
        db.rollback()
        logger.error(f"Migration failed: {e}")
        raise
    finally:
        db.close()

    return stats


def cleanup_old_entries(dry_run: bool = True) -> int:
    """
    Clean up any remaining old format entries.

    Args:
        dry_run: If True, only show what would be deleted without actually deleting

    Returns:
        Number of entries that would be/were deleted
    """
    db = SessionLocal()

    try:
        # Find all old format entries (contain '|' in spotify_id)
        old_entries = db.query(MatchedTrack).filter(
            MatchedTrack.spotify_id.like("%|%")
        ).all()

        count = len(old_entries)

        if dry_run:
            logger.info(f"DRY RUN: Would delete {count} old format entries")
            for entry in old_entries[:10]:  # Show first 10
                logger.info(f"  - {entry.spotify_id} → {entry.youtube_id}")
            if count > 10:
                logger.info(f"  ... and {count - 10} more")
        else:
            for entry in old_entries:
                db.delete(entry)
            db.commit()
            logger.info(f"Deleted {count} old format entries")

        return count

    except Exception as e:
        db.rollback()
        logger.error(f"Cleanup failed: {e}")
        raise
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Migrate cache from old format (name|artist) to new format (spotify_id)"
    )
    parser.add_argument(
        "playlist_id",
        nargs="?",
        help="Spotify playlist ID to migrate cache for",
    )
    parser.add_argument(
        "--liked-songs",
        action="store_true",
        help="Migrate cache for liked songs instead of a playlist",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Clean up remaining old format entries after migration",
    )
    parser.add_argument(
        "--cleanup-dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )

    args = parser.parse_args()

    if args.cleanup_dry_run:
        cleanup_old_entries(dry_run=True)
        return

    if args.cleanup:
        response = input("This will delete all old format entries. Continue? (yes/no): ")
        if response.lower() == "yes":
            count = cleanup_old_entries(dry_run=False)
            logger.info(f"Cleanup complete: {count} entries deleted")
        else:
            logger.info("Cleanup cancelled")
        return

    if args.liked_songs:
        stats = migrate_cache_for_playlist(None)
    elif args.playlist_id:
        stats = migrate_cache_for_playlist(args.playlist_id)
    else:
        parser.print_help()
        logger.error("\nError: Must provide either a playlist ID or --liked-songs flag")
        sys.exit(1)

    # Print summary
    print("\n" + "="*60)
    print("MIGRATION SUMMARY")
    print("="*60)
    print(f"Successfully migrated:  {stats['migrated']}")
    print(f"Already in new format:  {stats['already_new']}")
    print(f"Not found in cache:     {stats['not_found']}")
    print(f"Skipped (invalid):      {stats['skipped']}")
    print("="*60)

    if stats['migrated'] > 0:
        print("\nCache migration successful! Your tracks should now be found.")
        print("\nOptional: Run with --cleanup-dry-run to see old entries that can be cleaned up")
        print("         Run with --cleanup to remove old format entries")


if __name__ == "__main__":
    main()
