"""Tests for spotify_mcp.server module."""
from typing import Dict, Any
from unittest.mock import Mock, patch

import pytest
import mcp.types as types

from spotify_mcp.server import (
    handle_list_tools,
    handle_call_tool,
    Playback,
    Search,
    Queue,
    GetInfo
)


class TestToolModels:
    """Tests for MCP tool model definitions."""
    
    def test_playback_tool_schema(self) -> None:
        """Test Playback tool schema generation."""
        tool = Playback.as_tool()
        
        assert tool.name == "SpotifyPlayback"
        assert "action" in tool.inputSchema["properties"]
        assert "track_id" in tool.inputSchema["properties"]
        assert "num_skips" in tool.inputSchema["properties"]
    
    def test_search_tool_schema(self) -> None:
        """Test Search tool schema generation."""
        tool = Search.as_tool()
        
        assert tool.name == "SpotifySearch"
        assert "query" in tool.inputSchema["properties"]
        assert "qtype" in tool.inputSchema["properties"]
        assert "limit" in tool.inputSchema["properties"]
    
    def test_queue_tool_schema(self) -> None:
        """Test Queue tool schema generation."""
        tool = Queue.as_tool()
        
        assert tool.name == "SpotifyQueue"
        assert "action" in tool.inputSchema["properties"]
        assert "track_id" in tool.inputSchema["properties"]
    
    def test_get_info_tool_schema(self) -> None:
        """Test GetInfo tool schema generation."""
        tool = GetInfo.as_tool()
        
        assert tool.name == "SpotifyGetInfo"
        assert "item_id" in tool.inputSchema["properties"]
        assert "qtype" in tool.inputSchema["properties"]


class TestListTools:
    """Tests for handle_list_tools function."""
    
    @pytest.mark.asyncio
    async def test_handle_list_tools(self) -> None:
        """Test that handle_list_tools returns expected tools."""
        tools = await handle_list_tools()
        
        assert len(tools) == 8  # Current number of tools
        tool_names = [tool.name for tool in tools]
        
        expected_tools = [
            "SpotifyPlayback",
            "SpotifySearch", 
            "SpotifyQueue",
            "SpotifyGetInfo",
            "SpotifyPlaylistManage",
            "SpotifyPlaylistItems",
            "SpotifyUserPlaylists",
            "SpotifyPlaylistCover"
        ]
        
        for expected_tool in expected_tools:
            assert expected_tool in tool_names


class TestCallTool:
    """Tests for handle_call_tool function."""
    
    @pytest.mark.asyncio
    async def test_handle_call_tool_invalid_name(self) -> None:
        """Test handle_call_tool with invalid tool name."""
        with pytest.raises(AssertionError, match="Unknown tool"):
            await handle_call_tool("InvalidTool", {})
    
    @pytest.mark.asyncio
    @patch('spotify_mcp.server.spotify_client')
    async def test_handle_call_tool_playback_get(self, mock_client: Mock) -> None:
        """Test handle_call_tool for playback get action."""
        # Mock the client to return current track info
        mock_client.get_current_track.return_value = {
            "name": "Test Song",
            "artist": "Test Artist"
        }
        
        result = await handle_call_tool("SpotifyPlayback", {"action": "get"})
        
        assert len(result) == 1
        assert isinstance(result[0], types.TextContent)
        assert "Test Song" in result[0].text
    
    @pytest.mark.asyncio
    @patch('spotify_mcp.server.spotify_client')
    async def test_handle_call_tool_playback_no_track(self, mock_client: Mock) -> None:
        """Test handle_call_tool when no track is playing."""
        mock_client.get_current_track.return_value = None
        
        result = await handle_call_tool("SpotifyPlayback", {"action": "get"})
        
        assert len(result) == 1
        assert isinstance(result[0], types.TextContent)
        assert "No track playing" in result[0].text
    
    @pytest.mark.asyncio
    @patch('spotify_mcp.server.spotify_client')
    async def test_handle_call_tool_search(self, mock_client: Mock) -> None:
        """Test handle_call_tool for search action."""
        mock_client.search.return_value = {
            "tracks": [{"name": "Test Song", "artist": "Test Artist"}]
        }
        
        result = await handle_call_tool("SpotifySearch", {"query": "test song"})
        
        assert len(result) == 1
        assert isinstance(result[0], types.TextContent)
        mock_client.search.assert_called_once_with(
            query="test song",
            qtype="track", 
            limit=10
        )
    
    @pytest.mark.asyncio
    async def test_handle_call_tool_search_no_query(self) -> None:
        """Test handle_call_tool for search without query."""
        result = await handle_call_tool("SpotifySearch", {})
        
        assert len(result) == 1
        assert isinstance(result[0], types.TextContent)
        assert "query is required" in result[0].text
    
    @pytest.mark.asyncio
    @patch('spotify_mcp.server.spotify_client')
    async def test_handle_call_tool_queue_add(self, mock_client: Mock) -> None:
        """Test handle_call_tool for queue add action."""
        result = await handle_call_tool("SpotifyQueue", {
            "action": "add", 
            "track_id": "test_track_id"
        })
        
        assert len(result) == 1
        assert isinstance(result[0], types.TextContent)
        assert "Track added to queue" in result[0].text
        mock_client.add_to_queue.assert_called_once_with("test_track_id")
    
    @pytest.mark.asyncio
    async def test_handle_call_tool_queue_add_no_id(self) -> None:
        """Test handle_call_tool for queue add without track_id."""
        result = await handle_call_tool("SpotifyQueue", {"action": "add"})
        
        assert len(result) == 1
        assert isinstance(result[0], types.TextContent)
        assert "track_id is required" in result[0].text
    
    @pytest.mark.asyncio
    @patch('spotify_mcp.server.spotify_client')
    async def test_handle_call_tool_get_info(self, mock_client: Mock) -> None:
        """Test handle_call_tool for get info action."""
        mock_client.get_info.return_value = {
            "name": "Test Song",
            "artist": "Test Artist"
        }
        
        result = await handle_call_tool("SpotifyGetInfo", {"item_id": "test_id"})
        
        assert len(result) == 1
        assert isinstance(result[0], types.TextContent)
        mock_client.get_info.assert_called_once_with(
            item_id="test_id",
            qtype="track"
        )
    
    @pytest.mark.asyncio
    async def test_handle_call_tool_get_info_no_id(self) -> None:
        """Test handle_call_tool for get info without item_id."""
        result = await handle_call_tool("SpotifyGetInfo", {})
        
        assert len(result) == 1
        assert isinstance(result[0], types.TextContent)
        assert "item_id is required" in result[0].text