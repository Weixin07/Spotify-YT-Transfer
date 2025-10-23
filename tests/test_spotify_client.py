from spotify_yt_transfer.clients.spotify_client import SpotifyClient


def test_spotify_client_init(monkeypatch):
    # stub auth manager
    monkeypatch.setattr(
        "spotify_yt_transfer.clients.spotify_client.SpotifyOAuth", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        "spotify_yt_transfer.clients.spotify_client.spotipy.Spotify",
        lambda *args, **kwargs: object(),
    )
    client = SpotifyClient()
    assert hasattr(client, "get_playlist_tracks")
