"""Pytest configuration and fixtures."""
import asyncio
import os
from typing import Dict, Any, Generator
from unittest.mock import Mock, MagicMock, patch

import pytest
from mcp.server import Server

# Test environment variables are now configured in pyproject.toml via pytest-env


@pytest.fixture
def mock_env_vars() -> Generator[None, None, None]:
    """Mock environment variables for testing."""
    original_env = os.environ.copy()
    
    test_env = {
        "SPOTIFY_CLIENT_ID": "test_client_id",
        "SPOTIFY_CLIENT_SECRET": "test_client_secret", 
        "SPOTIFY_REDIRECT_URI": "http://localhost:8888",
    }
    
    os.environ.update(test_env)
    
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(original_env)


@pytest.fixture
def mock_logger() -> Mock:
    """Mock logger for testing."""
    return Mock()


@pytest.fixture
def mock_spotify_client(mock_logger: Mock) -> Mock:
    """Mock Spotify client for testing."""
    with patch('spotify_mcp.spotify_api.Client') as mock_client_class:
        mock_client = Mock()
        mock_client.logger = mock_logger
        mock_client.sp = Mock()
        mock_client.auth_manager = Mock()
        mock_client.cache_handler = Mock()
        mock_client_class.return_value = mock_client
        return mock_client


@pytest.fixture(autouse=True)
def mock_spotify_client_initialization(mock_env_vars):
    """Auto-use fixture to mock spotify client initialization at module level."""
    with patch('spotify_mcp.spotify_api.Client') as mock_client_class:
        mock_client = Mock()
        mock_client.logger = Mock()
        mock_client.sp = Mock()
        mock_client.auth_manager = Mock()
        mock_client.cache_handler = Mock()
        mock_client_class.return_value = mock_client
        yield mock_client


@pytest.fixture
def sample_track_data() -> Dict[str, Any]:
    """Sample track data for testing."""
    return {
        "id": "4iV5W9uYEdYUVa79Axb7Rh",
        "name": "Test Song",
        "artists": [{"name": "Test Artist", "id": "test_artist_id"}],
        "album": {
            "name": "Test Album",
            "id": "test_album_id",
            "artists": [{"name": "Test Artist", "id": "test_artist_id"}]
        },
        "duration_ms": 240000,
        "track_number": 1,
        "is_playable": True
    }


@pytest.fixture
def sample_playlist_data() -> Dict[str, Any]:
    """Sample playlist data for testing."""
    return {
        "id": "test_playlist_id",
        "name": "Test Playlist",
        "owner": {"display_name": "Test User"},
        "description": "A test playlist",
        "tracks": {
            "items": [
                {
                    "track": {
                        "id": "4iV5W9uYEdYUVa79Axb7Rh",
                        "name": "Test Song",
                        "artists": [{"name": "Test Artist", "id": "test_artist_id"}]
                    }
                }
            ]
        }
    }