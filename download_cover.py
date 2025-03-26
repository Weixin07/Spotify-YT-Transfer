import os
import requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI
import logging
from PIL import Image, ImageOps
from io import BytesIO

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)


def download_playlist_cover(
    playlist_id: str,
    save_path: str = "cover.jpg",
    min_width: int = 640,
    min_height: int = 480,
):
    """
    Downloads the cover image of a Spotify playlist that meets the minimum resolution criteria.
    If no image meets the criteria, the largest available image is enhanced to 640x640 (keeping the original ratio via center cropping).

    Parameters:
    - playlist_id: The Spotify playlist ID.
    - save_path: Local file path to save the cover image.
    - min_width: Minimum required width in pixels.
    - min_height: Minimum required height in pixels.
    """
    sp = spotipy.Spotify(
        auth_manager=SpotifyOAuth(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET,
            redirect_uri=SPOTIFY_REDIRECT_URI,
            scope="playlist-read-private",
        )
    )

    playlist = sp.playlist(playlist_id)

    if playlist.get("images"):
        images = playlist["images"]
        # Filter images with dimensions meeting the minimum requirements.
        valid_images = [
            img
            for img in images
            if (img.get("width") or 0) >= min_width
            and (img.get("height") or 0) >= min_height
        ]
        if valid_images:
            # Choose the image with the smallest area among those that meet the criteria.
            chosen_image = min(
                valid_images,
                key=lambda x: (x.get("width") or 0) * (x.get("height") or 0),
            )
            logging.info(
                f"Selected image with resolution {chosen_image.get('width')}x{chosen_image.get('height')} meeting requirements."
            )
            image_url = chosen_image["url"]
            response = requests.get(image_url)
            if response.status_code == 200:
                with open(save_path, "wb") as f:
                    f.write(response.content)
                logging.info(f"Cover image saved to {save_path}")
            else:
                logging.error(
                    f"Failed to download image. HTTP Status Code: {response.status_code}"
                )
        else:
            # No image meets the minimum resolution. Use the largest available image.
            chosen_image = max(
                images, key=lambda x: (x.get("width") or 0) * (x.get("height") or 0)
            )
            logging.warning(
                f"No image met the minimum resolution. Using largest available image with resolution {chosen_image.get('width')}x{chosen_image.get('height')}."
            )
            image_url = chosen_image["url"]
            response = requests.get(image_url)
            if response.status_code == 200:
                # Open the downloaded image with Pillow
                original_image = Image.open(BytesIO(response.content))
                # Enlarge (and center-crop) the image to 640x640 while preserving aspect ratio.
                enhanced_image = ImageOps.fit(
                    original_image, (640, 640), method=Image.BICUBIC
                )
                enhanced_image.save(save_path)
                logging.info(f"Enhanced cover image saved to {save_path}")
            else:
                logging.error(
                    f"Failed to download image. HTTP Status Code: {response.status_code}"
                )
    else:
        logging.warning("No cover image found for this playlist.")


if __name__ == "__main__":
    playlist_id = input("Enter Spotify playlist ID: ").strip()
    download_playlist_cover(playlist_id)
