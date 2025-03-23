from fastapi import FastAPI, HTTPException, Request
from spotify_client import SpotifyClient
from youtube_client import YouTubeClient
from track_matcher import match_track
from config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import time
from googleapiclient.errors import HttpError

app = FastAPI(title="Spotify to YouTube Music Playlist Migrator")


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
    # Initialize clients
    spotify = SpotifyClient()
    yt = YouTubeClient()

    # Retrieve Spotify tracks
    try:
        tracks = spotify.get_playlist_tracks(spotify_playlist_id)
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Error retrieving Spotify playlist: {str(e)}"
        )

    # Create a new YouTube playlist
    try:
        yt_playlist_id = yt.create_playlist(
            title=youtube_playlist_title, description="Migrated from Spotify"
        )
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Error creating YouTube playlist: {str(e)}"
        )

    # Process each track: search YouTube and add to the playlist
    for track in tracks:
        query = f"{track['name']} {track['artist']}"
        # Retrieve a candidate video from YouTube
        video_id = yt.search_video(query)
        if video_id:
            retries = 0
            max_retries = 3
            while retries < max_retries:
                try:
                    yt.add_video_to_playlist(
                        playlist_id=yt_playlist_id, video_id=video_id
                    )
                    print(
                        f"Successfully added video {video_id} for track '{track['name']}'"
                    )
                    break  # Exit the retry loop on success
                except HttpError as e:
                    print(f"Attempt {retries+1} failed for video {video_id}: {e}")
                    retries += 1
                    time.sleep(2**retries)  # Exponential backoff: 2, 4, 8 seconds...
                except Exception as e:
                    print(f"Unexpected error for video {video_id}: {e}")
                    break  # Exit loop if error is not HttpError
            if retries == max_retries:
                print(f"Failed to add video {video_id} after {max_retries} attempts.")
        else:
            print(
                f"No matching video found for track: {track['name']} by {track['artist']}"
            )

    return {"message": "Migration complete", "youtube_playlist_id": yt_playlist_id}
