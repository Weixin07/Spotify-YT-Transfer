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

    try:
        tracks = spotify.get_playlist_tracks(spotify_playlist_id)
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Error retrieving Spotify playlist: {str(e)}"
        )

    try:
        yt_playlist_id = yt.create_playlist(
            title=youtube_playlist_title, description="Migrated from Spotify"
        )
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Error creating YouTube playlist: {str(e)}"
        )

    for track in tracks:
        # Build a query for the search
        query = f"{track['name']} {track['artist']}"

        # Use the track's unique Spotify name+artist as an identifier
        # Alternatively, you could store the actual Spotify track ID if available
        spotify_unique_id = f"{track['name']}|{track['artist']}"

        # Check if we already have a match in the cache
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

        # Now add the matched video to the playlist, with retry logic
        if video_id:
            retries = 0
            max_retries = 3
            while retries < max_retries:
                try:
                    yt.add_video_to_playlist(
                        playlist_id=yt_playlist_id, video_id=video_id
                    )
                    print(f"Successfully added {video_id} for track '{track['name']}'")
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
