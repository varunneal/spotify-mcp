"""
Tests for error handling.
"""

import pytest
from spotipy import SpotifyException
from spotify_mcp.errors import convert_spotify_error, SpotifyMCPError, SpotifyMCPErrorCode


class TestSpotifyErrorHandling:
    """Test Spotify API error handling."""
    
    def test_handle_404_error(self):
        """Test handling 404 Not Found error."""
        error = SpotifyException(404, -1, "The requested resource could not be found.")
        
        result = convert_spotify_error(error)
        
        assert isinstance(result, ValueError)
        # Generic 404 goes to UNKNOWN_ERROR which includes the original message
        assert "could not be found" in str(result).lower()
    
    def test_handle_401_error(self):
        """Test handling 401 Unauthorized error."""
        error = SpotifyException(401, -1, "Invalid access token")
        
        result = convert_spotify_error(error)
        
        assert isinstance(result, ValueError)
        assert "authentication" in str(result).lower()
    
    def test_handle_401_token_expired_error(self):
        """Test handling 401 token expired error."""
        error = SpotifyException(401, -1, "The access token expired")
        
        result = convert_spotify_error(error)
        
        assert isinstance(result, ValueError)
        assert "token" in str(result).lower()
    
    def test_handle_403_error(self):
        """Test handling 403 Forbidden error."""
        error = SpotifyException(403, -1, "Insufficient client scope")
        
        result = convert_spotify_error(error)
        
        assert isinstance(result, ValueError)
        assert "permission" in str(result).lower()
    
    def test_handle_403_premium_error(self):
        """Test handling 403 Premium required error."""
        error = SpotifyException(403, -1, "Premium required")
        
        result = convert_spotify_error(error)
        
        assert isinstance(result, ValueError)
        assert "premium" in str(result).lower()
    
    def test_handle_429_rate_limit_error(self):
        """Test handling 429 Rate Limit error."""
        error = SpotifyException(429, -1, "Rate limit exceeded", headers={"Retry-After": "60"})
        
        result = convert_spotify_error(error)
        
        assert isinstance(result, ValueError)
        assert "rate limit" in str(result).lower()
    
    def test_handle_500_server_error(self):
        """Test handling 500 Internal Server Error."""
        error = SpotifyException(500, -1, "Internal server error")
        
        result = convert_spotify_error(error)
        
        assert isinstance(result, ValueError)
        assert "unavailable" in str(result).lower() or "api" in str(result).lower()
    
    def test_handle_generic_spotify_error(self):
        """Test handling generic Spotify error."""
        error = SpotifyException(418, -1, "I'm a teapot")
        
        result = convert_spotify_error(error)
        
        assert isinstance(result, ValueError)
        assert "teapot" in str(result).lower()
    
    def test_handle_non_spotify_exception(self):
        """Test handling non-Spotify exceptions."""
        error = ConnectionError("Network unreachable")
        
        result = convert_spotify_error(error)
        
        assert isinstance(result, ValueError)
        assert "network unreachable" in str(result).lower()
    
    def test_handle_spotify_mcp_error(self):
        """Test handling SpotifyMCPError directly."""
        error = SpotifyMCPError(
            SpotifyMCPErrorCode.NO_ACTIVE_DEVICE,
            "No active device found",
            suggestion="Open Spotify on a device"
        )
        
        result = convert_spotify_error(error)
        
        assert isinstance(result, ValueError)
        assert "no active device" in str(result).lower()
    
    def test_no_active_device_error(self):
        """Test handling device-related errors."""
        error = SpotifyException(404, -1, "No active device found")
        
        result = convert_spotify_error(error)
        
        assert isinstance(result, ValueError)
        # Could be caught by device error or 404 handling
        assert "device" in str(result).lower() or "not found" in str(result).lower()


class TestSpotifyMCPError:
    """Test SpotifyMCPError class functionality."""
    
    def test_create_basic_error(self):
        """Test creating a basic SpotifyMCPError."""
        error = SpotifyMCPError(
            SpotifyMCPErrorCode.TRACK_NOT_FOUND,
            "Track not found",
            {"track_id": "123"},
            "Check the track ID"
        )
        
        assert error.code == SpotifyMCPErrorCode.TRACK_NOT_FOUND
        assert error.message == "Track not found"
        assert error.details == {"track_id": "123"}
        assert error.suggestion == "Check the track ID"
    
    def test_validation_error_class_method(self):
        """Test validation error class method."""
        error = SpotifyMCPError.validation_error("track_id", "must be a valid Spotify ID")
        
        assert error.code == SpotifyMCPErrorCode.VALIDATION_ERROR
        assert "track_id" in error.message
        assert "must be a valid Spotify ID" in error.message
        assert error.details["field"] == "track_id"
    
    def test_no_active_device_class_method(self):
        """Test no active device class method."""
        error = SpotifyMCPError.no_active_device()
        
        assert error.code == SpotifyMCPErrorCode.NO_ACTIVE_DEVICE
        assert "device" in error.message.lower()
        assert "open spotify" in error.suggestion.lower()
    
    def test_premium_required_class_method(self):
        """Test premium required class method."""
        error = SpotifyMCPError.premium_required("playback control")
        
        assert error.code == SpotifyMCPErrorCode.PREMIUM_REQUIRED
        assert "premium" in error.message.lower()
        assert "playback control" in error.message
        assert error.details["operation"] == "playback control"
    
    def test_from_spotify_exception_404_track(self):
        """Test creating error from Spotify 404 track exception."""
        exc = SpotifyException(404, -1, "track not found")
        error = SpotifyMCPError.from_spotify_exception(exc)
        
        assert error.code == SpotifyMCPErrorCode.TRACK_NOT_FOUND
        assert "track" in error.message.lower()
        assert error.details["http_status"] == 404
    
    def test_from_spotify_exception_404_playlist(self):
        """Test creating error from Spotify 404 playlist exception."""
        exc = SpotifyException(404, -1, "playlist not found")
        error = SpotifyMCPError.from_spotify_exception(exc)
        
        assert error.code == SpotifyMCPErrorCode.PLAYLIST_NOT_FOUND
        assert "playlist" in error.message.lower()
        assert error.details["http_status"] == 404
    
    def test_to_mcp_error(self):
        """Test converting to MCP error format."""
        error = SpotifyMCPError(
            SpotifyMCPErrorCode.PREMIUM_REQUIRED,
            "Premium required",
            {"feature": "playback"},
            "Upgrade to Premium"
        )
        
        mcp_error = error.to_mcp_error()
        
        assert mcp_error.type == "text"
        assert "premium required" in mcp_error.text.lower()
        assert "upgrade to premium" in mcp_error.text.lower()