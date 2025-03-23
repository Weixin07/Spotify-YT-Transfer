import sqlite3
import os

DB_DIRECTORY = os.path.join("data", "matched_tracks.db")


def init_db():
    """
    Create the 'matched_tracks' and 'failed_tracks' tables if they do not exist.
    """
    conn = sqlite3.connect(DB_DIRECTORY)
    cur = conn.cursor()

    # Existing matched_tracks table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS matched_tracks (
            spotify_id TEXT PRIMARY KEY,
            youtube_id TEXT
        )
        """
    )

    # New failed_tracks table
    # Stores Spotify ID, corresponding YouTube ID, and a reason for failure
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS failed_tracks (
            spotify_id TEXT PRIMARY KEY,
            youtube_id TEXT,
            reason TEXT
        )
        """
    )

    conn.commit()
    conn.close()


def get_matched_youtube_id(spotify_id: str) -> str:
    """
    Retrieves the YouTube video ID mapped to the given Spotify track ID.
    Returns None if it doesn't exist in the database.
    """
    conn = sqlite3.connect(DB_DIRECTORY)
    cur = conn.cursor()
    cur.execute(
        "SELECT youtube_id FROM matched_tracks WHERE spotify_id = ?", (spotify_id,)
    )
    row = cur.fetchone()
    conn.close()
    if row:
        return row[0]
    return None


def save_matched_track(spotify_id: str, youtube_id: str):
    """
    Saves or updates the mapping of a Spotify track ID to a YouTube video ID.
    """
    conn = sqlite3.connect(DB_DIRECTORY)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT OR REPLACE INTO matched_tracks (spotify_id, youtube_id)
        VALUES (?, ?)
        """,
        (spotify_id, youtube_id),
    )
    conn.commit()
    conn.close()


def record_failed_track(spotify_id: str, youtube_id: str, reason: str):
    """
    Inserts or updates an entry in the 'failed_tracks' table with the reason for failure.
    """
    conn = sqlite3.connect(DB_DIRECTORY)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT OR REPLACE INTO failed_tracks (spotify_id, youtube_id, reason)
        VALUES (?, ?, ?)
        """,
        (spotify_id, youtube_id, reason),
    )
    conn.commit()
    conn.close()


def get_failed_tracks() -> list:
    """
    Retrieves all entries from the 'failed_tracks' table.
    Returns a list of tuples [(spotify_id, youtube_id, reason), ...].
    """
    conn = sqlite3.connect(DB_DIRECTORY)
    cur = conn.cursor()
    cur.execute("SELECT spotify_id, youtube_id, reason FROM failed_tracks")
    rows = cur.fetchall()
    conn.close()
    return rows


def clear_failed_track(spotify_id: str):
    """
    Removes a specific track from 'failed_tracks' if successfully retried.
    """
    conn = sqlite3.connect(DB_DIRECTORY)
    cur = conn.cursor()
    cur.execute("DELETE FROM failed_tracks WHERE spotify_id=?", (spotify_id,))
    conn.commit()
    conn.close()
