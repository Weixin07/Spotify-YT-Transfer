import sqlite3
import os

DB_DIRECTORY = os.path.join("data", "matched_tracks.db")


def init_db():
    """
    Create the 'matched_tracks' table if it does not exist.
    This table maps Spotify track IDs to YouTube video IDs.
    """
    conn = sqlite3.connect(DB_DIRECTORY)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS matched_tracks (
            spotify_id TEXT PRIMARY KEY,
            youtube_id TEXT
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
