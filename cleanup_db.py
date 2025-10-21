"""
Database Cleanup Script: Remove added_to_playlist column

This script removes the 'added_to_playlist' column from the matched_tracks table
since we're reverting optimization #5.

Usage:
    python cleanup_db.py
"""

import sqlite3
import os
import sys
from datetime import datetime

# Ensure proper encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DB_PATH = "data/matched_tracks.db"
BACKUP_PATH = f"data/matched_tracks_backup_cleanup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"


def backup_database():
    """Create a backup of the existing database."""
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found at {DB_PATH}")
        print("   No cleanup needed.")
        sys.exit(0)

    print(f"📦 Creating backup at {BACKUP_PATH}...")

    # Create data directory if it doesn't exist
    os.makedirs(os.path.dirname(BACKUP_PATH), exist_ok=True)

    # Copy database file
    import shutil
    shutil.copy2(DB_PATH, BACKUP_PATH)
    print(f"✅ Backup created successfully!")
    return True


def check_column_exists(cursor):
    """Check if added_to_playlist column exists."""
    cursor.execute("PRAGMA table_info(matched_tracks)")
    columns = [row[1] for row in cursor.fetchall()]
    return "added_to_playlist" in columns


def cleanup_database():
    """Remove the added_to_playlist column from matched_tracks table."""
    print(f"\n🔧 Connecting to database: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if cleanup is needed
        if not check_column_exists(cursor):
            print("✅ Column 'added_to_playlist' does not exist!")
            print("   No cleanup needed.")
            return True

        # Get current row count
        cursor.execute("SELECT COUNT(*) FROM matched_tracks")
        row_count = cursor.fetchone()[0]
        print(f"📊 Found {row_count} existing records")

        # SQLite doesn't support DROP COLUMN directly, so we need to recreate the table
        print("\n🔨 Recreating table without 'added_to_playlist' column...")

        # Step 1: Create new table with desired schema
        cursor.execute("""
            CREATE TABLE matched_tracks_new (
                spotify_id TEXT NOT NULL PRIMARY KEY,
                song_name TEXT NOT NULL,
                artist TEXT NOT NULL,
                album TEXT,
                youtube_id TEXT NOT NULL
            )
        """)

        # Step 2: Copy data from old table to new table
        cursor.execute("""
            INSERT INTO matched_tracks_new (spotify_id, song_name, artist, album, youtube_id)
            SELECT spotify_id, song_name, artist, album, youtube_id
            FROM matched_tracks
        """)

        # Step 3: Drop old table
        cursor.execute("DROP TABLE matched_tracks")

        # Step 4: Rename new table to original name
        cursor.execute("ALTER TABLE matched_tracks_new RENAME TO matched_tracks")

        # Step 5: Recreate index
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_matched_tracks_spotify_id ON matched_tracks (spotify_id)")

        conn.commit()
        print("✅ Column removed successfully!")

        # Verify the cleanup
        print("\n🔍 Verifying cleanup...")
        cursor.execute("PRAGMA table_info(matched_tracks)")
        columns = cursor.fetchall()

        print("\nCurrent schema:")
        for col in columns:
            col_id, name, type_, notnull, default, pk = col
            print(f"  - {name}: {type_} (nullable={not notnull}, default={default})")

        # Verify data integrity
        cursor.execute("SELECT COUNT(*) FROM matched_tracks")
        new_row_count = cursor.fetchone()[0]

        if new_row_count == row_count:
            print(f"\n✅ Data integrity verified: {new_row_count} records preserved")
        else:
            print(f"\n⚠️  Warning: Row count changed from {row_count} to {new_row_count}")

        # Show sample data
        cursor.execute("SELECT spotify_id, song_name, artist FROM matched_tracks LIMIT 3")
        samples = cursor.fetchall()

        if samples:
            print("\n📋 Sample records after cleanup:")
            for spotify_id, song_name, artist in samples:
                print(f"  - {song_name} by {artist}")

        return True

    except sqlite3.Error as e:
        print(f"\n❌ Cleanup failed: {e}")
        print(f"\n💡 Your backup is safe at: {BACKUP_PATH}")
        print("   You can restore it by copying the backup file back to the original location.")
        return False

    finally:
        conn.close()


def main():
    print("=" * 70)
    print("  DATABASE CLEANUP: Remove 'added_to_playlist' column")
    print("=" * 70)

    # Step 1: Backup
    if not backup_database():
        print("\n❌ Backup failed. Aborting cleanup.")
        sys.exit(1)

    # Step 2: Cleanup
    if cleanup_database():
        print("\n" + "=" * 70)
        print("  ✅ CLEANUP COMPLETED SUCCESSFULLY!")
        print("=" * 70)
        print(f"\n📁 Backup location: {BACKUP_PATH}")
        print(f"📁 Database location: {DB_PATH}")
        print("\n💡 Next steps:")
        print("   1. Run your application normally")
        print("   2. The app will use the database to cache search results only")
        print("   3. Songs can be added to multiple playlists as needed")
        print("   4. You can delete the backup file once you verify everything works")
    else:
        print("\n" + "=" * 70)
        print("  ❌ CLEANUP FAILED")
        print("=" * 70)
        print(f"\n📁 Your original data is safe in the backup: {BACKUP_PATH}")
        print("\n💡 You can restore the backup with:")
        print(f"   cp {BACKUP_PATH} {DB_PATH}")
        sys.exit(1)


if __name__ == "__main__":
    main()
