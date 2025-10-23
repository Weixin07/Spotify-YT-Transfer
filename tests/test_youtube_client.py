from unittest.mock import MagicMock, patch

from spotify_yt_transfer.clients.youtube_client import YouTubeClient


def test_youtube_client_init():
    """Test YouTube client initialization with keyring storage."""
    # Mock credentials
    mock_cred = MagicMock()
    mock_cred.valid = True
    mock_cred.expired = False

    # Mock the YouTube service
    mock_service = MagicMock()

    with patch("spotify_yt_transfer.clients.youtube_client.YouTubeTokenStorage") as mock_storage_class:
        with patch("spotify_yt_transfer.clients.youtube_client.build", return_value=mock_service):
            # Setup mock storage instance
            mock_storage = MagicMock()
            mock_storage.get_credentials.return_value = mock_cred
            mock_storage_class.return_value = mock_storage

            # Initialize client
            client = YouTubeClient()

            # Verify client is properly initialized
            assert client.service is not None
            assert client.service == mock_service
            assert client.creds == mock_cred

            # Verify storage was used
            mock_storage.get_credentials.assert_called_once()
