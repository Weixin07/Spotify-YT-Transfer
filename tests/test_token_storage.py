"""Tests for secure token storage using OS keyring."""

import json
from pathlib import Path
from unittest.mock import MagicMock, Mock, mock_open, patch

import pytest

from spotify_yt_transfer.core.token_storage import (
    KeyringCacheHandler,
    YouTubeTokenStorage,
    clear_all_tokens,
)


class TestKeyringCacheHandler:
    """Test Spotify keyring cache handler."""

    @patch("spotify_yt_transfer.core.token_storage.keyring")
    def test_get_cached_token_returns_token_when_exists(self, mock_keyring):
        """Test retrieving existing token from keyring."""
        token_data = {"access_token": "abc123", "refresh_token": "xyz789"}
        mock_keyring.get_password.return_value = json.dumps(token_data)

        handler = KeyringCacheHandler(username="testuser")
        result = handler.get_cached_token()

        assert result == token_data
        mock_keyring.get_password.assert_called_once_with(
            "spotify_yt_transfer", "spotify_token_testuser"
        )

    @patch("spotify_yt_transfer.core.token_storage.keyring")
    def test_get_cached_token_returns_none_when_not_exists(self, mock_keyring):
        """Test returning None when no token in keyring."""
        mock_keyring.get_password.return_value = None

        handler = KeyringCacheHandler(username="testuser")
        result = handler.get_cached_token()

        assert result is None

    @patch("spotify_yt_transfer.core.token_storage.keyring")
    def test_save_token_to_cache_stores_in_keyring(self, mock_keyring):
        """Test saving token to keyring."""
        token_data = {"access_token": "new_token", "refresh_token": "refresh"}
        handler = KeyringCacheHandler(username="testuser")

        with patch.object(Path, "exists", return_value=False):
            handler.save_token_to_cache(token_data)

        mock_keyring.set_password.assert_called_once_with(
            "spotify_yt_transfer", "spotify_token_testuser", json.dumps(token_data)
        )

    @patch("spotify_yt_transfer.core.token_storage.keyring")
    def test_save_token_removes_legacy_cache_file(self, mock_keyring):
        """Test that legacy cache file is removed after saving to keyring."""
        token_data = {"access_token": "token"}
        handler = KeyringCacheHandler(username="testuser", cache_path=".cache")

        mock_path = MagicMock()
        mock_path.exists.return_value = True
        handler.cache_path = mock_path

        handler.save_token_to_cache(token_data)

        mock_path.unlink.assert_called_once()

    @patch("spotify_yt_transfer.core.token_storage.keyring")
    def test_migrate_from_file_moves_token_to_keyring(self, mock_keyring):
        """Test migration of legacy cache file to keyring."""
        token_data = {"access_token": "old_token", "refresh_token": "old_refresh"}

        # Create a mock path that simulates file existence
        mock_cache_path = MagicMock()
        mock_cache_path.exists.return_value = True
        mock_cache_path.open.return_value.__enter__.return_value.read.return_value = json.dumps(
            token_data
        )

        with patch.object(Path, "__new__", return_value=mock_cache_path):
            handler = KeyringCacheHandler(username="testuser", cache_path=".cache")

            # Verify migration was attempted (save was called)
            assert mock_keyring.set_password.call_count >= 1
            # Verify file deletion was attempted
            mock_cache_path.unlink.assert_called()

    @patch("spotify_yt_transfer.core.token_storage.keyring")
    def test_save_none_token_logs_warning(self, mock_keyring):
        """Test that saving None token does not crash."""
        handler = KeyringCacheHandler(username="testuser")
        handler.save_token_to_cache(None)

        # Should not call keyring
        mock_keyring.set_password.assert_not_called()


class TestYouTubeTokenStorage:
    """Test YouTube keyring token storage."""

    @patch("spotify_yt_transfer.core.token_storage.keyring")
    def test_get_credentials_returns_credentials_when_exists(self, mock_keyring):
        """Test retrieving existing YouTube credentials from keyring."""
        creds_dict = {
            "token": "access_token",
            "refresh_token": "refresh_token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "client_id",
            "client_secret": "client_secret",
            "scopes": ["https://www.googleapis.com/auth/youtube.force-ssl"],
            "expiry": "2025-01-01T00:00:00",
        }
        mock_keyring.get_password.return_value = json.dumps(creds_dict)

        storage = YouTubeTokenStorage(username="testuser")
        result = storage.get_credentials()

        assert result is not None
        assert result.token == "access_token"
        assert result.refresh_token == "refresh_token"

    @patch("spotify_yt_transfer.core.token_storage.keyring")
    def test_get_credentials_returns_none_when_not_exists(self, mock_keyring):
        """Test returning None when no credentials in keyring."""
        mock_keyring.get_password.return_value = None

        storage = YouTubeTokenStorage(username="testuser")
        result = storage.get_credentials()

        assert result is None

    @patch("spotify_yt_transfer.core.token_storage.keyring")
    def test_save_credentials_stores_in_keyring(self, mock_keyring):
        """Test saving YouTube credentials to keyring."""
        mock_creds = MagicMock()
        mock_creds.token = "access_token"
        mock_creds.refresh_token = "refresh_token"
        mock_creds.token_uri = "https://oauth2.googleapis.com/token"
        mock_creds.client_id = "client_id"
        mock_creds.client_secret = "client_secret"
        mock_creds.scopes = ["scope1"]
        mock_creds.expiry = None

        storage = YouTubeTokenStorage(username="testuser")

        with patch.object(Path, "exists", return_value=False):
            storage.save_credentials(mock_creds)

        mock_keyring.set_password.assert_called_once()
        # Verify the call contains the serialized credentials
        call_args = mock_keyring.set_password.call_args
        assert call_args[0][0] == "spotify_yt_transfer"
        assert call_args[0][1] == "youtube_token_testuser"
        creds_json = call_args[0][2]
        creds_dict = json.loads(creds_json)
        assert creds_dict["token"] == "access_token"

    @patch("spotify_yt_transfer.core.token_storage.keyring")
    def test_save_credentials_removes_legacy_pickle_file(self, mock_keyring):
        """Test that legacy pickle file is removed after saving to keyring."""
        mock_creds = MagicMock()
        mock_creds.token = "token"
        mock_creds.refresh_token = None
        mock_creds.token_uri = "uri"
        mock_creds.client_id = "id"
        mock_creds.client_secret = "secret"
        mock_creds.scopes = []
        mock_creds.expiry = None

        storage = YouTubeTokenStorage(username="testuser", token_path="token.pickle")

        mock_path = MagicMock()
        mock_path.exists.return_value = True
        storage.token_path = mock_path

        storage.save_credentials(mock_creds)

        mock_path.unlink.assert_called_once()

    @patch("spotify_yt_transfer.core.token_storage.keyring")
    @patch("spotify_yt_transfer.core.token_storage.pickle")
    def test_migrate_from_pickle_moves_credentials_to_keyring(self, mock_pickle, mock_keyring):
        """Test migration of legacy pickle file to keyring."""
        mock_creds = MagicMock()
        mock_creds.token = "old_token"
        mock_creds.refresh_token = "old_refresh"
        mock_creds.token_uri = "uri"
        mock_creds.client_id = "id"
        mock_creds.client_secret = "secret"
        mock_creds.scopes = []
        mock_creds.expiry = None
        mock_pickle.load.return_value = mock_creds

        # Create a mock path that simulates pickle file existence
        mock_token_path = MagicMock()
        mock_token_path.exists.return_value = True

        with patch.object(Path, "__new__", return_value=mock_token_path):
            with patch("builtins.open", mock_open()):
                storage = YouTubeTokenStorage(username="testuser", token_path="token.pickle")

                # Verify migration was attempted (save was called)
                assert mock_keyring.set_password.call_count >= 1
                # Verify file deletion was attempted
                mock_token_path.unlink.assert_called()


class TestClearAllTokens:
    """Test clearing all tokens from keyring."""

    @patch("spotify_yt_transfer.core.token_storage.keyring")
    def test_clear_all_tokens_removes_both_tokens(self, mock_keyring):
        """Test that both Spotify and YouTube tokens are cleared."""
        clear_all_tokens(username="testuser")

        assert mock_keyring.delete_password.call_count == 2
        mock_keyring.delete_password.assert_any_call(
            "spotify_yt_transfer", "spotify_token_testuser"
        )
        mock_keyring.delete_password.assert_any_call(
            "spotify_yt_transfer", "youtube_token_testuser"
        )

    @patch("spotify_yt_transfer.core.token_storage.keyring")
    def test_clear_all_tokens_handles_missing_tokens(self, mock_keyring):
        """Test that clearing non-existent tokens doesn't crash."""
        # Mock the PasswordDeleteError
        password_delete_error = type('PasswordDeleteError', (Exception,), {})
        mock_keyring.errors.PasswordDeleteError = password_delete_error
        mock_keyring.delete_password.side_effect = password_delete_error()

        # Should not raise exception
        clear_all_tokens(username="testuser")
