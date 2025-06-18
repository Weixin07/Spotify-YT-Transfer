# Spotify-YT-Transfer

## Overview

A utility service to migrate Spotify playlists into YouTube Music playlists, handling OAuth, track matching, and cover images.

## Architecture

1. **FastAPI app** (`main.py`):
   - Defines HTTP endpoints for migration and cover download.
   - Manages application lifespan (DB init, client singletons).
2. **Clients**:
   - **SpotifyClient** (`spotify_client.py`): OAuth2 with Spotify, fetch playlists/liked tracks.
   - **YouTubeClient** (`youtube_client.py`): OAuth2 with Google, search videos, create/add to playlists.
3. **Track matching** (`track_matcher.py`): Fuzzy matching logic between Spotify track metadata and YouTube search results.
4. **Data storage** (`data_storage.py` + SQLite): Cache migrated tracks and failures in `matched_tracks.db`.
5. **Utilities**:
   - **download_cover.py**: Retrieve and serve a Spotify playlist’s cover image.
   - **check_missing.py**: Identify tracks that failed migration for retry.

## Installation

```bash
$ pip install -r requirements.txt
```

## Start service

```bash
$ uvicorn main:app --reload --port 8001
```

## API Documentation

Swagger UI: http://localhost:8001/docs
ReDoc: http://localhost:8001/redoc

## Monitor API Status

### Youtube

https://console.cloud.google.com/apis/api/youtube.googleapis.com/quotas?project=spotify-youtube--1741616053505

## Testing

```bash
$ pytest -q
```
