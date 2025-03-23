import spotipy
from spotipy.oauth2 import SpotifyOAuth
from config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI


class SpotifyClient:
    def __init__(self):
        self.sp = spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                client_id=SPOTIFY_CLIENT_ID,
                client_secret=SPOTIFY_CLIENT_SECRET,
                redirect_uri=SPOTIFY_REDIRECT_URI,
                scope="playlist-read-private",
            )
        )

    def get_playlist_tracks(self, playlist_id: str):
        results = self.sp.playlist_items(playlist_id)
        tracks = []
        while results:
            for item in results.get("items", []):
                track = item.get("track", {})
                tracks.append(
                    {
                        "name": track.get("name"),
                        "artist": ", ".join(
                            [artist["name"] for artist in track.get("artists", [])]
                        ),
                        "album": track.get("album", {}).get("name"),
                        "duration_ms": track.get("duration_ms"),
                    }
                )
            results = self.sp.next(results) if self.sp.next(results) else None
        return tracks
