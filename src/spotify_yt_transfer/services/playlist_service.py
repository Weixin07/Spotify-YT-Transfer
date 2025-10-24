"""Service for playlist utility operations."""

import logging
from collections import Counter
from io import BytesIO
from pathlib import Path
from typing import Any

import requests
from PIL import Image, ImageOps
from tenacity import retry, stop_after_attempt, wait_exponential

from spotify_yt_transfer.clients import SpotifyClient, YouTubeClient
from spotify_yt_transfer.core.config import settings
from spotify_yt_transfer.database.repository import TrackRepository

logger = logging.getLogger(__name__)


class PlaylistService:
    """
    Service for playlist utility operations.

    Handles:
    - Finding missing tracks between Spotify and YouTube playlists
    - Splitting liked songs into multiple playlists
    - Downloading playlist cover images
    """

    def __init__(
        self,
        spotify_client: SpotifyClient,
        youtube_client: YouTubeClient,
        repository: TrackRepository,
    ):
        """
        Initialize the playlist service.

        Args:
            spotify_client: Spotify API client
            youtube_client: YouTube API client
            repository: Database repository for track caching
        """
        self.spotify = spotify_client
        self.youtube = youtube_client
        self.repo = repository

    def find_missing_tracks(
        self, spotify_playlist_id: str, youtube_playlist_id: str
    ) -> dict[str, Any]:
        """
        Compare Spotify playlist tracks with YouTube playlist videos.

        Args:
            spotify_playlist_id: Spotify playlist ID to compare
            youtube_playlist_id: YouTube playlist ID to compare

        Returns:
            Dictionary with missing_tracks, duplicate_tracks, and unavailable_tracks
        """
        logger.info(
            f"Comparing Spotify playlist {spotify_playlist_id} with YouTube playlist {youtube_playlist_id}"
        )

        # Retrieve Spotify tracks
        spotify_tracks = self.spotify.get_playlist_tracks(spotify_playlist_id)
        logger.info(f"Total Spotify tracks retrieved: {len(spotify_tracks)}")

        # Create unique keys and track mapping
        unique_ids: list[str] = []
        track_mapping: dict[str, dict[str, Any]] = {}
        unavailable_tracks: list[dict[str, Any]] = []

        for track in spotify_tracks:
            spotify_id = track.get("id")

            # Check for essential metadata including Spotify ID
            if not spotify_id or not track.get("name") or not track.get("artist"):
                unavailable_tracks.append(track)
                continue

            unique_ids.append(spotify_id)

            # Keep first occurrence for duplicates (though Spotify IDs should be unique)
            if spotify_id not in track_mapping:
                track_mapping[spotify_id] = track

        # Identify duplicates (Note: With real Spotify IDs, duplicates should be rare)
        counter = Counter(unique_ids)
        duplicate_tracks = [
            {"spotify_id": sid, "count": cnt} for sid, cnt in counter.items() if cnt > 1
        ]

        # Retrieve YouTube playlist video IDs
        youtube_video_ids = set(self.youtube.get_playlist_items(youtube_playlist_id))
        logger.info(f"Total YouTube videos retrieved: {len(youtube_video_ids)}")

        # Find missing tracks
        missing_tracks: list[dict[str, Any]] = []

        for spotify_id, track in track_mapping.items():
            matched_record = self.repo.get_matched_track(spotify_id)

            if matched_record:
                youtube_id = matched_record.youtube_id
                if youtube_id not in youtube_video_ids:
                    missing_tracks.append(
                        {
                            "spotify_id": spotify_id,  # Use real Spotify ID
                            "track_name": track["name"],
                            "artist": track["artist"],
                            "album": track.get("album", ""),
                            "cached_youtube_id": youtube_id,
                        }
                    )
            else:
                # No match exists - consider it missing
                missing_tracks.append(
                    {
                        "spotify_id": spotify_id,  # Use real Spotify ID
                        "track_name": track["name"],
                        "artist": track["artist"],
                        "album": track.get("album", ""),
                        "cached_youtube_id": None,
                    }
                )

        logger.info(
            f"Found {len(missing_tracks)} missing, {len(duplicate_tracks)} duplicates, "
            f"{len(unavailable_tracks)} unavailable"
        )

        return {
            "missing_tracks": missing_tracks,
            "duplicate_tracks": duplicate_tracks,
            "unavailable_tracks": unavailable_tracks,
        }

    def split_liked_songs(
        self,
        playlist_base_name: str,
        tracks_per_playlist: int = 1000,
        public: bool = False,
    ) -> dict[str, Any]:
        """
        Split user's Spotify liked songs into multiple playlists.

        Args:
            playlist_base_name: Base name for playlists (will be suffixed with '-1', '-2', etc.)
            tracks_per_playlist: Number of tracks per playlist (default: 1000, max: 10000)
            public: Whether created playlists should be public (default: False)

        Returns:
            Dictionary with total_tracks and playlists_created list
        """
        logger.info(f"Splitting liked songs into playlists of {tracks_per_playlist} tracks")

        # Get current user
        user = self.spotify.get_current_user()
        user_id = user.get("id")
        logger.info(f"User ID: {user_id}")

        # Retrieve all liked songs with URIs
        liked_tracks = self.spotify.get_liked_tracks(include_uri=True)
        total_tracks = len(liked_tracks)
        logger.info(f"Total liked songs: {total_tracks}")

        if total_tracks == 0:
            logger.warning("No liked songs found")
            return {"total_tracks": 0, "playlists_created": []}

        # Calculate number of playlists needed
        num_playlists = (total_tracks + tracks_per_playlist - 1) // tracks_per_playlist
        logger.info(f"Will create {num_playlists} playlists")

        playlists_created: list[dict[str, Any]] = []

        # Split tracks into chunks and create playlists
        for playlist_num in range(1, num_playlists + 1):
            start_idx = (playlist_num - 1) * tracks_per_playlist
            end_idx = min(start_idx + tracks_per_playlist, total_tracks)
            chunk = liked_tracks[start_idx:end_idx]

            # Create playlist name
            playlist_name = f"{playlist_base_name}-{playlist_num}"
            description = (
                f"Liked Songs split {playlist_num}/{num_playlists} "
                f"(tracks {start_idx + 1}-{end_idx})"
            )

            logger.info(f"Creating playlist '{playlist_name}' with {len(chunk)} tracks")

            # Create the playlist
            playlist_id = self.spotify.create_playlist(
                user_id=user_id,
                name=playlist_name,
                description=description,
                public=public,
            )

            # Extract URIs from the chunk
            track_uris = [track["uri"] for track in chunk if track.get("uri")]
            logger.info(f"Adding {len(track_uris)} tracks to playlist")

            # Add tracks in batches of 100 (Spotify API limit)
            batch_size = 100
            for batch_start in range(0, len(track_uris), batch_size):
                batch_end = min(batch_start + batch_size, len(track_uris))
                batch_uris = track_uris[batch_start:batch_end]

                logger.info(
                    f"Adding batch {batch_start // batch_size + 1} "
                    f"({len(batch_uris)} tracks) to playlist '{playlist_name}'"
                )
                self.spotify.add_tracks_to_playlist(playlist_id, batch_uris)

            logger.info(f"Successfully created and populated playlist '{playlist_name}'")

            playlists_created.append(
                {"name": playlist_name, "playlist_id": playlist_id, "track_count": len(chunk)}
            )

        logger.info(f"Split operation complete. Created {len(playlists_created)} playlists")

        return {"total_tracks": total_tracks, "playlists_created": playlists_created}

    @retry(
        stop=stop_after_attempt(settings.resilience.retries),
        wait=wait_exponential(
            multiplier=settings.resilience.backoff_factor,
            min=settings.resilience.min_backoff,
            max=settings.resilience.max_backoff,
        ),
        retry_error_callback=lambda retry_state: logger.error(
            f"Failed to download image after {retry_state.attempt_number} attempts"
        ),
    )
    def _download_image_with_retry(self, image_url: str) -> bytes:
        """Download an image with retry logic."""
        response = requests.get(image_url, timeout=settings.cover.http_timeout)
        response.raise_for_status()
        return response.content

    def download_playlist_cover(
        self,
        playlist_id: str,
        save_path: str | None = None,
        min_width: int | None = None,
        min_height: int | None = None,
    ) -> bytes:
        """
        Download the cover image of a Spotify playlist.

        Args:
            playlist_id: Spotify playlist ID
            save_path: Optional local file path to save the image
            min_width: Minimum required width (defaults to config)
            min_height: Minimum required height (defaults to config)

        Returns:
            Image bytes (JPEG format)

        Raises:
            ValueError: If no cover image is found
            requests.RequestException: If image download fails
        """
        min_width = min_width or settings.cover.min_width
        min_height = min_height or settings.cover.min_height

        logger.info(f"Downloading cover for playlist {playlist_id}")

        # Get playlist info
        playlist = self.spotify.sp.playlist(playlist_id)

        if not playlist.get("images"):
            raise ValueError("No cover image found for this playlist")

        images = playlist["images"]

        # Filter images meeting minimum requirements
        valid_images = [
            img
            for img in images
            if (img.get("width") or 0) >= min_width and (img.get("height") or 0) >= min_height
        ]

        if valid_images:
            # Choose smallest image that meets criteria
            chosen_image = min(
                valid_images,
                key=lambda x: (x.get("width") or 0) * (x.get("height") or 0),
            )
            logger.info(f"Selected image {chosen_image.get('width')}x{chosen_image.get('height')}")
            image_url = chosen_image["url"]
            image_bytes = self._download_image_with_retry(image_url)

        else:
            # No image meets minimum - use largest and enhance
            chosen_image = max(images, key=lambda x: (x.get("width") or 0) * (x.get("height") or 0))
            logger.warning(
                f"No image met minimum resolution. Using largest: "
                f"{chosen_image.get('width')}x{chosen_image.get('height')}"
            )
            image_url = chosen_image["url"]
            image_bytes = self._download_image_with_retry(image_url)

            # Enhance image to desired size
            original_image = Image.open(BytesIO(image_bytes))
            enhanced_image = ImageOps.fit(
                original_image,
                (settings.cover.enhance_size, settings.cover.enhance_size),
                method=Image.Resampling.BICUBIC,
            )

            # Convert to bytes
            buffer = BytesIO()
            enhanced_image.save(buffer, format="JPEG")
            image_bytes = buffer.getvalue()

            logger.info(
                f"Enhanced image to {settings.cover.enhance_size}x{settings.cover.enhance_size}"
            )

        # Optionally save to file
        if save_path:
            path = Path(save_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("wb") as f:
                f.write(image_bytes)
            logger.info(f"Cover image saved to {save_path}")

        return image_bytes
