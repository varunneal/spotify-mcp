"""Tests for MCP resources functionality."""
import json
from typing import Dict, Any
from unittest.mock import Mock, patch

import pytest
import mcp.types as types

from spotify_mcp.server import handle_list_resources, handle_read_resource


class TestListResources:
    """Tests for handle_list_resources function."""
    
    @pytest.mark.asyncio
    async def test_handle_list_resources(self) -> None:
        """Test that handle_list_resources returns expected resources."""
        resources = await handle_list_resources()
        
        assert len(resources) == 4
        resource_uris = [str(resource.uri) for resource in resources]
        
        expected_uris = [
            "spotify://user/current",
            "spotify://playback/current", 
            "spotify://devices/available",
            "spotify://queue/current"
        ]
        
        for expected_uri in expected_uris:
            assert expected_uri in resource_uris
        
        # Check that all resources have proper structure
        for resource in resources:
            assert isinstance(resource, types.Resource)
            assert resource.name
            assert resource.description
            assert resource.mimeType == "application/json"


class TestReadResource:
    """Tests for handle_read_resource function."""
    
    @pytest.mark.asyncio
    @patch('spotify_mcp.server.spotify_client')
    async def test_read_user_current(self, mock_client: Mock) -> None:
        """Test reading current user resource."""
        # Mock user data
        mock_user_data = {
            "id": "test_user",
            "display_name": "Test User",
            "email": "test@example.com",
            "country": "US",
            "product": "premium",
            "followers": {"total": 100},
            "images": [{"url": "http://example.com/image.jpg"}]
        }
        mock_client.sp.current_user.return_value = mock_user_data
        
        result = await handle_read_resource("spotify://user/current")
        
        # Parse the JSON response
        parsed_result = json.loads(result)
        
        assert parsed_result["id"] == "test_user"
        assert parsed_result["display_name"] == "Test User"
        assert parsed_result["email"] == "test@example.com"
        assert parsed_result["followers"] == 100
        
        mock_client.sp.current_user.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('spotify_mcp.server.spotify_client')
    async def test_read_user_current_error(self, mock_client: Mock) -> None:
        """Test reading current user resource when API fails."""
        mock_client.sp.current_user.return_value = None
        
        result = await handle_read_resource("spotify://user/current")
        parsed_result = json.loads(result)
        
        assert "error" in parsed_result
        assert parsed_result["error"] == "Unable to fetch user information"
    
    @pytest.mark.asyncio
    @patch('spotify_mcp.server.spotify_client')
    async def test_read_playback_current(self, mock_client: Mock) -> None:
        """Test reading current playback resource."""
        # Mock playback data
        mock_playback_data = {
            "is_playing": True,
            "progress_ms": 120000,
            "device": {
                "name": "Test Device",
                "type": "Computer",
                "is_active": True,
                "volume_percent": 75
            },
            "shuffle_state": False,
            "repeat_state": "off"
        }
        mock_client.sp.current_playback.return_value = mock_playback_data
        mock_client.get_current_track.return_value = {
            "name": "Test Song",
            "artist": "Test Artist"
        }
        
        result = await handle_read_resource("spotify://playback/current")
        parsed_result = json.loads(result)
        
        assert parsed_result["is_playing"] is True
        assert parsed_result["progress_ms"] == 120000
        assert parsed_result["device"]["name"] == "Test Device"
        assert parsed_result["current_track"]["name"] == "Test Song"
        assert parsed_result["shuffle_state"] is False
        
        mock_client.sp.current_playback.assert_called_once()
        mock_client.get_current_track.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('spotify_mcp.server.spotify_client')
    async def test_read_playback_current_no_playback(self, mock_client: Mock) -> None:
        """Test reading current playback when nothing is playing."""
        mock_client.sp.current_playback.return_value = None
        
        result = await handle_read_resource("spotify://playback/current")
        parsed_result = json.loads(result)
        
        assert parsed_result["is_playing"] is False
        assert parsed_result["current_track"] is None
    
    @pytest.mark.asyncio
    @patch('spotify_mcp.server.spotify_client')
    async def test_read_devices_available(self, mock_client: Mock) -> None:
        """Test reading available devices resource."""
        mock_devices = [
            {"name": "Device 1", "type": "Computer", "is_active": True},
            {"name": "Device 2", "type": "Smartphone", "is_active": False}
        ]
        mock_client.get_devices.return_value = mock_devices
        
        result = await handle_read_resource("spotify://devices/available")
        parsed_result = json.loads(result)
        
        assert "devices" in parsed_result
        assert len(parsed_result["devices"]) == 2
        assert parsed_result["devices"][0]["name"] == "Device 1"
        
        mock_client.get_devices.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('spotify_mcp.server.spotify_client')
    async def test_read_queue_current(self, mock_client: Mock) -> None:
        """Test reading current queue resource."""
        mock_queue = {
            "currently_playing": {"name": "Current Song"},
            "queue": [
                {"name": "Next Song 1"},
                {"name": "Next Song 2"}
            ]
        }
        mock_client.get_queue.return_value = mock_queue
        
        result = await handle_read_resource("spotify://queue/current")
        parsed_result = json.loads(result)
        
        assert parsed_result["currently_playing"]["name"] == "Current Song"
        assert len(parsed_result["queue"]) == 2
        
        mock_client.get_queue.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_read_unknown_resource(self) -> None:
        """Test reading an unknown resource URI."""
        result = await handle_read_resource("spotify://unknown/resource")
        parsed_result = json.loads(result)
        
        assert "error" in parsed_result
        assert "Unknown resource" in parsed_result["error"]
    
    @pytest.mark.asyncio
    @patch('spotify_mcp.server.spotify_client')
    async def test_read_resource_exception(self, mock_client: Mock) -> None:
        """Test handling exceptions during resource reading."""
        mock_client.sp.current_user.side_effect = Exception("API Error")
        
        result = await handle_read_resource("spotify://user/current")
        parsed_result = json.loads(result)
        
        assert "error" in parsed_result
        assert "Error reading resource" in parsed_result["error"]