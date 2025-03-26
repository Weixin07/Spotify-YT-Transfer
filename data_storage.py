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

    # Updated matched_tracks table to store full metadata.
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS matched_tracks (
            spotify_id TEXT PRIMARY KEY,
            song_name TEXT,
            artist TEXT,
            album TEXT,
            youtube_id TEXT
        )
        """
    )
    logging.info("Table 'matched_tracks' ensured with metadata columns.")

    # Failed tracks table remains unchanged.
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


def get_matched_track(spotify_id: str) -> dict:
    """
    Retrieves the full record mapped to the given Spotify track ID.
    Returns a dict with keys: spotify_id, song_name, artist, album, youtube_id.
    Returns None if no record exists.
    """
    logging.info(f"Retrieving full match record for Spotify ID: {spotify_id}")
    conn = sqlite3.connect(DB_DIRECTORY)
    cur = conn.cursor()
    cur.execute(
        "SELECT spotify_id, song_name, artist, album, youtube_id FROM matched_tracks WHERE spotify_id = ?",
        (spotify_id,),
    )
    row = cur.fetchone()
    conn.close()
    if row:
        logging.info(f"Found matched record: {row}")
        return {
            "spotify_id": row[0],
            "song_name": row[1],
            "artist": row[2],
            "album": row[3],
            "youtube_id": row[4],
        }
    logging.info("No matched record found.")
    return None


def save_matched_track(
    spotify_id: str, song_name: str, artist: str, album: str, youtube_id: str
):
    """
    Saves or updates the mapping of a Spotify track ID to its metadata and YouTube video ID.
    """
    logging.info(
        f"Saving matched track: Spotify ID = {spotify_id}, YouTube ID = {youtube_id}, Song Name = {song_name}, Artist = {artist}, Album = {album}"
    )
    conn = sqlite3.connect(DB_DIRECTORY)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT OR REPLACE INTO matched_tracks (spotify_id, song_name, artist, album, youtube_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (spotify_id, song_name, artist, album, youtube_id),
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
