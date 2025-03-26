import logging
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI

# Configure logging to display info-level messages with a timestamp.
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)


class SpotifyClient:
    def __init__(self):
        logging.info("Initializing SpotifyClient.")
        self.sp = spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                client_id=SPOTIFY_CLIENT_ID,
                client_secret=SPOTIFY_CLIENT_SECRET,
                redirect_uri=SPOTIFY_REDIRECT_URI,
                scope="playlist-read-private",
            )
        )
        logging.info("Spotify client initialized successfully.")

    def get_playlist_tracks(self, playlist_id: str):
        logging.info(f"Retrieving tracks for Spotify playlist ID: {playlist_id}")
        results = self.sp.playlist_items(playlist_id)
        tracks = []
        page = 1
        while results:
            items = results.get("items", [])
            logging.info(f"Processing page {page} with {len(items)} items.")
            for idx, item in enumerate(items, start=1):
                track = item.get("track", {})
                if track:
                    track_info = {
                        "name": track.get("name"),
                        "artist": ", ".join(
                            [artist["name"] for artist in track.get("artists", [])]
                        ),
                        "album": track.get("album", {}).get("name"),
                        "duration_ms": track.get("duration_ms"),
                    }
                    tracks.append(track_info)
                    logging.info(
                        f"Added track {idx} on page {page}: '{track_info['name']}' by {track_info['artist']}."
                    )
                else:
                    logging.warning(
                        f"Item {idx} on page {page} has no track information."
                    )
            results = self.sp.next(results) if self.sp.next(results) else None
            page += 1
        logging.info(f"Total tracks retrieved: {len(tracks)}")
        return tracks
