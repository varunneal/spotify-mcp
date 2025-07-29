"""Custom error handling for Spotify MCP server."""
import json
from enum import Enum
from typing import Dict, Any, Optional

import mcp.types as types
from spotipy import SpotifyException


class SpotifyMCPErrorCode(Enum):
    """Error codes for Spotify MCP operations."""
    
    # Authentication errors
    AUTHENTICATION_FAILED = "authentication_failed"
    TOKEN_EXPIRED = "token_expired"
    INSUFFICIENT_SCOPE = "insufficient_scope"
    
    # API errors  
    API_RATE_LIMITED = "api_rate_limited"
    API_UNAVAILABLE = "api_unavailable"
    INVALID_REQUEST = "invalid_request"
    
    # Device errors
    NO_ACTIVE_DEVICE = "no_active_device"
    DEVICE_NOT_FOUND = "device_not_found"
    PREMIUM_REQUIRED = "premium_required"
    
    # Resource errors
    TRACK_NOT_FOUND = "track_not_found"
    PLAYLIST_NOT_FOUND = "playlist_not_found"
    USER_NOT_FOUND = "user_not_found"
    
    # Playback errors
    PLAYBACK_RESTRICTED = "playback_restricted"
    ALREADY_PLAYING = "already_playing"
    ALREADY_PAUSED = "already_paused"
    
    # General errors
    UNKNOWN_ERROR = "unknown_error"
    VALIDATION_ERROR = "validation_error"


class SpotifyMCPError(Exception):
    """Custom exception for Spotify MCP operations with MCP-compliant error reporting."""
    
    def __init__(
        self,
        code: SpotifyMCPErrorCode,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        suggestion: Optional[str] = None
    ):
        """
        Initialize a Spotify MCP error.
        
        Args:
            code: Error code enum
            message: Human-readable error message
            details: Additional error details
            suggestion: Suggestion for resolving the error
        """
        self.code = code
        self.message = message
        self.details = details or {}
        self.suggestion = suggestion
        super().__init__(message)
    
    def to_mcp_error(self) -> types.TextContent:
        """Convert to MCP-compliant error response."""
        error_response = {
            "error": {
                "code": self.code.value,
                "message": self.message,
                "details": self.details
            }
        }
        
        if self.suggestion:
            error_response["error"]["suggestion"] = self.suggestion
            
        return types.TextContent(
            type="text",
            text=json.dumps(error_response, indent=2)
        )
    
    @classmethod
    def from_spotify_exception(cls, exc: SpotifyException) -> "SpotifyMCPError":
        """Create SpotifyMCPError from spotipy SpotifyException."""
        status_code = getattr(exc, 'http_status', None)
        error_message = str(exc)
        
        # Map HTTP status codes to our error codes
        if status_code == 401:
            if "token expired" in error_message.lower():
                return cls(
                    SpotifyMCPErrorCode.TOKEN_EXPIRED,
                    "Spotify access token has expired",
                    {"http_status": status_code},
                    "Please re-authenticate with Spotify"
                )
            else:
                return cls(
                    SpotifyMCPErrorCode.AUTHENTICATION_FAILED,
                    "Authentication with Spotify failed",
                    {"http_status": status_code},
                    "Check your Spotify API credentials"
                )
        
        elif status_code == 403:
            if "premium" in error_message.lower():
                return cls(
                    SpotifyMCPErrorCode.PREMIUM_REQUIRED,
                    "Spotify Premium is required for this operation",
                    {"http_status": status_code},
                    "Upgrade to Spotify Premium to use playback features"
                )
            elif "scope" in error_message.lower():
                return cls(
                    SpotifyMCPErrorCode.INSUFFICIENT_SCOPE,
                    "Insufficient permissions for this operation",
                    {"http_status": status_code},
                    "Re-authenticate with required scopes"
                )
            else:
                return cls(
                    SpotifyMCPErrorCode.PLAYBACK_RESTRICTED,
                    "Playback is restricted for this content",
                    {"http_status": status_code}
                )
        
        elif status_code == 404:
            if "track" in error_message.lower():
                return cls(
                    SpotifyMCPErrorCode.TRACK_NOT_FOUND,
                    "The requested track was not found",
                    {"http_status": status_code},
                    "Check the track ID and try again"
                )
            elif "playlist" in error_message.lower():
                return cls(
                    SpotifyMCPErrorCode.PLAYLIST_NOT_FOUND,
                    "The requested playlist was not found",
                    {"http_status": status_code},
                    "Check the playlist ID and try again"
                )
            elif "user" in error_message.lower():
                return cls(
                    SpotifyMCPErrorCode.USER_NOT_FOUND,
                    "The requested user was not found",
                    {"http_status": status_code}
                )
        
        elif status_code == 429:
            return cls(
                SpotifyMCPErrorCode.API_RATE_LIMITED,
                "Spotify API rate limit exceeded",
                {"http_status": status_code},
                "Wait a moment before making more requests"
            )
        
        elif status_code and status_code >= 500:
            return cls(
                SpotifyMCPErrorCode.API_UNAVAILABLE,
                "Spotify API is temporarily unavailable",
                {"http_status": status_code},
                "Try again in a few minutes"
            )
        
        # Handle specific device-related errors
        if "no active device" in error_message.lower():
            return cls(
                SpotifyMCPErrorCode.NO_ACTIVE_DEVICE,
                "No active Spotify device found",
                {"original_error": error_message},
                "Open Spotify on a device to start playback"
            )
        
        if "device not found" in error_message.lower():
            return cls(
                SpotifyMCPErrorCode.DEVICE_NOT_FOUND,
                "The specified device was not found",
                {"original_error": error_message},
                "Check available devices and try again"
            )
        
        # Default case
        return cls(
            SpotifyMCPErrorCode.UNKNOWN_ERROR,
            f"Spotify API error: {error_message}",
            {"http_status": status_code, "original_error": error_message}
        )
    
    @classmethod
    def validation_error(cls, field: str, message: str) -> "SpotifyMCPError":
        """Create a validation error."""
        return cls(
            SpotifyMCPErrorCode.VALIDATION_ERROR,
            f"Validation error for '{field}': {message}",
            {"field": field},
            "Check the input parameters and try again"
        )
    
    @classmethod
    def no_active_device(cls) -> "SpotifyMCPError":
        """Create a no active device error."""
        return cls(
            SpotifyMCPErrorCode.NO_ACTIVE_DEVICE,
            "No active Spotify device found for playback",
            {},
            "Open Spotify on a device (phone, computer, etc.) to enable playback control"
        )
    
    @classmethod
    def premium_required(cls, operation: str) -> "SpotifyMCPError":
        """Create a premium required error."""
        return cls(
            SpotifyMCPErrorCode.PREMIUM_REQUIRED,
            f"Spotify Premium is required for {operation}",
            {"operation": operation},
            "Upgrade to Spotify Premium to access this feature"
        )


def convert_spotify_error(e: Exception) -> Exception:
    """Convert Spotify exceptions to appropriate exception types for FastMCP."""
    if isinstance(e, SpotifyException):
        error = SpotifyMCPError.from_spotify_exception(e)
        # For FastMCP, we'll raise a ValueError with the error message
        return ValueError(error.message)
    elif isinstance(e, SpotifyMCPError):
        return ValueError(e.message)
    else:
        return ValueError(f"Unexpected error: {str(e)}")


def handle_spotify_error(func):
    """Decorator to handle Spotify API errors and convert them to MCP-compliant responses."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except SpotifyException as e:
            error = SpotifyMCPError.from_spotify_exception(e)
            return [error.to_mcp_error()]
        except SpotifyMCPError as e:
            return [e.to_mcp_error()]
        except Exception as e:
            error = SpotifyMCPError(
                SpotifyMCPErrorCode.UNKNOWN_ERROR,
                f"Unexpected error: {str(e)}",
                {"error_type": type(e).__name__}
            )
            return [error.to_mcp_error()]
    
    return wrapper


async def handle_spotify_error_async(func):
    """Async decorator to handle Spotify API errors and convert them to MCP-compliant responses."""
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except SpotifyException as e:
            error = SpotifyMCPError.from_spotify_exception(e)
            return [error.to_mcp_error()]
        except SpotifyMCPError as e:
            return [e.to_mcp_error()]
        except Exception as e:
            error = SpotifyMCPError(
                SpotifyMCPErrorCode.UNKNOWN_ERROR,
                f"Unexpected error: {str(e)}",
                {"error_type": type(e).__name__}
            )
            return [error.to_mcp_error()]
    
    return wrapper