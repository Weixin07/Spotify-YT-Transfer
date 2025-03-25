import os
import requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI


def download_playlist_cover(playlist_id: str, save_path: str = "cover.jpg"):
    """
    Downloads the cover image of a Spotify playlist and saves it to disk.

    Parameters:
    - playlist_id: The Spotify playlist ID.
    - save_path: Local file path to save the cover image.
    """
    # Create a Spotify client using OAuth2
    sp = spotipy.Spotify(
        auth_manager=SpotifyOAuth(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET,
            redirect_uri=SPOTIFY_REDIRECT_URI,
            scope="playlist-read-private",
        )
    )

    # Retrieve the playlist details
    playlist = sp.playlist(playlist_id)

    # Check if images exist in the playlist object
    if playlist.get("images"):
        # Use the first image in the list
        image_url = playlist["images"][0]["url"]
        print(f"Found cover image URL: {image_url}")
        # Download the image
        response = requests.get(image_url)
        if response.status_code == 200:
            with open(save_path, "wb") as f:
                f.write(response.content)
            print(f"Cover image saved to {save_path}")
        else:
            print("Failed to download image. HTTP Status Code:", response.status_code)
    else:
        print("No cover image found for this playlist.")


if __name__ == "__main__":
    # Prompt the user for a Spotify playlist ID
    playlist_id = input("Enter Spotify playlist ID: ").strip()
    download_playlist_cover(playlist_id)
