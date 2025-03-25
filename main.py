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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Equivalent to "startup" work
    init_db()
    # Hand over control to the application
    yield
    # Cleanup or "shutdown" logic goes here if needed


app = FastAPI(title="Spotify to YouTube Music Playlist Migrator", lifespan=lifespan)


@app.get("/")
def read_root():
    return {"message": "Welcome to the Playlist Migrator API"}


@app.get("/spotify/callback")
async def spotify_callback(request: Request):
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(
            status_code=400, detail="Missing code parameter in callback."
        )
    try:
        spotify_auth_manager = SpotifyOAuth(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET,
            redirect_uri=SPOTIFY_REDIRECT_URI,
            scope="playlist-read-private",
        )
        token_info = spotify_auth_manager.get_access_token(code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Authentication failed: {str(e)}")
    return {"message": "Spotify authentication successful", "token_info": token_info}


@app.get("/migrate")
def migrate_playlist(spotify_playlist_id: str, youtube_playlist_title: str):
    spotify = SpotifyClient()
    yt = YouTubeClient()

    # 1. Get tracks from Spotify
    try:
        tracks = spotify.get_playlist_tracks(spotify_playlist_id)
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Error retrieving Spotify playlist: {str(e)}"
        )

    # 2. Check if a playlist with this name already exists
    existing_playlist_id = yt.find_playlist_by_name(youtube_playlist_title)
    if existing_playlist_id:
        yt_playlist_id = existing_playlist_id
        print(
            f"Using existing playlist '{youtube_playlist_title}' ({existing_playlist_id})."
        )
        # Fetch existing videos in this playlist
        existing_videos = set(yt.get_playlist_items(yt_playlist_id))
    else:
        # Create a new YouTube playlist if none found
        try:
            yt_playlist_id = yt.create_playlist(
                title=youtube_playlist_title, description="Migrated from Spotify"
            )
            existing_videos = set()  # new playlist, no videos yet
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Error creating YouTube playlist: {str(e)}"
            )

    # 3. Iterate over each Spotify track and add to YT if not already in playlist
    failed_attempts = []  # keep track of songs that fail after all retries

    for track in tracks:
        query = f"{track['name']} {track['artist']}"
        spotify_unique_id = f"{track['name']}|{track['artist']}"
        cached_youtube_id = get_matched_youtube_id(spotify_unique_id)

        # Check if this track has a previous failed record
        failed_record = get_failed_track(spotify_unique_id)

        # If no cached match, perform a new search
        if not cached_youtube_id:
            try:
                video_id = yt.search_video(query)
                if video_id:
                    save_matched_track(spotify_unique_id, video_id)
                else:
                    print(
                        f"No matching video found for track: {track['name']} by {track['artist']}"
                    )
                    continue
            except HttpError as e:
                print(f"Error searching for track: {e}")
                continue
        else:
            video_id = cached_youtube_id

        # If the video is already in the playlist and there's no failed record, skip it.
        if video_id in existing_videos and not failed_record:
            print(
                f"Skipping '{track['name']}' (video_id={video_id}) - already in playlist."
            )
            continue

        # For tracks with failed records, or those not in the playlist, attempt addition.
        if video_id:
            retries = 0
            max_retries = 3
            added_successfully = False

            while retries < max_retries:
                try:
                    yt.add_video_to_playlist(
                        playlist_id=yt_playlist_id, video_id=video_id
                    )
                    print(f"Successfully added {video_id} for track '{track['name']}'")
                    existing_videos.add(video_id)
                    added_successfully = True
                    # If there was a previous failure record, clear it upon success.
                    if failed_record:
                        clear_failed_track(spotify_unique_id)
                    break
                except HttpError as e:
                    print(f"Attempt {retries + 1} failed for video {video_id}: {e}")
                    retries += 1
                    time.sleep(2**retries)
                except Exception as ex:
                    print(f"Unexpected error for video {video_id}: {ex}")
                    break

            if not added_successfully:
                print(f"Failed to add video {video_id} after {max_retries} attempts.")
                failed_attempts.append(
                    (spotify_unique_id, video_id, "Add to playlist failed")
                )

    # 4. Record failed songs in DB and attempt a second pass
    for spotify_id, yid, reason in failed_attempts:
        record_failed_track(spotify_id, yid, reason)

    # Immediate second pass, ignoring concurrency concerns
    for spotify_id, yid, reason in failed_attempts:
        print(f"Retrying failed track: {spotify_id} => {yid}")
        try:
            yt.add_video_to_playlist(playlist_id=yt_playlist_id, video_id=yid)
            print(f"Second-pass success: {yid} for track {spotify_id}")
            clear_failed_track(spotify_id)  # remove from failed_tracks if successful
        except HttpError as e:
            print(f"Second-pass attempt failed for {yid}: {e}")
            # We leave it in the DB for potential later tries
        except Exception as ex:
            print(f"Unexpected error in second-pass for {yid}: {ex}")

    return {"message": "Migration complete", "youtube_playlist_id": yt_playlist_id}
