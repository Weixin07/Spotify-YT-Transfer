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
            return {"access_token": "token"}

    with override_oauth_service(StubService()):
        with TestClient(app) as client:
            response = client.get("/v1/spotify/callback", params={"code": "abc", "state": "state123"})

    assert response.status_code == 200
    assert response.json()["token_info"]["access_token"] == "token"


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
            return {"token": "yt-token"}

    with override_oauth_service(StubService()):
        with TestClient(app) as client:
            response = client.get("/v1/youtube/callback", params={"code": "def", "state": "state456"})

    assert response.status_code == 200
    assert response.json()["credentials"]["token"] == "yt-token"
