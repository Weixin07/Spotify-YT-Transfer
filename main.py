import time, json, logging
from contextlib import asynccontextmanager

from logging.config import dictConfig
from logging.handlers import RotatingFileHandler

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.concurrency import run_in_threadpool

from googleapiclient.errors import HttpError
from spotipy.oauth2 import SpotifyOAuth

from config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI
from spotify_client import SpotifyClient
from youtube_client import YouTubeClient
from data_storage import (
    init_db,
    get_matched_track,
    save_matched_track,
    get_failed_track,
    record_failed_track,
    clear_failed_track,
)
from track_matcher import match_track
from check_missing import find_missing_tracks
from download_cover import download_playlist_cover
from schemas import (
    MigrateParams,
    MigrateResponse,
    CheckMissingParams,
    CheckMissingResponse,
    YouTubePlaylistParams,
    YouTubePlaylistResponse,
)

# centralized logging config
dictConfig(
    {
        "version": 1,
        "formatters": {
            "default": {"format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"}
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "level": "INFO",
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "default",
                "filename": "migration.log",
                "maxBytes": 10 * 1024 * 1024,
                "backupCount": 5,
                "level": "INFO",
            },
        },
        "root": {"level": "INFO", "handlers": ["console", "file"]},
        "loggers": {
            # suppress overly‐verbose libs
            "googleapiclient": {"level": "WARNING"},
        },
    }
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up: Initializing database.")
    init_db()
    # instantiate singletons once
    app.state.spotify = SpotifyClient()
    app.state.youtube = YouTubeClient()
    yield
    logger.info("Shutting down: Cleanup if needed.")


app = FastAPI(title="Spotify to YouTube Music Playlist Migrator", lifespan=lifespan)


def get_spotify_client() -> SpotifyClient:
    """Retrieve the singleton SpotifyClient from app state"""
    return app.state.spotify


def get_youtube_client() -> YouTubeClient:
    """Retrieve the singleton YouTubeClient from app state"""
    return app.state.youtube


@app.get("/")
def read_root():
    logger.info("Received request at root endpoint.")
    return {"message": "Welcome to the Playlist Migrator API"}


@app.get("/spotify/callback")
async def spotify_callback(request: Request):
    code = request.query_params.get("code")
    if not code:
        logger.error("Spotify callback: Missing 'code' parameter.")
        raise HTTPException(
            status_code=400, detail="Missing code parameter in callback."
        )
    try:
        logger.info("Processing Spotify callback with code received.")
        spotify_auth_manager = SpotifyOAuth(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET,
            redirect_uri=SPOTIFY_REDIRECT_URI,
            scope="playlist-read-private",
        )
        token_info = await run_in_threadpool(
            spotify_auth_manager.get_access_token, code
        )
        logger.info("Spotify authentication successful.")
    except Exception as e:
        logger.error(f"Spotify authentication failed: {e}")
        raise HTTPException(status_code=400, detail=f"Authentication failed: {str(e)}")
    return {"message": "Spotify authentication successful", "token_info": token_info}


def is_quota_exceeded(e: HttpError) -> bool:
    try:
        status = e.resp.status
        try:
            body = e.content.decode()
            js = json.loads(body)
            reason = js.get("error", {}).get("errors", [{}])[0].get("reason", "")
        except Exception:
            return False
        return status == 403 and reason == "quotaExceeded"
    except Exception:
        return False


@app.get("/migrate", response_model=MigrateResponse)
async def migrate_playlist(
    params: MigrateParams = Depends(),
    spotify: SpotifyClient = Depends(get_spotify_client),
    yt: YouTubeClient = Depends(get_youtube_client),
):
    spotify_playlist_id = params.spotify_playlist_id
    youtube_playlist_title = params.youtube_playlist_title

    quota_exceeded = False

    # 1. Get tracks from Spotify
    try:
        tracks = await run_in_threadpool(
            spotify.get_playlist_tracks, spotify_playlist_id
        )
        logger.info(
            f"Retrieved {len(tracks)} tracks from Spotify playlist {spotify_playlist_id}."
        )
    except Exception as e:
        logger.error(f"Error retrieving Spotify playlist: {e}")
        raise HTTPException(
            status_code=400, detail=f"Error retrieving Spotify playlist: {str(e)}"
        )

    # 2. Check if a playlist with this name already exists
    existing_playlist_id = await run_in_threadpool(
        yt.find_playlist_by_name, youtube_playlist_title
    )
    if existing_playlist_id:
        yt_playlist_id = existing_playlist_id
        logger.info(
            f"Using existing YouTube playlist '{youtube_playlist_title}' with ID {existing_playlist_id}."
        )
        # Fetch existing videos in this playlist
        try:
            existing_videos = set(
                await run_in_threadpool(yt.get_playlist_items, yt_playlist_id)
            )
            logger.info(f"Found {len(existing_videos)} existing videos in playlist.")

        except HttpError as e:
            if is_quota_exceeded(e):
                logger.error("Max quota reached. Stopping migration now.")
                raise HTTPException(
                    status_code=429,
                    detail="YouTube API quota exceeded—migration aborted.",
                )
            else:
                raise  # re-raise any other HttpError
    else:
        try:
            yt_playlist_id = await run_in_threadpool(
                yt.create_playlist,
                title=youtube_playlist_title,
                description="Migrated from Spotify",
            )
            existing_videos = set()
            logger.info(
                f"Created new YouTube playlist '{youtube_playlist_title}' with ID {yt_playlist_id}."
            )
        except Exception as e:
            logger.error(f"Error creating YouTube playlist: {e}")
            raise HTTPException(
                status_code=400, detail=f"Error creating YouTube playlist: {str(e)}"
            )

    # 3. Iterate over each Spotify track and add to YT if not already in playlist
    failed_attempts = []  # keep track of songs that fail after all retries

    for idx, track in enumerate(tracks, start=1):
        logger.info(
            f"Processing track {idx}/{len(tracks)}: {track['name']} by {track['artist']}."
        )
        query = f"{track['name']} {track['artist']}"
        spotify_unique_id = f"{track['name']}|{track['artist']}"

        # Wrap DB lookup
        matched_record = await run_in_threadpool(get_matched_track, spotify_unique_id)
        failed_record = await run_in_threadpool(get_failed_track, spotify_unique_id)

        # If a match exists, reuse its youtube_id; otherwise, perform a new search.
        if matched_record:
            video_id = matched_record["youtube_id"]
            logger.info(f"Using cached match for track '{track['name']}': {video_id}.")
        else:
            try:
                video_id = await run_in_threadpool(yt.search_video, query)
                if video_id:
                    await run_in_threadpool(
                        save_matched_track,
                        spotify_unique_id,
                        track["name"],
                        track["artist"],
                        track.get("album", ""),
                        video_id,
                    )
                    logger.info(
                        f"Cached new match for track '{track['name']}': {video_id}."
                    )
                else:
                    logger.warning(
                        f"No matching video found for track: '{track['name']}' by {track['artist']}."
                    )
                    continue
            except HttpError as e:
                logger.error(f"Error searching for track '{track['name']}': {e}")
                continue

        # Skip if already in playlist
        if video_id in existing_videos and not failed_record:
            logger.info(
                f"Skipping track '{track['name']}' (video_id={video_id}) - already in playlist."
            )
            continue

        # Attempt to add the video with retries
        if video_id:
            try:
                await run_in_threadpool(
                    yt.add_video_to_playlist,
                    playlist_id=yt_playlist_id,
                    video_id=video_id,
                )
                logger.info(f"Added {video_id} for {track['name']}")
            except HttpError as e:
                if is_quota_exceeded(e):
                    logger.error("Max quota reached. Stopping migration now.")
                    raise HTTPException(
                        status_code=429,
                        detail=(
                            f"YouTube API quota exceeded at track {idx}/{len(tracks)} "
                            f"('{track['name']}')—migration aborted."
                        ),
                    )
                logger.error(f"Failed to add video {video_id} after retries: {e}")
                failed_attempts.append((spotify_unique_id, video_id, "add_failed"))
            except Exception as ex:
                logger.exception(
                    f"Unexpected error adding {video_id}, aborting this track"
                )

    # 4. Record and retry failures
    for spotify_id, yid, reason in failed_attempts:
        await run_in_threadpool(record_failed_track, spotify_id, yid, reason)
        logger.info(
            f"Recorded failed track {spotify_id} with video {yid} (Reason: {reason})."
        )
    logger.info("Starting second pass for failed tracks.")

    for spotify_id, yid, _ in failed_attempts:
        logger.info(f"Retrying failed track: {spotify_id} => {yid}")

        try:
            await run_in_threadpool(
                yt.add_video_to_playlist, playlist_id=yt_playlist_id, video_id=yid
            )
            logger.info(
                f"Second-pass success: Added video {yid} for track {spotify_id}."
            )
            await run_in_threadpool(clear_failed_track, spotify_id)
        except HttpError as e:
            logger.error(f"Second-pass attempt failed for video {yid}: {e}")
        except Exception as ex:
            logger.error(f"Unexpected error in second-pass for video {yid}: {ex}")

    logger.info(f"Migration complete. YouTube playlist ID: {yt_playlist_id}")
    return {"message": "Migration complete", "youtube_playlist_id": yt_playlist_id}


@app.get("/check_missing", response_model=CheckMissingResponse)
async def check_missing(params: CheckMissingParams = Depends()):
    """
    Endpoint to compare a Spotify playlist with a YouTube playlist.
    Returns a list of missing tracks with their details.
    """
    spotify_playlist_id = params.spotify_playlist_id
    youtube_playlist_id = params.youtube_playlist_id
    return await run_in_threadpool(
        find_missing_tracks, spotify_playlist_id, youtube_playlist_id
    )


# Get YouTube Playlist ID by Playlist Name
@app.get("/youtube/playlist", response_model=YouTubePlaylistResponse)
async def get_youtube_playlist_id(
    params: YouTubePlaylistParams = Depends(),
    yt: YouTubeClient = Depends(get_youtube_client),
):
    """
    Retrieves the YouTube playlist ID for a given playlist name from the user's account.
    If found, returns the playlist ID; otherwise, returns a not found message.
    """
    playlist_name = params.playlist_name
    playlist_id = await run_in_threadpool(yt.find_playlist_by_name, playlist_name)
    if playlist_id:
        return {"playlist_name": playlist_name, "playlist_id": playlist_id}
    else:
        raise HTTPException(
            status_code=404,
            detail=f"Playlist '{playlist_name}' not found."
        )


# Download Spotify Playlist Cover
@app.get("/download_cover")
async def download_cover_endpoint(playlist_id: str, filename: str = "cover.jpg"):
    """
    Endpoint to download the Spotify playlist cover image.
    Downloads the image using download_cover.py and returns it as a downloadable file.
    """
    try:
        await run_in_threadpool(download_playlist_cover, playlist_id, filename)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error downloading cover image: {str(e)}"
        )
    return FileResponse(path=filename, filename=filename, media_type="image/jpeg")
