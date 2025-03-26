import sqlite3
import os
import logging

# Set up logging to print progress messages with a timestamp and level.
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)

DB_DIRECTORY = os.path.join("data", "matched_tracks.db")


def init_db():
    """
    Create the 'matched_tracks' and 'failed_tracks' tables if they do not exist.
    """
    logging.info("Initializing database: Creating tables if they do not exist.")
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
    logging.info("Table 'matched_tracks' ensured.")

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
    logging.info("Table 'failed_tracks' ensured.")

    conn.commit()
    conn.close()
    logging.info("Database initialization complete.")


def get_matched_youtube_id(spotify_id: str) -> str:
    """
    Retrieves the YouTube video ID mapped to the given Spotify track ID.
    Returns None if it doesn't exist in the database.
    """
    logging.info(f"Retrieving matched YouTube ID for Spotify ID: {spotify_id}")
    conn = sqlite3.connect(DB_DIRECTORY)
    cur = conn.cursor()
    cur.execute(
        "SELECT youtube_id FROM matched_tracks WHERE spotify_id = ?", (spotify_id,)
    )
    row = cur.fetchone()
    conn.close()
    if row:
        logging.info(f"Found matched YouTube ID: {row[0]}")
        return row[0]
    logging.info("No matched YouTube ID found.")
    return None


def save_matched_track(spotify_id: str, youtube_id: str):
    """
    Saves or updates the mapping of a Spotify track ID to a YouTube video ID.
    """
    logging.info(
        f"Saving matched track: Spotify ID = {spotify_id}, YouTube ID = {youtube_id}"
    )
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
    logging.info("Matched track saved successfully.")


def record_failed_track(spotify_id: str, youtube_id: str, reason: str):
    """
    Inserts or updates an entry in the 'failed_tracks' table with the reason for failure.
    """
    logging.info(
        f"Recording failed track: Spotify ID = {spotify_id}, YouTube ID = {youtube_id}, Reason = {reason}"
    )
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
    logging.info("Failed track recorded successfully.")


def get_failed_track(spotify_id: str) -> tuple:
    """
    Retrieves a failed record for the given Spotify track ID from the 'failed_tracks' table.
    Returns a tuple (spotify_id, youtube_id, reason) if found, otherwise None.
    """
    logging.info(f"Retrieving failed track record for Spotify ID: {spotify_id}")
    conn = sqlite3.connect(DB_DIRECTORY)
    cur = conn.cursor()
    cur.execute(
        "SELECT spotify_id, youtube_id, reason FROM failed_tracks WHERE spotify_id=?",
        (spotify_id,),
    )
    row = cur.fetchone()
    conn.close()
    if row:
        logging.info(f"Found failed track record: {row}")
    else:
        logging.info("No failed track record found.")
    return row


def get_failed_tracks() -> list:
    """
    Retrieves all entries from the 'failed_tracks' table.
    Returns a list of tuples [(spotify_id, youtube_id, reason), ...].
    """
    logging.info("Retrieving all failed tracks from database.")
    conn = sqlite3.connect(DB_DIRECTORY)
    cur = conn.cursor()
    cur.execute("SELECT spotify_id, youtube_id, reason FROM failed_tracks")
    rows = cur.fetchall()
    conn.close()
    logging.info(f"Retrieved {len(rows)} failed track(s) from database.")
    return rows


def clear_failed_track(spotify_id: str):
    """
    Removes a specific track from 'failed_tracks' if successfully retried.
    """
    logging.info(f"Clearing failed track record for Spotify ID: {spotify_id}")
    conn = sqlite3.connect(DB_DIRECTORY)
    cur = conn.cursor()
    cur.execute("DELETE FROM failed_tracks WHERE spotify_id=?", (spotify_id,))
    conn.commit()
    conn.close()
    logging.info("Failed track record cleared.")
