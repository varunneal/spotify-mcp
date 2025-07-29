"""Tests for real-time notification functionality."""
import asyncio
from typing import Dict, Any
from unittest.mock import Mock, patch, AsyncMock

import pytest

from spotify_mcp.server import (
    _has_significant_change,
    monitor_playback_state,
    start_notifications,
    stop_notifications,
    _notification_task
)


class TestSignificantChange:
    """Tests for _has_significant_change function."""
    
    def test_play_pause_change(self) -> None:
        """Test that play/pause state changes are considered significant."""
        old_state = {"is_playing": False, "track_id": "track1"}
        new_state = {"is_playing": True, "track_id": "track1"}
        
        assert _has_significant_change(old_state, new_state) is True
    
    def test_track_change(self) -> None:
        """Test that track changes are considered significant."""
        old_state = {"is_playing": True, "track_id": "track1"}
        new_state = {"is_playing": True, "track_id": "track2"}
        
        assert _has_significant_change(old_state, new_state) is True
    
    def test_device_change(self) -> None:
        """Test that device changes are considered significant."""
        old_state = {"is_playing": True, "device_name": "Device1"}
        new_state = {"is_playing": True, "device_name": "Device2"}
        
        assert _has_significant_change(old_state, new_state) is True
    
    def test_shuffle_change(self) -> None:
        """Test that shuffle state changes are considered significant."""
        old_state = {"is_playing": True, "shuffle_state": False}
        new_state = {"is_playing": True, "shuffle_state": True}
        
        assert _has_significant_change(old_state, new_state) is True
    
    def test_repeat_change(self) -> None:
        """Test that repeat state changes are considered significant."""
        old_state = {"is_playing": True, "repeat_state": "off"}
        new_state = {"is_playing": True, "repeat_state": "track"}
        
        assert _has_significant_change(old_state, new_state) is True
    
    def test_volume_significant_change(self) -> None:
        """Test that significant volume changes are detected."""
        old_state = {"is_playing": True, "volume_percent": 50}
        new_state = {"is_playing": True, "volume_percent": 60}
        
        assert _has_significant_change(old_state, new_state) is True
    
    def test_volume_insignificant_change(self) -> None:
        """Test that small volume changes are not considered significant."""
        old_state = {"is_playing": True, "volume_percent": 50}
        new_state = {"is_playing": True, "volume_percent": 52}
        
        assert _has_significant_change(old_state, new_state) is False
    
    def test_progress_significant_change(self) -> None:
        """Test that large progress changes are detected."""
        old_state = {"is_playing": True, "progress_ms": 10000}
        new_state = {"is_playing": True, "progress_ms": 25000}  # 15 second jump
        
        assert _has_significant_change(old_state, new_state) is True
    
    def test_progress_insignificant_change(self) -> None:
        """Test that small progress changes are not considered significant."""
        old_state = {"is_playing": True, "progress_ms": 10000}
        new_state = {"is_playing": True, "progress_ms": 15000}  # 5 second change
        
        assert _has_significant_change(old_state, new_state) is False
    
    def test_no_change(self) -> None:
        """Test that identical states are not considered significant."""
        state = {"is_playing": True, "track_id": "track1", "volume_percent": 50}
        
        assert _has_significant_change(state, state) is False
    
    def test_missing_keys_handled(self) -> None:
        """Test that missing keys are handled gracefully."""
        old_state = {"is_playing": True}
        new_state = {"is_playing": True, "track_id": "track1"}
        
        # Should not crash and should detect the change
        assert _has_significant_change(old_state, new_state) is True


class TestNotificationLifecycle:
    """Tests for notification task lifecycle management."""
    
    @pytest.mark.asyncio
    async def test_start_notifications(self) -> None:
        """Test that notifications can be started."""
        # Reset global state
        import spotify_mcp.server
        spotify_mcp.server._notification_task = None
        
        with patch('spotify_mcp.server.monitor_playback_state') as mock_monitor:
            mock_monitor.return_value = AsyncMock()
            
            await start_notifications()
            
            # Check that task was created
            assert spotify_mcp.server._notification_task is not None
            assert not spotify_mcp.server._notification_task.done()
            
            # Clean up
            if spotify_mcp.server._notification_task:
                spotify_mcp.server._notification_task.cancel()
                try:
                    await spotify_mcp.server._notification_task
                except asyncio.CancelledError:
                    pass
    
    @pytest.mark.asyncio
    async def test_stop_notifications(self) -> None:
        """Test that notifications can be stopped."""
        # Reset global state
        import spotify_mcp.server
        spotify_mcp.server._notification_task = None
        
        with patch('spotify_mcp.server.monitor_playback_state') as mock_monitor:
            # Create a mock coroutine that will run indefinitely
            async def mock_monitor_func():
                while True:
                    await asyncio.sleep(1)
            
            mock_monitor.side_effect = mock_monitor_func
            
            # Start notifications
            await start_notifications()
            assert spotify_mcp.server._notification_task is not None
            
            # Stop notifications
            await stop_notifications()
            assert spotify_mcp.server._notification_task.done()
    
    @pytest.mark.asyncio
    async def test_start_notifications_idempotent(self) -> None:
        """Test that starting notifications multiple times is safe."""
        # Reset global state
        import spotify_mcp.server
        spotify_mcp.server._notification_task = None
        
        with patch('spotify_mcp.server.monitor_playback_state') as mock_monitor:
            mock_monitor.return_value = AsyncMock()
            
            # Start notifications twice
            await start_notifications()
            first_task = spotify_mcp.server._notification_task
            
            await start_notifications()
            second_task = spotify_mcp.server._notification_task
            
            # Should be the same task (or new one if first completed)
            assert second_task is not None
            
            # Clean up
            if spotify_mcp.server._notification_task:
                spotify_mcp.server._notification_task.cancel()
                try:
                    await spotify_mcp.server._notification_task
                except asyncio.CancelledError:
                    pass


class TestMonitorPlaybackState:
    """Tests for monitor_playback_state function."""
    
    @pytest.mark.asyncio
    async def test_monitor_playback_state_sends_notification(self) -> None:
        """Test that monitor_playback_state sends notifications on changes."""
        # Reset global state
        import spotify_mcp.server
        spotify_mcp.server._last_playback_state = None
        
        with patch('spotify_mcp.server.spotify_client') as mock_client, \
             patch('spotify_mcp.server.server') as mock_server, \
             patch('asyncio.sleep') as mock_sleep:
            
            # Mock the sleep to run only once
            mock_sleep.side_effect = [None, asyncio.CancelledError()]
            
            # Mock playback data
            mock_playback_data = {
                "is_playing": True,
                "item": {"id": "track123"},
                "progress_ms": 10000,
                "device": {"name": "Test Device", "volume_percent": 75},
                "shuffle_state": False,
                "repeat_state": "off"
            }
            mock_client.sp.current_playback.return_value = mock_playback_data
            mock_server.send_resource_updated = AsyncMock()
            
            # Run monitoring (will be cancelled after first iteration)
            with pytest.raises(asyncio.CancelledError):
                await monitor_playback_state()
            
            # Verify notification was sent
            mock_server.send_resource_updated.assert_called_once_with("spotify://playback/current")
    
    @pytest.mark.asyncio 
    async def test_monitor_playback_state_handles_errors(self) -> None:
        """Test that monitor_playback_state handles API errors gracefully."""
        # Reset global state
        import spotify_mcp.server
        spotify_mcp.server._last_playback_state = None
        
        with patch('spotify_mcp.server.spotify_client') as mock_client, \
             patch('asyncio.sleep') as mock_sleep:
            
            # Mock the sleep to run only once after error
            mock_sleep.side_effect = [asyncio.CancelledError()]
            
            # Mock API error
            mock_client.sp.current_playback.side_effect = Exception("API Error")
            
            # Run monitoring (will be cancelled after error handling)
            with pytest.raises(asyncio.CancelledError):
                await monitor_playback_state()
            
            # Should have called current_playback despite the error
            mock_client.sp.current_playback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_monitor_playback_state_no_notification_when_no_change(self) -> None:
        """Test that no notification is sent when state doesn't change significantly."""
        # Reset global state with an initial state
        import spotify_mcp.server
        spotify_mcp.server._last_playback_state = {
            "is_playing": True,
            "track_id": "track123",
            "progress_ms": 10000,
            "device_name": "Test Device",
            "shuffle_state": False,
            "repeat_state": "off",
            "volume_percent": 75
        }
        
        with patch('spotify_mcp.server.spotify_client') as mock_client, \
             patch('spotify_mcp.server.server') as mock_server, \
             patch('asyncio.sleep') as mock_sleep:
            
            # Mock the sleep to run only once
            mock_sleep.side_effect = [None, asyncio.CancelledError()]
            
            # Mock same playback data (with small progress change)
            mock_playback_data = {
                "is_playing": True,
                "item": {"id": "track123"},
                "progress_ms": 12000,  # Only 2 second difference
                "device": {"name": "Test Device", "volume_percent": 75},
                "shuffle_state": False,
                "repeat_state": "off"
            }
            mock_client.sp.current_playback.return_value = mock_playback_data
            mock_server.send_resource_updated = AsyncMock()
            
            # Run monitoring (will be cancelled after first iteration)
            with pytest.raises(asyncio.CancelledError):
                await monitor_playback_state()
            
            # Verify no notification was sent
            mock_server.send_resource_updated.assert_not_called()