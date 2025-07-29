"""Tests for error handling functionality."""
import json
from typing import Dict, Any

import pytest
import mcp.types as types
from spotipy import SpotifyException

from spotify_mcp.errors import (
    SpotifyMCPError,
    SpotifyMCPErrorCode,
    handle_spotify_error
)


class TestSpotifyMCPError:
    """Tests for SpotifyMCPError class."""
    
    def test_basic_error_creation(self) -> None:
        """Test basic error creation and properties."""
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
    
    def test_to_mcp_error(self) -> None:
        """Test conversion to MCP error format."""
        error = SpotifyMCPError(
            SpotifyMCPErrorCode.AUTHENTICATION_FAILED,
            "Auth failed",
            {"code": 401},
            "Re-authenticate"
        )
        
        mcp_error = error.to_mcp_error()
        
        assert isinstance(mcp_error, types.TextContent)
        parsed_response = json.loads(mcp_error.text)
        
        assert parsed_response["error"]["code"] == "authentication_failed"
        assert parsed_response["error"]["message"] == "Auth failed"
        assert parsed_response["error"]["details"] == {"code": 401}
        assert parsed_response["error"]["suggestion"] == "Re-authenticate"
    
    def test_to_mcp_error_without_suggestion(self) -> None:
        """Test MCP error format without suggestion."""
        error = SpotifyMCPError(
            SpotifyMCPErrorCode.UNKNOWN_ERROR,
            "Something went wrong"
        )
        
        mcp_error = error.to_mcp_error()
        parsed_response = json.loads(mcp_error.text)
        
        assert "suggestion" not in parsed_response["error"]
    
    def test_validation_error_class_method(self) -> None:
        """Test validation error class method."""
        error = SpotifyMCPError.validation_error("track_id", "cannot be empty")
        
        assert error.code == SpotifyMCPErrorCode.VALIDATION_ERROR
        assert "track_id" in error.message
        assert "cannot be empty" in error.message
        assert error.details["field"] == "track_id"
        assert "Check the input parameters" in error.suggestion
    
    def test_no_active_device_class_method(self) -> None:
        """Test no active device error class method."""
        error = SpotifyMCPError.no_active_device()
        
        assert error.code == SpotifyMCPErrorCode.NO_ACTIVE_DEVICE
        assert "No active Spotify device" in error.message
        assert "Open Spotify on a device" in error.suggestion
    
    def test_premium_required_class_method(self) -> None:
        """Test premium required error class method."""
        error = SpotifyMCPError.premium_required("playback control")
        
        assert error.code == SpotifyMCPErrorCode.PREMIUM_REQUIRED
        assert "playback control" in error.message
        assert error.details["operation"] == "playback control"
        assert "Upgrade to Spotify Premium" in error.suggestion


class TestSpotifyExceptionMapping:
    """Tests for converting SpotifyException to SpotifyMCPError."""
    
    def test_401_token_expired(self) -> None:
        """Test mapping 401 token expired error."""
        spotify_exc = SpotifyException(
            http_status=401,
            code=401,
            msg="The access token expired"
        )
        
        error = SpotifyMCPError.from_spotify_exception(spotify_exc)
        
        assert error.code == SpotifyMCPErrorCode.TOKEN_EXPIRED
        assert "expired" in error.message
        assert "re-authenticate" in error.suggestion.lower()
        assert error.details["http_status"] == 401
    
    def test_401_general_auth_failure(self) -> None:
        """Test mapping 401 general authentication failure."""
        spotify_exc = SpotifyException(
            http_status=401,
            code=401,
            msg="Invalid access token"
        )
        
        error = SpotifyMCPError.from_spotify_exception(spotify_exc)
        
        assert error.code == SpotifyMCPErrorCode.AUTHENTICATION_FAILED
        assert "Authentication" in error.message
        assert "credentials" in error.suggestion.lower()
    
    def test_403_premium_required(self) -> None:
        """Test mapping 403 premium required error."""
        spotify_exc = SpotifyException(
            http_status=403,
            code=403,
            msg="Premium required"
        )
        
        error = SpotifyMCPError.from_spotify_exception(spotify_exc)
        
        assert error.code == SpotifyMCPErrorCode.PREMIUM_REQUIRED
        assert "Premium" in error.message
        assert "Upgrade" in error.suggestion
    
    def test_403_insufficient_scope(self) -> None:
        """Test mapping 403 insufficient scope error."""
        spotify_exc = SpotifyException(
            http_status=403,
            code=403,
            msg="Insufficient client scope"
        )
        
        error = SpotifyMCPError.from_spotify_exception(spotify_exc)
        
        assert error.code == SpotifyMCPErrorCode.INSUFFICIENT_SCOPE
        assert "permissions" in error.message.lower()
        assert "scope" in error.suggestion.lower()
    
    def test_404_track_not_found(self) -> None:
        """Test mapping 404 track not found error."""
        spotify_exc = SpotifyException(
            http_status=404,
            code=404,
            msg="Track not found"
        )
        
        error = SpotifyMCPError.from_spotify_exception(spotify_exc)
        
        assert error.code == SpotifyMCPErrorCode.TRACK_NOT_FOUND
        assert "track" in error.message.lower()
        assert "track ID" in error.suggestion
    
    def test_404_playlist_not_found(self) -> None:
        """Test mapping 404 playlist not found error."""
        spotify_exc = SpotifyException(
            http_status=404,
            code=404,
            msg="Playlist not found"
        )
        
        error = SpotifyMCPError.from_spotify_exception(spotify_exc)
        
        assert error.code == SpotifyMCPErrorCode.PLAYLIST_NOT_FOUND
        assert "playlist" in error.message.lower()
        assert "playlist ID" in error.suggestion
    
    def test_429_rate_limited(self) -> None:
        """Test mapping 429 rate limit error."""
        spotify_exc = SpotifyException(
            http_status=429,
            code=429,
            msg="API rate limit exceeded"
        )
        
        error = SpotifyMCPError.from_spotify_exception(spotify_exc)
        
        assert error.code == SpotifyMCPErrorCode.API_RATE_LIMITED
        assert "rate limit" in error.message.lower()
        assert "Wait" in error.suggestion
    
    def test_500_api_unavailable(self) -> None:
        """Test mapping 500 server error."""
        spotify_exc = SpotifyException(
            http_status=500,
            code=500,
            msg="Internal server error"
        )
        
        error = SpotifyMCPError.from_spotify_exception(spotify_exc)
        
        assert error.code == SpotifyMCPErrorCode.API_UNAVAILABLE
        assert "unavailable" in error.message.lower()
        assert "Try again" in error.suggestion
    
    def test_no_active_device_message(self) -> None:
        """Test mapping no active device message."""
        spotify_exc = SpotifyException(
            http_status=404,
            code=404,
            msg="No active device found"
        )
        
        error = SpotifyMCPError.from_spotify_exception(spotify_exc)
        
        assert error.code == SpotifyMCPErrorCode.NO_ACTIVE_DEVICE
        assert "No active" in error.message
        assert "Open Spotify" in error.suggestion
    
    def test_unknown_error_fallback(self) -> None:
        """Test fallback to unknown error for unmapped exceptions."""
        spotify_exc = SpotifyException(
            http_status=418,  # I'm a teapot
            code=418,
            msg="I'm a teapot"
        )
        
        error = SpotifyMCPError.from_spotify_exception(spotify_exc)
        
        assert error.code == SpotifyMCPErrorCode.UNKNOWN_ERROR
        assert "I'm a teapot" in error.message
        assert error.details["http_status"] == 418


class TestErrorHandlerDecorator:
    """Tests for the error handler decorator."""
    
    def test_successful_function_call(self) -> None:
        """Test that successful function calls are not affected."""
        @handle_spotify_error
        def successful_function(value: str) -> str:
            return f"Success: {value}"
        
        result = successful_function("test")
        assert result == "Success: test"
    
    def test_spotify_exception_handling(self) -> None:
        """Test that SpotifyException is properly handled."""
        @handle_spotify_error
        def failing_function() -> str:
            raise SpotifyException(
                http_status=401,
                code=401,
                msg="Token expired"
            )
        
        result = failing_function()
        
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], types.TextContent)
        
        parsed_response = json.loads(result[0].text)
        assert parsed_response["error"]["code"] == "token_expired"
    
    def test_spotify_mcp_error_handling(self) -> None:
        """Test that SpotifyMCPError is properly handled."""
        @handle_spotify_error
        def failing_function() -> str:
            raise SpotifyMCPError.validation_error("test_field", "invalid value")
        
        result = failing_function()
        
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], types.TextContent)
        
        parsed_response = json.loads(result[0].text)
        assert parsed_response["error"]["code"] == "validation_error"
    
    def test_generic_exception_handling(self) -> None:
        """Test that generic exceptions are properly handled."""
        @handle_spotify_error
        def failing_function() -> str:
            raise ValueError("Something went wrong")
        
        result = failing_function()
        
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], types.TextContent)
        
        parsed_response = json.loads(result[0].text)
        assert parsed_response["error"]["code"] == "unknown_error"
        assert "Something went wrong" in parsed_response["error"]["message"]
        assert parsed_response["error"]["details"]["error_type"] == "ValueError"