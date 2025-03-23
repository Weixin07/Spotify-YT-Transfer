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
    for track in tracks:
        query = f"{track['name']} {track['artist']}"
        spotify_unique_id = f"{track['name']}|{track['artist']}"
        cached_youtube_id = get_matched_youtube_id(spotify_unique_id)

        # If no cached match, do a new search
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

        # If video already in playlist, skip
        if video_id in existing_videos:
            print(
                f"Skipping '{track['name']}' (video_id={video_id}) - already in playlist."
            )
            continue

        # Retry logic to add the video
        if video_id:
            retries = 0
            max_retries = 3
            while retries < max_retries:
                try:
                    yt.add_video_to_playlist(
                        playlist_id=yt_playlist_id, video_id=video_id
                    )
                    print(f"Successfully added {video_id} for track '{track['name']}'")
                    # Once added, record it in 'existing_videos'
                    existing_videos.add(video_id)
                    break
                except HttpError as e:
                    print(f"Attempt {retries + 1} failed for video {video_id}: {e}")
                    retries += 1
                    time.sleep(2**retries)
                except Exception as ex:
                    print(f"Unexpected error for video {video_id}: {ex}")
                    break
            if retries == max_retries:
                print(f"Failed to add video {video_id} after {max_retries} attempts.")

    return {"message": "Migration complete", "youtube_playlist_id": yt_playlist_id}
