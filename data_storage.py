import os
import logging
from config import SessionLocal, engine, Base
from models import MatchedTrack, FailedTrack

# Use centralized logger.error; get module logger
logger = logging.getLogger(__name__)

def init_db():
    """
    Create the 'matched_tracks' and 'failed_tracks' tables if they do not exist.
    """
    logger.info("Initializing database via ORM models.")
    # creates both matched_tracks & failed_tracks tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables ensured via SQLAlchemy.")


def get_matched_track(spotify_id: str) -> dict:
    """
    Retrieves the full record mapped to the given Spotify track ID.
    Returns a dict with keys: spotify_id, song_name, artist, album, youtube_id.
    Returns None if no record exists.
    """
    logger.info(f"Retrieving full match record for Spotify ID: {spotify_id}")
    with SessionLocal() as session:
        obj = session.get(MatchedTrack, spotify_id)
    if obj:
        logger.info(f"Found matched record: {obj}")
        return {
            "spotify_id": obj.spotify_id,
            "song_name": obj.song_name,
            "artist": obj.artist,
            "album": obj.album,
            "youtube_id": obj.youtube_id,
        }

    logger.info("No matched record found.")
    return None


def save_matched_track(
    spotify_id: str, song_name: str, artist: str, album: str, youtube_id: str
):
    """
    Saves or updates the mapping of a Spotify track ID to its metadata and YouTube video ID.
    """
    logger.info(
        f"Saving matched track: Spotify ID = {spotify_id}, YouTube ID = {youtube_id}, Song Name = {song_name}, Artist = {artist}, Album = {album}"
    )
    with SessionLocal() as session:
        obj = MatchedTrack(
            spotify_id=spotify_id,
            song_name=song_name,
            artist=artist,
            album=album,
            youtube_id=youtube_id,
        )
        session.merge(obj)
        session.commit()

    logger.info("Matched track saved successfully.")


def record_failed_track(spotify_id: str, youtube_id: str, reason: str):
    """
    Inserts or updates an entry in the 'failed_tracks' table with the reason for failure.
    """
    logger.info(
        f"Recording failed track: Spotify ID = {spotify_id}, YouTube ID = {youtube_id}, Reason = {reason}"
    )
    with SessionLocal() as session:
        obj = FailedTrack(
            spotify_id=spotify_id,
            youtube_id=youtube_id,
            reason=reason,
        )
        session.merge(obj)
        session.commit()

    logger.info("Failed track recorded successfully.")


def get_failed_track(spotify_id: str) -> tuple:
    """
    Retrieves a failed record for the given Spotify track ID from the 'failed_tracks' table.
    Returns a tuple (spotify_id, youtube_id, reason) if found, otherwise None.
    """
    logger.info(f"Retrieving failed track record for Spotify ID: {spotify_id}")
    with SessionLocal() as session:
        obj = session.get(FailedTrack, spotify_id)
    if obj:
        return (obj.spotify_id, obj.youtube_id, obj.reason)
    return obj


def get_failed_tracks() -> list:
    """
    Retrieves all entries from the 'failed_tracks' table.
    Returns a list of tuples [(spotify_id, youtube_id, reason), ...].
    """
    logger.info("Retrieving all failed tracks from database.")
    with SessionLocal() as session:
        rows = session.query(FailedTrack).all()
    # convert ORM objects to tuples
    logger.info(f"Retrieved {len(rows)} failed track(s) from database.")
    return [(f.spotify_id, f.youtube_id, f.reason) for f in rows]


def clear_failed_track(spotify_id: str):
    """
    Removes a specific track from 'failed_tracks' if successfully retried.
    """
    logger.info(f"Clearing failed track record for Spotify ID: {spotify_id}")
    with SessionLocal() as session:
        obj = session.get(FailedTrack, spotify_id)
        if obj:
            session.delete(obj)
            session.commit()
            logger.info("Failed track record cleared.")


def get_all_matched_tracks() -> list:
    """
    Retrieves all matched tracks from the database.
    Returns a list of dicts with keys: spotify_id, song_name, artist, album, youtube_id.
    """
    logger.info("Retrieving all matched tracks from database.")
    with SessionLocal() as session:
        tracks = session.query(MatchedTrack).all()
    result = [
        {
            "spotify_id": t.spotify_id,
            "song_name": t.song_name,
            "artist": t.artist,
            "album": t.album,
            "youtube_id": t.youtube_id,
        }
        for t in tracks
    ]
    logger.info(f"Retrieved {len(result)} matched tracks from database.")
    return result
