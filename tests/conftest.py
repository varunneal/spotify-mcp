"""
FastMCP test configuration and fixtures.
"""

import pytest
from unittest.mock import MagicMock, patch
from typing import Dict, Any

# Sample Spotify API response data for testing
SAMPLE_TRACK = {
    "id": "4iV5W9uYEdYUVa79Axb7Rh",
    "name": "Never Gonna Give You Up",
    "artists": [{"name": "Rick Astley", "id": "0gxyHStUsqpMadRV0Di1Qt"}],
    "album": {
        "name": "Whenever You Need Somebody",
        "id": "6XzKGcM6laRkTrME3rQvJw"
    },
    "duration_ms": 213573,
    "popularity": 85,
    "external_urls": {"spotify": "https://open.spotify.com/track/4iV5W9uYEdYUVa79Axb7Rh"}
}

SAMPLE_PLAYLIST = {
    "id": "37i9dQZF1DX0XUsuxWHRQd",
    "name": "RapCaviar",
    "description": "New music from hip-hop's underground",
    "owner": {"display_name": "Spotify", "id": "spotify"},
    "tracks": {"total": 50},
    "external_urls": {"spotify": "https://open.spotify.com/playlist/37i9dQZF1DX0XUsuxWHRQd"}
}

SAMPLE_PLAYBACK_STATE = {
    "is_playing": True,
    "item": SAMPLE_TRACK,
    "device": {"name": "My iPhone", "volume_percent": 70},
    "shuffle_state": False,
    "repeat_state": "off",
    "progress_ms": 60000
}

SAMPLE_SEARCH_RESULTS = {
    "tracks": {
        "items": [SAMPLE_TRACK],
        "total": 1
    },
    "albums": {"items": [], "total": 0},
    "artists": {"items": [], "total": 0},
    "playlists": {"items": [], "total": 0}
}


@pytest.fixture
def mock_spotify_client():
    """Create a mocked Spotify client for testing."""
    mock_client = MagicMock()
    
    # Mock common methods
    mock_client.current_playback.return_value = SAMPLE_PLAYBACK_STATE
    mock_client.search.return_value = SAMPLE_SEARCH_RESULTS
    mock_client.user_playlists.return_value = {"items": [SAMPLE_PLAYLIST]}
    mock_client.playlist.return_value = SAMPLE_PLAYLIST
    mock_client.track.return_value = SAMPLE_TRACK
    mock_client.playlist_add_items.return_value = {"snapshot_id": "test123"}
    mock_client.user_playlist_create.return_value = SAMPLE_PLAYLIST
    
    return mock_client


@pytest.fixture
def mock_spotify_api(mock_spotify_client):
    """Mock the spotify_api module."""
    with patch('spotify_mcp.fastmcp_server.spotify_client', mock_spotify_client):
        yield mock_spotify_client


@pytest.fixture
def sample_track_data():
    """Provide sample track data for tests."""
    return SAMPLE_TRACK


@pytest.fixture 
def sample_playlist_data():
    """Provide sample playlist data for tests."""
    return SAMPLE_PLAYLIST


@pytest.fixture
def sample_playback_data():
    """Provide sample playback state data for tests."""
    return SAMPLE_PLAYBACK_STATE


@pytest.fixture
def sample_search_results():
    """Provide sample search results for tests."""
    return SAMPLE_SEARCH_RESULTS