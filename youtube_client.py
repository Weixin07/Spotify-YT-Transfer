import os
import pickle
import logging
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request as GoogleAuthRequest
from googleapiclient.discovery import build
from config import YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REDIRECT_URI
import json
from googleapiclient.errors import HttpError
from cachetools import TTLCache, cached
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
    retry_if_exception,
    before_sleep_log,
)
from config import YOUTUBE_RETRY_ATTEMPTS, YOUTUBE_RETRY_MULTIPLIER, YOUTUBE_RETRY_MAX


# Helper to detect quotaExceeded errors
def _is_quota_exceeded(error: HttpError) -> bool:
    try:
        status = error.resp.status
        body = error.content.decode()
        payload = json.loads(body)
        reason = payload.get("error", {}).get("errors", [{}])[0].get("reason", "")
        return status == 403 and reason == "quotaExceeded"
    except Exception:
        return False


# If modifying these scopes, delete the file token.pickle.
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]

# Configure logging if not already configured by main application
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)

# 15 min TTL cache for search_video (max 1000 entries)
_youtube_search_cache = TTLCache(maxsize=1000, ttl=15 * 60)


class YouTubeClient:
    def __init__(self):
        logging.info("Initializing YouTubeClient.")
        self.creds = None
        self.service = self.authenticate()
        logging.info("YouTubeClient initialized successfully.")

    def authenticate(self):
        logging.info("Authenticating with YouTube API.")
        if os.path.exists("token.pickle"):
            logging.info("Found existing token.pickle. Loading credentials.")
            with open("token.pickle", "rb") as token:
                self.creds = pickle.load(token)
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                logging.info("Credentials expired. Refreshing token.")
                self.creds.refresh(GoogleAuthRequest())
            else:
                logging.info("No valid credentials found. Initiating OAuth2 flow.")
                flow = InstalledAppFlow.from_client_config(
                    {
                        "installed": {
                            "client_id": YOUTUBE_CLIENT_ID,
                            "client_secret": YOUTUBE_CLIENT_SECRET,
                            "redirect_uris": [YOUTUBE_REDIRECT_URI],
                            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                            "token_uri": "https://oauth2.googleapis.com/token",
                        }
                    },
                    SCOPES,
                )
                self.creds = flow.run_local_server(port=8002)
            with open("token.pickle", "wb") as token:
                pickle.dump(self.creds, token)
            logging.info("New credentials saved to token.pickle.")
        else:
            logging.info("Using valid credentials from token.pickle.")
        return build("youtube", "v3", credentials=self.creds)



    @cached(cache=_youtube_search_cache, key=lambda self, query: query)
    @retry(
        stop=stop_after_attempt(YOUTUBE_RETRY_ATTEMPTS),
        wait=wait_random_exponential(
            multiplier=YOUTUBE_RETRY_MULTIPLIER, max=YOUTUBE_RETRY_MAX
        ),
        retry=retry_if_exception(
            lambda e: isinstance(e, HttpError) and not _is_quota_exceeded(e)
        ),
        before_sleep=before_sleep_log(logging.getLogger(__name__), logging.WARNING),
    )
    def find_playlist_by_name(self, playlist_name: str) -> str:
        """
        Checks if a playlist with the given name already exists in the user's account.
        Returns the playlist ID if found, otherwise None.
        """
        logging.info(f"Searching for existing playlist with name: '{playlist_name}'.")
        page_token = None
        page = 1
        while True:
            response = (
                self.service.playlists()
                .list(part="snippet", mine=True, maxResults=50, pageToken=page_token)
                .execute()
            )
            logging.info(
                f"Processing page {page} of playlists. Items found: {len(response.get('items', []))}."
            )
            for item in response.get("items", []):
                title = item["snippet"]["title"]
                logging.info(f"Found playlist: '{title}'.")
                if title.lower() == playlist_name.lower():
                    logging.info(f"Match found. Playlist ID: {item['id']}")
                    return item["id"]
            page_token = response.get("nextPageToken")
            if not page_token:
                break
            page += 1
        logging.info("No matching playlist found.")
        return None



    @cached(cache=_youtube_search_cache, key=lambda self, query: query)
    @retry(
        stop=stop_after_attempt(YOUTUBE_RETRY_ATTEMPTS),
        wait=wait_random_exponential(
            multiplier=YOUTUBE_RETRY_MULTIPLIER, max=YOUTUBE_RETRY_MAX
        ),
        retry=retry_if_exception(
            lambda e: isinstance(e, HttpError) and not _is_quota_exceeded(e)
        ),
        before_sleep=before_sleep_log(logging.getLogger(__name__), logging.WARNING),
    )
    def get_playlist_items(self, playlist_id: str) -> list:
        """
        Retrieves all video IDs currently in the specified playlist.
        Returns a list of video IDs.
        """
        logging.info(f"Retrieving videos from playlist ID: {playlist_id}")
        page_token = None
        video_ids = []
        page = 1
        while True:
            response = (
                self.service.playlistItems()
                .list(
                    part="snippet",
                    playlistId=playlist_id,
                    maxResults=50,
                    pageToken=page_token,
                )
                .execute()
            )
            items = response.get("items", [])
            logging.info(f"Page {page}: Retrieved {len(items)} items.")
            for idx, item in enumerate(items, start=1):
                resource = item["snippet"]["resourceId"]
                if resource["kind"] == "youtube#video":
                    video_ids.append(resource["videoId"])
                    logging.info(f"Page {page} - Video {idx}: {resource['videoId']}")
            page_token = response.get("nextPageToken")
            if not page_token:
                break
            page += 1
        logging.info(f"Total videos retrieved: {len(video_ids)}")
        return video_ids



    @cached(cache=_youtube_search_cache, key=lambda self, query: query)
    @retry(
        stop=stop_after_attempt(YOUTUBE_RETRY_ATTEMPTS),
        wait=wait_random_exponential(
            multiplier=YOUTUBE_RETRY_MULTIPLIER, max=YOUTUBE_RETRY_MAX
        ),
        retry=retry_if_exception(
            lambda e: isinstance(e, HttpError) and not _is_quota_exceeded(e)
        ),
        before_sleep=before_sleep_log(logging.getLogger(__name__), logging.WARNING),
    )
    def search_video(self, query: str):
        logging.info(
            f"Searching YouTube for query: '{query}' with one-by-one candidate evaluation."
        )
        page_token = None
        # Loop until a candidate meeting the Music criteria is found, or no more results are available.
        while True:
            request = self.service.search().list(
                part="snippet",
                q=query,
                type="video",
                maxResults=1,
                pageToken=page_token,
            )
            response = request.execute()
            items = response.get("items", [])
            if not items:
                logging.info("No more search results available.")
                break
            candidate = items[0]
            # Safely retrieve the candidate video ID
            video_id = candidate.get("id", {}).get("videoId")
            if not video_id:
                logging.warning(
                    "Candidate item missing 'videoId', skipping to next result."
                )
                page_token = response.get("nextPageToken")
                if not page_token:
                    logging.info("No further candidates available.")
                    break
                continue
            logging.info(f"Evaluating candidate video ID: {video_id}")
            # Retrieve detailed information for this candidate.
            details_request = self.service.videos().list(
                part="snippet,contentDetails,status", id=video_id
            )
            details_response = details_request.execute()
            detail_items = details_response.get("items", [])
            if detail_items:
                video_details = detail_items[0]
                category_id = video_details["snippet"].get("categoryId")
                logging.info(
                    f"Candidate video {video_id} has categoryId: {category_id}"
                )
                # Check if the candidate is in the Music category (typically categoryId "10")
                if category_id == "10":
                    logging.info(
                        f"Candidate video {video_id} accepted as a Music video."
                    )
                    return video_id
                else:
                    logging.info(
                        f"Candidate video {video_id} rejected (not in Music category)."
                    )
            # Move to next candidate if available.
            page_token = response.get("nextPageToken")
            if not page_token:
                logging.info(
                    "Reached end of search results without finding a valid Music video."
                )
                break
        return None



    @retry(
        stop=stop_after_attempt(YOUTUBE_RETRY_ATTEMPTS),
        wait=wait_random_exponential(
            multiplier=YOUTUBE_RETRY_MULTIPLIER, max=YOUTUBE_RETRY_MAX
        ),
        retry=retry_if_exception(
            lambda e: isinstance(e, HttpError) and not _is_quota_exceeded(e)
        ),
        before_sleep=before_sleep_log(logging.getLogger(__name__), logging.WARNING),
    )
    def create_playlist(self, title: str, description: str = ""):
        logging.info(
            f"Creating YouTube playlist: '{title}' with description: '{description}'"
        )
        request = self.service.playlists().insert(
            part="snippet,status",
            body={
                "snippet": {"title": title, "description": description},
                "status": {"privacyStatus": "private"},
            },
        )
        response = request.execute()
        playlist_id = response.get("id")
        logging.info(f"Playlist created with ID: {playlist_id}")
        return playlist_id



    @retry(
        stop=stop_after_attempt(YOUTUBE_RETRY_ATTEMPTS),
        wait=wait_random_exponential(
            multiplier=YOUTUBE_RETRY_MULTIPLIER, max=YOUTUBE_RETRY_MAX
        ),
        retry=retry_if_exception(
            lambda e: isinstance(e, HttpError) and not _is_quota_exceeded(e)
        ),
        before_sleep=before_sleep_log(logging.getLogger(__name__), logging.WARNING),
    )
    def add_video_to_playlist(self, playlist_id: str, video_id: str):
        logging.info(f"Adding video ID: {video_id} to playlist ID: {playlist_id}")
        request = self.service.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {"kind": "youtube#video", "videoId": video_id},
                }
            },
        )
        response = request.execute()
        logging.info(f"Video {video_id} added to playlist {playlist_id} successfully.")
        return response


if __name__ == "__main__":
    # Regenerate the YouTube API credentials and save token.pickle
    client = YouTubeClient()
    print("New token.pickle generated successfully.")