import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import time
from googleapiclient.errors import HttpError
from spotify_client import *
from youtube_client import *
from track_matcher import *
from data_storage import *

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("Starting up: Initializing database.")
    init_db()
    yield
    logging.info("Shutting down: Cleanup if needed.")


app = FastAPI(title="Spotify to YouTube Music Playlist Migrator", lifespan=lifespan)


@app.get("/")
def read_root():
    logging.info("Received request at root endpoint.")
    return {"message": "Welcome to the Playlist Migrator API"}


@app.get("/spotify/callback")
async def spotify_callback(request: Request):
    code = request.query_params.get("code")
    if not code:
        logging.error("Spotify callback: Missing 'code' parameter.")
        raise HTTPException(
            status_code=400, detail="Missing code parameter in callback."
        )
    try:
        logging.info("Processing Spotify callback with code received.")
        spotify_auth_manager = SpotifyOAuth(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET,
            redirect_uri=SPOTIFY_REDIRECT_URI,
            scope="playlist-read-private",
        )
        token_info = spotify_auth_manager.get_access_token(code)
        logging.info("Spotify authentication successful.")
    except Exception as e:
        logging.error(f"Spotify authentication failed: {e}")
        raise HTTPException(status_code=400, detail=f"Authentication failed: {str(e)}")
    return {"message": "Spotify authentication successful", "token_info": token_info}


@app.get("/migrate")
def migrate_playlist(spotify_playlist_id: str, youtube_playlist_title: str):
    logging.info(
        f"Migration started for Spotify playlist: {spotify_playlist_id} into YouTube playlist: '{youtube_playlist_title}'."
    )
    spotify = SpotifyClient()
    yt = YouTubeClient()

    # 1. Get tracks from Spotify
    try:
        tracks = spotify.get_playlist_tracks(spotify_playlist_id)
        logging.info(
            f"Retrieved {len(tracks)} tracks from Spotify playlist {spotify_playlist_id}."
        )
    except Exception as e:
        logging.error(f"Error retrieving Spotify playlist: {e}")
        raise HTTPException(
            status_code=400, detail=f"Error retrieving Spotify playlist: {str(e)}"
        )

    # 2. Check if a playlist with this name already exists
    existing_playlist_id = yt.find_playlist_by_name(youtube_playlist_title)
    if existing_playlist_id:
        yt_playlist_id = existing_playlist_id
        logging.info(
            f"Using existing YouTube playlist '{youtube_playlist_title}' with ID {existing_playlist_id}."
        )
        # Fetch existing videos in this playlist
        existing_videos = set(yt.get_playlist_items(yt_playlist_id))
        logging.info(f"Found {len(existing_videos)} existing videos in playlist.")
    else:
        try:
            yt_playlist_id = yt.create_playlist(
                title=youtube_playlist_title, description="Migrated from Spotify"
            )
            existing_videos = set()  # new playlist, no videos yet
            logging.info(
                f"Created new YouTube playlist '{youtube_playlist_title}' with ID {yt_playlist_id}."
            )
        except Exception as e:
            logging.error(f"Error creating YouTube playlist: {e}")
            raise HTTPException(
                status_code=400, detail=f"Error creating YouTube playlist: {str(e)}"
            )

    # 3. Iterate over each Spotify track and add to YT if not already in playlist
    failed_attempts = []  # keep track of songs that fail after all retries

    for idx, track in enumerate(tracks, start=1):
        logging.info(
            f"Processing track {idx}/{len(tracks)}: '{track['name']}' by {track['artist']}."
        )
        query = f"{track['name']} {track['artist']}"
        spotify_unique_id = f"{track['name']}|{track['artist']}"
        matched_record = get_matched_track(spotify_unique_id)
        failed_record = get_failed_track(spotify_unique_id)

        # If a match exists, reuse its youtube_id; otherwise, perform a new search.
        if matched_record:
            video_id = matched_record["youtube_id"]
            logging.info(f"Using cached match for track '{track['name']}': {video_id}.")
        else:
            try:
                video_id = yt.search_video(query)
                if video_id:
                    # Save full metadata: song name, artist, album, and youtube_id.
                    save_matched_track(
                        spotify_unique_id,
                        track["name"],
                        track["artist"],
                        track.get("album", ""),
                        video_id,
                    )
                    logging.info(
                        f"Cached new match for track '{track['name']}': {video_id}."
                    )
                else:
                    logging.warning(
                        f"No matching video found for track: '{track['name']}' by {track['artist']}."
                    )
                    continue
            except HttpError as e:
                logging.error(f"Error searching for track '{track['name']}': {e}")
                continue

        # Skip if already in playlist and no failure exists.
        if video_id in existing_videos and not failed_record:
            logging.info(
                f"Skipping track '{track['name']}' (video_id={video_id}) - already in playlist."
            )
            continue

        # Attempt to add the video with retries.
        if video_id:
            retries = 0
            max_retries = 3
            added_successfully = False

            while retries < max_retries:
                try:
                    yt.add_video_to_playlist(
                        playlist_id=yt_playlist_id, video_id=video_id
                    )
                    logging.info(
                        f"Successfully added video {video_id} for track '{track['name']}'."
                    )
                    existing_videos.add(video_id)
                    added_successfully = True
                    if failed_record:
                        clear_failed_track(spotify_unique_id)
                        logging.info(
                            f"Cleared previous failure record for track '{track['name']}'."
                        )
                    break
                except HttpError as e:
                    retries += 1
                    logging.error(
                        f"Attempt {retries} failed for video {video_id} (track '{track['name']}'): {e}"
                    )
                    time.sleep(2**retries)
                except Exception as ex:
                    logging.error(
                        f"Unexpected error for video {video_id} (track '{track['name']}'): {ex}"
                    )
                    break

            if not added_successfully:
                logging.error(
                    f"Failed to add video {video_id} for track '{track['name']}' after {max_retries} attempts."
                )
                failed_attempts.append(
                    (spotify_unique_id, video_id, "Add to playlist failed")
                )

    # 4. Record failed songs in DB and attempt a second pass.
    for spotify_id, yid, reason in failed_attempts:
        record_failed_track(spotify_id, yid, reason)
        logging.info(
            f"Recorded failed track {spotify_id} with video {yid} (Reason: {reason})."
        )

    logging.info("Starting second pass for failed tracks.")
    for spotify_id, yid, reason in failed_attempts:
        logging.info(f"Retrying failed track: {spotify_id} => {yid}")
        try:
            yt.add_video_to_playlist(playlist_id=yt_playlist_id, video_id=yid)
            logging.info(
                f"Second-pass success: Added video {yid} for track {spotify_id}."
            )
            clear_failed_track(spotify_id)
        except HttpError as e:
            logging.error(f"Second-pass attempt failed for video {yid}: {e}")
        except Exception as ex:
            logging.error(f"Unexpected error in second-pass for video {yid}: {ex}")

    logging.info(f"Migration complete. YouTube playlist ID: {yt_playlist_id}")
    return {"message": "Migration complete", "youtube_playlist_id": yt_playlist_id}
