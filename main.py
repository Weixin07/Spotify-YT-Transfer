import time, json, logging
from contextlib import asynccontextmanager

from logging.config import dictConfig
from logging.handlers import RotatingFileHandler

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.concurrency import run_in_threadpool

from googleapiclient.errors import HttpError
from spotipy.oauth2 import SpotifyOAuth
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded
from config import (
    SPOTIFY_CLIENT_ID,
    SPOTIFY_CLIENT_SECRET,
    SPOTIFY_REDIRECT_URI,
    engine,
    Base,
)
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
import models  # just to register classes
from config import (
    SPOTIFY_CLIENT_ID,
    SPOTIFY_CLIENT_SECRET,
    SPOTIFY_REDIRECT_URI,
    engine,
    Base,
    LOG_FILE_NAME,
    LOG_MAX_BYTES,
    LOG_BACKUP_COUNT,
)

Base.metadata.create_all(bind=engine)

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
                "filename": LOG_FILE_NAME,
                "maxBytes": LOG_MAX_BYTES,
                "backupCount": LOG_BACKUP_COUNT,
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
    """Lifespan context manager for application startup and shutdown.

    Args:
        app (FastAPI): The FastAPI application instance.

    Yields:
        None: Control is yielded back to the application during runtime.

    Side Effects:
        - Initializes the database.
        - Instantiates SpotifyClient and YouTubeClient singletons in `app.state`.
        - Logs startup and shutdown events.
    """
    logger.info("Starting up: Initializing database.")
    init_db()
    app.state.spotify = SpotifyClient()
    app.state.youtube = YouTubeClient()
    yield
    logger.info("Shutting down: Cleanup if needed.")


# Define OpenAPI tags for grouping endpoints
openapi_tags = [
    {"name": "Info", "description": "General informational endpoints"},
    {"name": "Auth", "description": "OAuth and authentication callbacks"},
    {"name": "Migration", "description": "Playlist migration operations"},
    {"name": "Utilities", "description": "Utility endpoints (e.g., cover download)"},
]

app = FastAPI(
    title="Spotify to YouTube Music Playlist Migrator",
    description="A utility service to migrate Spotify playlists into YouTube Music playlists, handling OAuth, track matching, and cover images.",
    version="0.1.0",
    contact={"name": "developer", "email": "faithlin07@gmail.com"},
    license_info={"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
    openapi_tags=openapi_tags,
    lifespan=lifespan,
    swagger_ui_parameters={"docExpansion": "none", "defaultModelsExpandDepth": -1},
    redoc_ui_parameters={"hideHostname": True},
)


# Rate limiting: 10 requests per minute per IP
limiter = Limiter(key_func=get_remote_address, default_limits=["10/minute"])
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


def get_spotify_client() -> SpotifyClient:
    """Retrieve the SpotifyClient singleton from the application state.

    Returns:
        SpotifyClient: The initialized SpotifyClient instance.
    """
    return app.state.spotify


def get_youtube_client() -> YouTubeClient:
    """Retrieve the YouTubeClient singleton from the application state.

    Returns:
        YouTubeClient: The initialized YouTubeClient instance.
    """
    return app.state.youtube


@app.get(
    "/",
    tags=["Info"],
    summary="Root endpoint",
    description="Returns a welcome message to confirm the service is running.",
    responses={
        200: {
            "description": "Service is up",
            "content": {
                "application/json": {
                    "example": {"message": "Welcome to the Playlist Migrator API"}
                }
            },
        }
    },
)
def read_root():
    """Root endpoint returning a welcome message.

    Returns:
        dict: A dictionary containing a welcome message.
    """
    logger.info("Received request at root endpoint.")
    return {"message": "Welcome to the Playlist Migrator API"}


@app.get(
    "/spotify/callback",
    tags=["Auth"],
    summary="Spotify OAuth2 callback",
    description=(
        "Handles Spotify OAuth2 callback by exchanging the provided "
        "`code` query parameter for access tokens."
    ),
    responses={
        400: {
            "description": "Missing or invalid code parameter",
            "content": {
                "application/json": {
                    "example": {"detail": "Missing code parameter in callback."}
                }
            },
        },
        200: {
            "description": "Authentication successful",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Spotify authentication successful",
                        "token_info": {
                            "access_token": "BQD...xyz",
                            "refresh_token": "AQD...abc",
                            "...": "...",
                        },
                    }
                }
            },
        },
    },
)
async def spotify_callback(request: Request):
    """Handle Spotify OAuth2 callback and exchange code for tokens.

    Args:
        request (Request): The incoming HTTP request containing query parameters.

    Returns:
        dict: A message indicating success and the Spotify token information.

    Raises:
        HTTPException: If the 'code' parameter is missing or exchange fails.
    """
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
            scope="playlist-read-private user-library-read",
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
    """Check if a Google API HttpError is due to quota exhaustion.

    Args:
        e (HttpError): The caught HttpError exception from Google API client.

    Returns:
        bool: True if the error reason is 'quotaExceeded', False otherwise.
    """
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


@app.get(
    "/migrate",
    response_model=MigrateResponse,
    tags=["Migration"],
    summary="Migrate Spotify playlist",
    description=(
        "Migrates a Spotify playlist (or liked songs if no playlist ID is given) "
        "into a YouTube Music playlist."
    ),
    responses={
        200: {
            "description": "Migration completed",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Migration complete",
                        "youtube_playlist_id": "PL1234567890abcdef",
                    }
                }
            },
        },
        400: {
            "description": "Invalid request or Spotify API error",
            "content": {
                "application/json": {
                    "example": {"detail": "Error retrieving Spotify tracks: ..."}
                }
            },
        },
        429: {
            "description": "YouTube API quota exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "YouTube API quota exceeded—migration aborted."
                    }
                }
            },
        },
    },
)
async def migrate_playlist(
    params: MigrateParams = Depends(),
    spotify: SpotifyClient = Depends(get_spotify_client),
    yt: YouTubeClient = Depends(get_youtube_client),
):
    """Migrate a Spotify playlist to YouTube Music.

    Given either a Spotify playlist ID or the user’s liked songs, this endpoint:
    1. Retrieves tracks from Spotify.
    2. Finds or creates a YouTube playlist.
    3. Searches YouTube for each track and adds videos to the playlist.
    4. Records failures and retries them.

    Args:
        params (MigrateParams): Migration parameters (Spotify playlist ID or liked songs, YouTube playlist title).
        spotify (SpotifyClient): Spotify API client dependency.
        yt (YouTubeClient): YouTube API client dependency.

    Returns:
        MigrateResponse: Contains migration status and resulting YouTube playlist ID.

    Raises:
        HTTPException: On API errors (e.g., retrieving tracks, quota exceeded, authentication issues).
    """
    spotify_playlist_id = params.spotify_playlist_id
    youtube_playlist_title = params.youtube_playlist_title

    quota_exceeded = False

    # 1. Get tracks from Spotify (playlist or liked songs)
    try:
        if spotify_playlist_id:
            tracks = await run_in_threadpool(
                spotify.get_playlist_tracks, spotify_playlist_id
            )
            logger.info(
                f"Retrieved {len(tracks)} tracks from Spotify playlist {spotify_playlist_id}."
            )
        else:
            tracks = await run_in_threadpool(spotify.get_liked_tracks)
            logger.info(f"Retrieved {len(tracks)} liked songs from Spotify account.")
    except Exception as e:
        logger.error(f"Error retrieving Spotify tracks: {e}")
        raise HTTPException(
            status_code=400, detail=f"Error retrieving Spotify tracks: {str(e)}"
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


@app.get(
    "/check_missing",
    response_model=CheckMissingResponse,
    tags=["Utilities"],
    summary="Check missing tracks",
    description=(
        "Compares a Spotify playlist with a YouTube playlist and returns "
        "tracks that are missing, duplicated, or unavailable."
    ),
    responses={
        200: {
            "description": "Missing/duplicate/unavailable tracks listed",
            "content": {
                "application/json": {
                    "example": {
                        "missing_tracks": [
                            {
                                "unique_id": "Song|Artist",
                                "track_name": "Song",
                                "artist": "Artist",
                                "album": "Album",
                                "cached_youtube_id": "abcd1234",
                            }
                        ],
                        "duplicate_tracks": [{"unique_id": "Song|Artist", "count": 2}],
                        "unavailable_tracks": [
                            {
                                "name": "Song",
                                "artist": None,
                                "album": None,
                                "duration_ms": None,
                            }
                        ],
                    }
                }
            },
        }
    },
)
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
@app.get(
    "/youtube/playlist",
    response_model=YouTubePlaylistResponse,
    tags=["Utilities"],
    summary="Get YouTube playlist by name",
    description=(
        "Retrieves the YouTube playlist ID for a given playlist name in the user's account."
    ),
    responses={
        200: {
            "description": "Playlist found",
            "content": {
                "application/json": {
                    "example": {
                        "playlist_name": "My Favourite Songs",
                        "playlist_id": "PLabcdef123456",
                    }
                }
            },
        },
        404: {
            "description": "Playlist not found",
            "content": {
                "application/json": {"example": {"detail": "Playlist 'Foo' not found."}}
            },
        },
    },
)
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
            status_code=404, detail=f"Playlist '{playlist_name}' not found."
        )


# Download Spotify Playlist Cover
@app.get(
    "/download_cover",
    tags=["Utilities"],
    summary="Download playlist cover",
    description="Downloads a Spotify playlist’s cover image and returns it as a JPEG file.",
    responses={
        200: {
            "description": "Cover image file returned",
            "content": {"image/jpeg": {}},
        },
        500: {
            "description": "Error during cover download",
            "content": {
                "application/json": {
                    "example": {"detail": "Error downloading cover image: ..."}
                }
            },
        },
    },
)
async def download_cover_endpoint(playlist_id: str, filename: str = "cover.jpg"):
    """Download a Spotify playlist cover image and serve it as a JPEG file.

    Args:
        playlist_id (str): The Spotify playlist ID whose cover to download.
        filename (str): Filename to save and return. Defaults to "cover.jpg".

    Returns:
        FileResponse: A FastAPI response with the image file.

    Raises:
        HTTPException: If downloading the cover image fails.
    """

    try:
        await run_in_threadpool(download_playlist_cover, playlist_id, filename)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error downloading cover image: {str(e)}"
        )
    return FileResponse(path=filename, filename=filename, media_type="image/jpeg")
