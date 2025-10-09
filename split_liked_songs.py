import logging
from spotify_client import SpotifyClient

logger = logging.getLogger(__name__)


def split_liked_songs(
    playlist_base_name: str,
    tracks_per_playlist: int = 1000,
    public: bool = False
) -> dict:
    """
    Splits the user's Spotify liked songs into multiple playlists with a specified number of tracks each.

    Args:
        playlist_base_name (str): Base name for the playlists. Will be suffixed with '-1', '-2', etc.
        tracks_per_playlist (int): Number of tracks per playlist (default: 1000, max: 10000).
        public (bool): Whether the created playlists should be public (default: False).

    Returns:
        dict: A dictionary containing:
            - total_tracks: Total number of liked songs processed
            - playlists_created: List of created playlist info (name, id, track_count)

    Raises:
        Exception: If there's an error retrieving liked songs or creating playlists.
    """
    spotify = SpotifyClient()

    # Get current user
    logger.info("Retrieving current user information.")
    user = spotify.get_current_user()
    user_id = user.get('id')
    logger.info(f"User ID: {user_id}")

    # Retrieve all liked songs with URIs
    logger.info("Retrieving liked songs with URIs.")
    liked_tracks = spotify.get_liked_tracks(include_uri=True)
    total_tracks = len(liked_tracks)
    logger.info(f"Total liked songs: {total_tracks}")

    if total_tracks == 0:
        logger.warning("No liked songs found.")
        return {
            "total_tracks": 0,
            "playlists_created": []
        }

    # Calculate number of playlists needed
    num_playlists = (total_tracks + tracks_per_playlist - 1) // tracks_per_playlist
    logger.info(f"Will create {num_playlists} playlists with {tracks_per_playlist} tracks each.")

    playlists_created = []

    # Split tracks into chunks and create playlists
    for playlist_num in range(1, num_playlists + 1):
        start_idx = (playlist_num - 1) * tracks_per_playlist
        end_idx = min(start_idx + tracks_per_playlist, total_tracks)
        chunk = liked_tracks[start_idx:end_idx]

        # Create playlist name
        playlist_name = f"{playlist_base_name}-{playlist_num}"
        description = f"Liked Songs split {playlist_num}/{num_playlists} (tracks {start_idx + 1}-{end_idx})"

        logger.info(f"Creating playlist '{playlist_name}' with {len(chunk)} tracks.")

        # Create the playlist
        playlist_id = spotify.create_playlist(
            user_id=user_id,
            name=playlist_name,
            description=description,
            public=public
        )

        # Extract URIs from the chunk
        track_uris = [track['uri'] for track in chunk if track.get('uri')]
        logger.info(f"Adding {len(track_uris)} tracks to playlist '{playlist_name}'.")

        # Add tracks in batches of 100 (Spotify API limit)
        batch_size = 100
        for batch_start in range(0, len(track_uris), batch_size):
            batch_end = min(batch_start + batch_size, len(track_uris))
            batch_uris = track_uris[batch_start:batch_end]

            logger.info(
                f"Adding batch {batch_start // batch_size + 1} "
                f"({len(batch_uris)} tracks) to playlist '{playlist_name}'."
            )
            spotify.add_tracks_to_playlist(playlist_id, batch_uris)

        logger.info(f"Successfully created and populated playlist '{playlist_name}'.")

        playlists_created.append({
            "name": playlist_name,
            "playlist_id": playlist_id,
            "track_count": len(chunk)
        })

    logger.info(f"Split operation complete. Created {len(playlists_created)} playlists.")

    return {
        "total_tracks": total_tracks,
        "playlists_created": playlists_created
    }
