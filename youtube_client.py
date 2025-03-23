import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from config import YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REDIRECT_URI

# If modifying these scopes, delete the file token.pickle.
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]


class YouTubeClient:
    def __init__(self):
        self.creds = None
        self.service = self.authenticate()

    def authenticate(self):
        # Token file stores the user's credentials
        if os.path.exists("token.pickle"):
            with open("token.pickle", "rb") as token:
                self.creds = pickle.load(token)
        # If no valid credentials, let the user log in.
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
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
                self.creds = flow.run_local_server(port=8001)
            # Save the credentials for the next run
            with open("token.pickle", "wb") as token:
                pickle.dump(self.creds, token)
        return build("youtube", "v3", credentials=self.creds)

    def search_video(self, query: str):
        request = self.service.search().list(
            part="snippet", q=query, type="video", maxResults=1
        )
        response = request.execute()
        items = response.get("items", [])
        if items:
            video_id = items[0]["id"]["videoId"]
            return video_id
        return None

    def create_playlist(self, title: str, description: str = ""):
        request = self.service.playlists().insert(
            part="snippet,status",
            body={
                "snippet": {"title": title, "description": description},
                "status": {"privacyStatus": "private"},
            },
        )
        response = request.execute()
        return response.get("id")

    def add_video_to_playlist(self, playlist_id: str, video_id: str):
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
        return response
