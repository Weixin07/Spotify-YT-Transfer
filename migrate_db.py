"""
Database Migration Script: Add added_to_playlist column

This script safely adds the new 'added_to_playlist' column to existing matched_tracks table
while preserving all existing data.

Usage:
    python migrate_db.py
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
BACKUP_PATH = f"data/matched_tracks_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"


def backup_database():
    """Create a backup of the existing database."""
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found at {DB_PATH}")
        print("   No migration needed - new database will be created on first run.")
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
    """Check if added_to_playlist column already exists."""
    cursor.execute("PRAGMA table_info(matched_tracks)")
    columns = [row[1] for row in cursor.fetchall()]
    return "added_to_playlist" in columns


def migrate_database():
    """Add the added_to_playlist column to matched_tracks table."""
    print(f"\n🔧 Connecting to database: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if migration is needed
        if check_column_exists(cursor):
            print("✅ Column 'added_to_playlist' already exists!")
            print("   No migration needed.")
            return True

        # Get current row count
        cursor.execute("SELECT COUNT(*) FROM matched_tracks")
        row_count = cursor.fetchone()[0]
        print(f"📊 Found {row_count} existing records")

        # Add the new column
        print("\n🔨 Adding 'added_to_playlist' column...")
        cursor.execute("""
            ALTER TABLE matched_tracks
            ADD COLUMN added_to_playlist BOOLEAN DEFAULT 0 NOT NULL
        """)

        conn.commit()
        print("✅ Column added successfully!")

        # Verify the migration
        print("\n🔍 Verifying migration...")
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
        cursor.execute("SELECT spotify_id, song_name, artist, added_to_playlist FROM matched_tracks LIMIT 3")
        samples = cursor.fetchall()

        if samples:
            print("\n📋 Sample records after migration:")
            for spotify_id, song_name, artist, added in samples:
                print(f"  - {song_name} by {artist}: added_to_playlist={bool(added)}")

        return True

    except sqlite3.Error as e:
        print(f"\n❌ Migration failed: {e}")
        print(f"\n💡 Your backup is safe at: {BACKUP_PATH}")
        print("   You can restore it by copying the backup file back to the original location.")
        return False

    finally:
        conn.close()


def main():
    print("=" * 70)
    print("  DATABASE MIGRATION: Add 'added_to_playlist' column")
    print("=" * 70)

    # Step 1: Backup
    if not backup_database():
        print("\n❌ Backup failed. Aborting migration.")
        sys.exit(1)

    # Step 2: Migrate
    if migrate_database():
        print("\n" + "=" * 70)
        print("  ✅ MIGRATION COMPLETED SUCCESSFULLY!")
        print("=" * 70)
        print(f"\n📁 Backup location: {BACKUP_PATH}")
        print(f"📁 Database location: {DB_PATH}")
        print("\n💡 Next steps:")
        print("   1. Run your application normally")
        print("   2. The migration will detect previously added songs on next run")
        print("   3. You can delete the backup file once you verify everything works")
        print("\n⚠️  Note: Existing records have added_to_playlist=False")
        print("   This means they will be checked against the playlist on next migration run")
        print("   to determine if they need to be added.")
    else:
        print("\n" + "=" * 70)
        print("  ❌ MIGRATION FAILED")
        print("=" * 70)
        print(f"\n📁 Your original data is safe in the backup: {BACKUP_PATH}")
        print("\n💡 You can restore the backup with:")
        print(f"   cp {BACKUP_PATH} {DB_PATH}")
        sys.exit(1)


if __name__ == "__main__":
    main()
