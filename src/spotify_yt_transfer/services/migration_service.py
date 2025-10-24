"""Service for migrating Spotify playlists to YouTube Music."""

import logging

from googleapiclient.errors import HttpError

from spotify_yt_transfer.clients import SpotifyClient, YouTubeClient
from spotify_yt_transfer.database.repository import TrackRepository
from spotify_yt_transfer.services.exceptions import QuotaExceededError
from spotify_yt_transfer.services.track_matcher import TrackMatcher

logger = logging.getLogger(__name__)


def _is_quota_exceeded(error: HttpError) -> bool:
    """
    Determine if the HttpError is due to YouTube API quota exhaustion.

    Args:
        error: Exception raised by the YouTube API client

    Returns:
        True if the error reason equals 'quotaExceeded', False otherwise
    """
    try:
        import json

        status = error.resp.status
        body = error.content.decode()
        payload = json.loads(body)
        reason = payload.get("error", {}).get("errors", [{}])[0].get("reason", "")
        return status == 403 and reason == "quotaExceeded"
    except Exception:
        return False


class MigrationService:
    """
    Service for migrating Spotify playlists to YouTube Music.

    Handles the complete migration workflow including:
    - Fetching tracks from Spotify
    - Searching for matching YouTube videos with fuzzy matching
    - Creating/finding YouTube playlists
    - Adding videos to playlists
    - Handling failures and retries
    """

    def __init__(
        self,
        spotify_client: SpotifyClient,
        youtube_client: YouTubeClient,
        repository: TrackRepository,
        track_matcher: TrackMatcher | None = None,
    ):
        """
        Initialize the migration service.

        Args:
            spotify_client: Spotify API client
            youtube_client: YouTube API client
            repository: Database repository for track caching
            track_matcher: Optional TrackMatcher instance (creates default if None)
        """
        self.spotify = spotify_client
        self.youtube = youtube_client
        self.repo = repository
        self.matcher = track_matcher or TrackMatcher()
        logger.info(f"MigrationService initialized with fuzzy match threshold: {self.matcher.threshold}")

    def migrate_playlist(
        self,
        youtube_playlist_title: str,
        spotify_playlist_id: str | None = None,
    ) -> dict[str, str]:
        """
        Migrate a Spotify playlist to YouTube Music.

        Args:
            youtube_playlist_title: Title for the YouTube playlist
            spotify_playlist_id: Spotify playlist ID (if None, uses liked songs)

        Returns:
            Dictionary with migration result and YouTube playlist ID

        Raises:
            Exception: If migration fails due to API errors or quota exhaustion
        """
        logger.info(f"Starting migration to '{youtube_playlist_title}'")

        # 1. Get tracks from Spotify
        if spotify_playlist_id:
            tracks = self.spotify.get_playlist_tracks(spotify_playlist_id)
            logger.info(f"Retrieved {len(tracks)} tracks from playlist {spotify_playlist_id}")
        else:
            tracks = self.spotify.get_liked_tracks()
            logger.info(f"Retrieved {len(tracks)} liked songs")

        if not tracks:
            logger.warning("No tracks found to migrate")
            return {"message": "No tracks to migrate", "youtube_playlist_id": ""}

        # 2. Find or create YouTube playlist
        existing_playlist_id = self.youtube.find_playlist_by_name(youtube_playlist_title)
        if existing_playlist_id:
            yt_playlist_id = existing_playlist_id
            logger.info(f"Using existing playlist: {yt_playlist_id}")
        else:
            yt_playlist_id = self.youtube.create_playlist(
                title=youtube_playlist_title,
                description="Migrated from Spotify",
            )
            logger.info(f"Created new playlist: {yt_playlist_id}")

        # 3. Process each track
        failed_attempts: list[tuple[str, str, str]] = []

        for idx, track in enumerate(tracks, start=1):
            spotify_id = track.get("id")
            track_name = track.get("name")
            artist = track.get("artist")

            if not spotify_id:
                logger.warning(f"Skipping track {idx} - missing Spotify ID")
                continue

            if not track_name or not artist:
                logger.warning(f"Skipping track {idx} (ID: {spotify_id}) - missing name or artist")
                continue

            logger.info(f"Processing {idx}/{len(tracks)}: {track_name} by {artist} (ID: {spotify_id})")

            query = f"{track_name} {artist}"

            # Check cache using real Spotify ID
            matched_record = self.repo.get_matched_track(spotify_id)
            failed_record = self.repo.get_failed_track(spotify_id)

            if matched_record:
                video_id = matched_record.youtube_id
                logger.info(f"Using cached match: {video_id}")
            else:
                # Search YouTube with fuzzy matching
                try:
                    # Get multiple candidates from YouTube
                    candidates = self.youtube.search_video_candidates(query, max_results=10)

                    if not candidates:
                        logger.warning(f"No YouTube candidates found for: {track_name}")
                        continue

                    logger.info(f"Found {len(candidates)} candidates for '{track_name}'")

                    # Use fuzzy matching to find the best match
                    spotify_track_info = {
                        "name": track_name,
                        "artist": artist,
                        "album": track.get("album"),
                    }
                    video_id = self.matcher.match_track(spotify_track_info, candidates)

                    if video_id:
                        self.repo.save_matched_track(
                            spotify_id=spotify_id,  # Use real Spotify ID
                            song_name=track_name,
                            artist=artist,
                            youtube_id=video_id,
                            album=track.get("album"),
                        )
                        logger.info(f"Fuzzy matched and cached: {video_id}")
                    else:
                        logger.warning(
                            f"No match above threshold ({self.matcher.threshold}) for: {track_name}"
                        )
                        continue
                except HttpError as e:
                    if _is_quota_exceeded(e):
                        logger.error("YouTube API quota exceeded - stopping migration")
                        raise QuotaExceededError(
                            f"YouTube API quota exceeded at track {idx}/{len(tracks)}",
                            service="youtube",
                            details={"track_index": idx, "total_tracks": len(tracks)},
                        ) from e
                    logger.error(f"Error searching for track: {e}")
                    continue

            # Add to playlist
            if video_id:
                try:
                    self.youtube.add_video_to_playlist(yt_playlist_id, video_id)
                    logger.info(f"Added {video_id} to playlist")

                    # Clear from failed tracks if it was previously failed
                    if failed_record:
                        self.repo.clear_failed_track(spotify_id)

                except HttpError as e:
                    if _is_quota_exceeded(e):
                        logger.error("YouTube API quota exceeded - stopping migration")
                        raise QuotaExceededError(
                            f"YouTube API quota exceeded at track {idx}/{len(tracks)}",
                            service="youtube",
                            details={"track_index": idx, "total_tracks": len(tracks)},
                        ) from e

                    logger.error(f"Failed to add video {video_id}: {e}")
                    failed_attempts.append((spotify_id, video_id, "add_failed"))
                except Exception as ex:
                    logger.error(f"Unexpected error adding {video_id}: {ex}")
                    failed_attempts.append((spotify_id, video_id, "unknown_error"))

        # 4. Record failures
        for spotify_id, yid, reason in failed_attempts:
            self.repo.record_failed_track(spotify_id, yid, reason)
            logger.info(f"Recorded failed track: {spotify_id}")

        # 5. Retry failures
        logger.info(f"Starting retry pass for {len(failed_attempts)} failed tracks")
        for spotify_id, yid, _ in failed_attempts:
            try:
                self.youtube.add_video_to_playlist(yt_playlist_id, yid)
                logger.info(f"Retry success: Added {yid}")
                self.repo.clear_failed_track(spotify_id)
            except HttpError as e:
                if not _is_quota_exceeded(e):
                    logger.error(f"Retry failed for {yid}: {e}")
                else:
                    logger.error("Quota exceeded during retry pass")
                    break
            except Exception as ex:
                logger.error(f"Unexpected error during retry for {yid}: {ex}")

        logger.info(f"Migration complete. YouTube playlist ID: {yt_playlist_id}")
        return {"message": "Migration complete", "youtube_playlist_id": yt_playlist_id}
