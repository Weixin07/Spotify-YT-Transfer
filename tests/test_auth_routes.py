from contextlib import contextmanager

from fastapi.testclient import TestClient

from spotify_yt_transfer.api import dependencies
from spotify_yt_transfer.main import app
from spotify_yt_transfer.services import OAuthAuthorizeResponse, OAuthStateError


@contextmanager
def override_oauth_service(service):
    app.dependency_overrides[dependencies.get_oauth_service] = lambda: service
    try:
        yield
    finally:
        app.dependency_overrides.pop(dependencies.get_oauth_service, None)


def test_spotify_authorize_returns_url_and_state():
    class StubService:
        def build_spotify_authorize_url(self):
            return OAuthAuthorizeResponse("https://spotify.example/auth", "state123")

    with override_oauth_service(StubService()):
        with TestClient(app) as client:
            response = client.get("/v1/spotify/authorize")

    assert response.status_code == 200
    payload = response.json()
    assert payload["authorize_url"] == "https://spotify.example/auth"
    assert payload["state"] == "state123"


def test_spotify_callback_rejects_invalid_state():
    class StubService:
        def build_spotify_authorize_url(self):
            return OAuthAuthorizeResponse("https://spotify.example/auth", "state123")

        def exchange_spotify_code(self, code, state):
            raise OAuthStateError("Invalid or expired OAuth state")

    with override_oauth_service(StubService()):
        with TestClient(app) as client:
            response = client.get("/v1/spotify/callback", params={"code": "abc", "state": "foo"})

    assert response.status_code == 400


def test_spotify_callback_success_returns_token_info():
    class StubService:
        def build_spotify_authorize_url(self):
            return OAuthAuthorizeResponse("https://spotify.example/auth", "state123")

        def exchange_spotify_code(self, code, state):
            assert code == "abc"
            assert state == "state123"
            return {"access_token": "token", "expires_in": 3600}

    with override_oauth_service(StubService()):
        with TestClient(app) as client:
            response = client.get(
                "/v1/spotify/callback", params={"code": "abc", "state": "state123"}
            )

    assert response.status_code == 200
    # SECURITY: Tokens should NOT be in response, only confirmation message
    payload = response.json()
    assert "message" in payload
    assert "Spotify authentication successful" in payload["message"]
    assert "expires_in" in payload
    # Ensure tokens are NOT exposed in response
    assert "token_info" not in payload
    assert "access_token" not in payload


def test_youtube_authorize_returns_url_and_state():
    class StubService:
        def build_youtube_authorize_url(self):
            return OAuthAuthorizeResponse("https://youtube.example/auth", "state456")

    with override_oauth_service(StubService()):
        with TestClient(app) as client:
            response = client.get("/v1/youtube/authorize")

    assert response.status_code == 200
    payload = response.json()
    assert payload["authorize_url"] == "https://youtube.example/auth"
    assert payload["state"] == "state456"


def test_youtube_callback_success_returns_credentials():
    class StubService:
        def build_youtube_authorize_url(self):
            return OAuthAuthorizeResponse("https://youtube.example/auth", "state456")

        def exchange_youtube_code(self, code, state):
            return {
                "token": "yt-token",
                "refresh_token": "refresh",
                "scopes": ["https://www.googleapis.com/auth/youtube.force-ssl"],
            }

    with override_oauth_service(StubService()):
        with TestClient(app) as client:
            response = client.get(
                "/v1/youtube/callback", params={"code": "def", "state": "state456"}
            )

    assert response.status_code == 200
    # SECURITY: Tokens should NOT be in response, only confirmation and scopes
    payload = response.json()
    assert "message" in payload
    assert "YouTube authentication successful" in payload["message"]
    assert "scopes" in payload
    assert "https://www.googleapis.com/auth/youtube.force-ssl" in payload["scopes"]
    # Ensure tokens are NOT exposed in response
    assert "credentials" not in payload
    assert "token" not in payload
    assert "refresh_token" not in payload
