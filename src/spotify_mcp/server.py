import asyncio
import os
import logging
from enum import Enum
import json
from typing import List, Optional, Tuple, Dict, Any, cast
from datetime import datetime
from pathlib import Path

import mcp.types as types
from mcp.server import NotificationOptions, Server, stdio_server
from pydantic import BaseModel, Field, AnyUrl
from spotipy import SpotifyException

from . import spotify_api


# Global state for tracking playback changes
_last_playback_state: Optional[Dict[str, Any]] = None
_notification_task: Optional[asyncio.Task] = None


def setup_logger() -> logging.Logger:
    # TODO: can use mcp.server.stdio
    logger = logging.getLogger("spotify_mcp")

    # Check if LOGGING_PATH environment variable is set
    logging_path = os.getenv("LOGGING_PATH")

    if logging_path:
        log_dir = Path(logging_path)
        log_dir.mkdir(parents=True, exist_ok=True)

        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

        log_file = log_dir / f"spotify_mcp_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)

        error_log_file = log_dir / f"spotify_mcp_errors_{datetime.now().strftime('%Y%m%d')}.log"
        error_file_handler = logging.FileHandler(error_log_file)
        error_file_handler.setFormatter(formatter)
        error_file_handler.setLevel(logging.ERROR)

        # Configure logger with both handlers
        logger.setLevel(logging.INFO)
        logger.addHandler(file_handler)
        logger.addHandler(error_file_handler)
    else:
        # Use default logging configuration
        logger.setLevel(logging.INFO)

    return logger


logger = setup_logger()
server = Server("spotify-mcp")
spotify_client = spotify_api.Client(logger)

class ToolModel(BaseModel):
    @classmethod
    def as_tool(cls) -> types.Tool:
        return types.Tool(
            name="Spotify" + cls.__name__,
            description=cls.__doc__,
            inputSchema=cls.model_json_schema()
        )

class Playback(ToolModel):
    """Manages the current playback with the following actions:
    - get: Get information about user's current track.
    - start: Starts of resumes playback.
    - pause: Pauses current playback.
    - skip: Skips current track.
    """
    action: str = Field(description="Action to perform: 'get', 'start', 'pause' or 'skip'.")
    track_id: Optional[str] = Field(default=None, description="Specifies track to play for 'start' action. If omitted, resumes current playback.")
    num_skips: Optional[int] = Field(default=1, description="Number of tracks to skip for `skip` action.")


class Queue(ToolModel):
    """Manage the playback queue - get the queue or add tracks."""
    action: str = Field(description="Action to perform: 'add' or 'get'.")
    track_id: Optional[str] = Field(default=None, description="Track ID to add to queue (required for add action)")


class GetInfo(ToolModel):
    """Get detailed information about a Spotify item (track, album, artist, or playlist)."""
    item_id: str = Field(description="ID of the item to get information about")
    qtype: str = Field(default="track", description="Type of item: 'track', 'album', 'artist', or 'playlist'. "
                                                    "If 'playlist' or 'album', returns its tracks. If 'artist',"
                                                    "returns albums and top tracks.")


class Search(ToolModel):
    """Search for tracks, albums, artists, or playlists on Spotify."""
    query: str = Field(description="query term")
    qtype: Optional[str] = Field(default="track", description="Type of items to search for (track, album, artist, playlist, or comma-separated combination)")
    limit: Optional[int] = Field(default=10, description="Maximum number of items to return")


class PlaylistManage(ToolModel):
    """Manage playlists - create, update details, or get details of playlists."""
    action: str = Field(description="Action to perform: 'create', 'update_details', 'get'")
    playlist_id: Optional[str] = Field(default=None, description="Playlist ID (required for update_details and get actions)")
    name: Optional[str] = Field(default=None, description="Playlist name (required for create action, optional for update_details)")
    description: Optional[str] = Field(default=None, description="Playlist description (optional)")
    public: Optional[bool] = Field(default=None, description="Whether the playlist should be public (optional)")


class PlaylistItems(ToolModel):
    """Manage playlist items - add, remove, or update items in a playlist."""
    action: str = Field(description="Action to perform: 'add', 'remove', 'update'")
    playlist_id: str = Field(description="Playlist ID")
    uris: List[str] = Field(description="List of Spotify URIs for tracks to add/remove/update")
    position: Optional[int] = Field(default=None, description="Position to insert tracks (for add action)")
    range_start: Optional[int] = Field(default=None, description="Start index for reordering (for update action)")
    insert_before: Optional[int] = Field(default=None, description="Position to insert before (for update action)")
    range_length: Optional[int] = Field(default=None, description="Number of items to move (for update action)")
    snapshot_id: Optional[str] = Field(default=None, description="Playlist's snapshot ID (optional)")


class UserPlaylists(ToolModel):
    """Get a user's playlists."""
    user_id: Optional[str] = Field(default=None, description="User ID (optional, if omitted returns current user's playlists)")
    limit: Optional[int] = Field(default=20, description="Maximum number of playlists to return")
    offset: Optional[int] = Field(default=0, description="Offset for pagination")


class PlaylistCover(ToolModel):
    """Manage playlist cover image - get or upload custom cover."""
    action: str = Field(description="Action to perform: 'get' or 'upload'")
    playlist_id: str = Field(description="Playlist ID")
    image_data: Optional[str] = Field(default=None, description="Base64-encoded JPEG image data (required for upload action)")


@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    """List available MCP resources."""
    logger.info("Listing available resources")
    resources = [
        types.Resource(
            uri="spotify://user/current",
            name="Current User Profile", 
            description="Current Spotify user's profile information and preferences",
            mimeType="application/json"
        ),
        types.Resource(
            uri="spotify://playback/current",
            name="Current Playback State",
            description="Real-time information about current playback including track, device, and state",
            mimeType="application/json"
        ),
        types.Resource(
            uri="spotify://devices/available", 
            name="Available Devices",
            description="List of available Spotify devices for playback control",
            mimeType="application/json"
        ),
        types.Resource(
            uri="spotify://queue/current",
            name="Current Queue",
            description="Current playback queue with upcoming tracks",
            mimeType="application/json"
        )
    ]
    logger.info(f"Available resources: {[r.name for r in resources]}")
    return resources


@server.read_resource()
async def handle_read_resource(uri: AnyUrl) -> str:
    """Handle resource read requests."""
    uri_str = str(uri)
    logger.info(f"Reading resource: {uri_str}")
    
    try:
        if uri_str == "spotify://user/current":
            user_info = spotify_client.sp.current_user()
            if user_info:
                # Clean up the user info to include relevant details
                cleaned_info = {
                    "id": user_info.get("id"),
                    "display_name": user_info.get("display_name"),
                    "email": user_info.get("email"),
                    "country": user_info.get("country"),
                    "product": user_info.get("product"),
                    "followers": user_info.get("followers", {}).get("total", 0),
                    "images": user_info.get("images", [])
                }
                return json.dumps(cleaned_info, indent=2)
            return json.dumps({"error": "Unable to fetch user information"})
            
        elif uri_str == "spotify://playback/current":
            playback_info = spotify_client.sp.current_playback()
            if playback_info:
                # Parse and clean playback information
                current_track = spotify_client.get_current_track()
                cleaned_playback = {
                    "is_playing": playback_info.get("is_playing", False),
                    "progress_ms": playback_info.get("progress_ms", 0),
                    "volume_percent": playback_info.get("device", {}).get("volume_percent"),
                    "device": {
                        "name": playback_info.get("device", {}).get("name"),
                        "type": playback_info.get("device", {}).get("type"),
                        "is_active": playback_info.get("device", {}).get("is_active")
                    },
                    "current_track": current_track,
                    "shuffle_state": playback_info.get("shuffle_state"),
                    "repeat_state": playback_info.get("repeat_state")
                }
                return json.dumps(cleaned_playback, indent=2)
            return json.dumps({"is_playing": False, "current_track": None})
            
        elif uri_str == "spotify://devices/available":
            devices = spotify_client.get_devices()
            return json.dumps({"devices": devices}, indent=2)
            
        elif uri_str == "spotify://queue/current":
            queue_info = spotify_client.get_queue()
            return json.dumps(queue_info, indent=2)
            
        else:
            logger.error(f"Unknown resource URI: {uri_str}")
            return json.dumps({"error": f"Unknown resource: {uri_str}"})
            
    except Exception as e:
        error_msg = f"Error reading resource {uri_str}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return json.dumps({"error": error_msg})


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available tools."""
    logger.info("Listing available tools")
    tools = [
        Playback.as_tool(),
        Search.as_tool(),
        Queue.as_tool(),
        GetInfo.as_tool(),
        PlaylistManage.as_tool(),
        PlaylistItems.as_tool(),
        UserPlaylists.as_tool(),
        PlaylistCover.as_tool(),
    ]
    logger.info(f"Available tools: {[tool.name for tool in tools]}")
    return tools


@server.call_tool()
async def handle_call_tool(
        name: str, arguments: Optional[Dict[str, Any]]
) -> List[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool execution requests."""
    arguments = arguments or {}
    # Ensure all string values are properly typed
    def get_str_arg(args: Dict[str, Any], key: str, default: str = "") -> str:
        val = args.get(key, default)
        return str(val) if val is not None else default

    def get_int_arg(args: Dict[str, Any], key: str, default: int) -> int:
        val = args.get(key, default)
        return int(val) if val is not None else default
    logger.info(f"Tool called: {name} with arguments: {arguments}")
    assert name[:7] == "Spotify", f"Unknown tool: {name}"

    try:
        match name[7:]:
            case "Playback":
                action = get_str_arg(arguments, "action")
                match action:
                    case "get":
                        logger.info("Attempting to get current track")
                        if curr_track := spotify_client.get_current_track():
                            logger.info(f"Current track retrieved: {curr_track.get('name', 'Unknown')}")
                            return [types.TextContent(
                                type="text",
                                text=json.dumps(curr_track, indent=2)
                            )]
                        logger.info("No track currently playing")
                        return [types.TextContent(
                            type="text",
                            text="No track playing."
                        )]
                    case "start":
                        logger.info(f"Starting playback with arguments: {arguments}")
                        track_id = arguments.get("track_id")
                        if track_id is not None and not isinstance(track_id, str):
                            return [types.TextContent(
                                type="text",
                                text="track_id must be a string if provided"
                            )]
                        spotify_client.start_playback(track_id=str(track_id) if track_id else None)
                        logger.info("Playback started successfully")
                        return [types.TextContent(
                            type="text",
                            text="Playback starting with no errors."
                        )]
                    case "pause":
                        logger.info("Attempting to pause playback")
                        spotify_client.pause_playback()
                        logger.info("Playback paused successfully")
                        return [types.TextContent(
                            type="text",
                            text="Playback paused successfully."
                        )]
                    case "skip":
                        num_skips = get_int_arg(arguments, "num_skips", 1)
                        logger.info(f"Skipping {num_skips} tracks.")
                        spotify_client.skip_track(n=num_skips)
                        return [types.TextContent(
                            type="text",
                            text="Skipped to next track."
                        )]
                    case _:
                        return [types.TextContent(
                            type="text",
                            text=f"Unknown playback action: {action}. Supported actions are: get, start, pause, skip"
                        )]

            case "Search":
                logger.info(f"Performing search with arguments: {arguments}")
                query = get_str_arg(arguments, "query")
                if not query:
                    return [types.TextContent(
                        type="text",
                        text="query is required"
                    )]
                search_results = spotify_client.search(
                    query=query,
                    qtype=get_str_arg(arguments, "qtype", "track"),
                    limit=get_int_arg(arguments, "limit", 10)
                )
                logger.info("Search completed successfully")
                return [types.TextContent(
                    type="text",
                    text=json.dumps(search_results, indent=2)
                )]

            case "Queue":
                logger.info(f"Queue operation with arguments: {arguments}")
                action = get_str_arg(arguments, "action")

                match action:
                    case "add":
                        track_id = get_str_arg(arguments, "track_id")
                        if not track_id:
                            logger.error("track_id is required for add to queue")
                            return [types.TextContent(
                                type="text",
                                text="track_id is required for add action"
                            )]
                        spotify_client.add_to_queue(track_id)
                        return [types.TextContent(
                            type="text",
                            text=f"Track added to queue successfully."
                        )]

                    case "get":
                        queue = spotify_client.get_queue()
                        return [types.TextContent(
                            type="text",
                            text=json.dumps(queue, indent=2)
                        )]

                    case _:
                        return [types.TextContent(
                            type="text",
                            text=f"Unknown queue action: {action}. Supported actions are: add, get"
                        )]

            case "GetInfo":
                logger.info(f"Getting item info with arguments: {arguments}")
                item_id = get_str_arg(arguments, "item_id")
                if not item_id:
                    return [types.TextContent(
                        type="text",
                        text="item_id is required"
                    )]
                item_info = spotify_client.get_info(
                    item_id=item_id,
                    qtype=get_str_arg(arguments, "qtype", "track")
                )
                return [types.TextContent(
                    type="text",
                    text=json.dumps(item_info, indent=2)
                )]

            case "PlaylistManage":
                action = get_str_arg(arguments, "action")
                match action:
                    case "create":
                        name = get_str_arg(arguments, "name")
                        if not name:
                            return [types.TextContent(
                                type="text",
                                text="name is required for create action"
                            )]
                        current_user = spotify_client.sp.current_user()
                        if not current_user or not isinstance(current_user, dict) or "id" not in current_user:
                            return [types.TextContent(
                                type="text",
                                text="Failed to get current user ID"
                            )]
                        user_id = str(current_user["id"])
                        playlist = spotify_client.create_playlist(
                            user_id=user_id,
                            name=name,
                            description=get_str_arg(arguments, "description"),
                            public=bool(arguments.get("public", False))
                        )
                        return [types.TextContent(
                            type="text",
                            text=json.dumps(playlist, indent=2)
                        )]
                    case "update_details":
                        playlist_id = get_str_arg(arguments, "playlist_id")
                        if not playlist_id:
                            return [types.TextContent(
                                type="text",
                                text="playlist_id is required for update_details action"
                            )]
                        spotify_client.update_playlist_details(
                            playlist_id=playlist_id,
                            name=arguments.get("name"),
                            description=arguments.get("description"),
                            public=arguments.get("public")
                        )
                        return [types.TextContent(
                            type="text",
                            text="Playlist details updated successfully."
                        )]
                    case "get":
                        playlist_id = get_str_arg(arguments, "playlist_id")
                        if not playlist_id:
                            return [types.TextContent(
                                type="text",
                                text="playlist_id is required for get action"
                            )]
                        playlist = spotify_client.get_playlist(playlist_id)
                        return [types.TextContent(
                            type="text",
                            text=json.dumps(playlist, indent=2)
                        )]
                    case _:
                        return [types.TextContent(
                            type="text",
                            text=f"Unknown playlist action: {action}. Supported actions are: create, update_details, get"
                        )]

            case "PlaylistItems":
                action = get_str_arg(arguments, "action")
                playlist_id = get_str_arg(arguments, "playlist_id")
                if not playlist_id:
                    return [types.TextContent(
                        type="text",
                        text="playlist_id is required"
                    )]
                uris = arguments.get("uris")
                if not uris or not isinstance(uris, list):
                    return [types.TextContent(
                        type="text",
                        text="uris must be a non-empty list"
                    )]

                match action:
                    case "add":
                        result = spotify_client.add_playlist_items(
                            playlist_id=playlist_id,
                            uris=cast(List[str], uris),
                            position=arguments.get("position")
                        )
                        return [types.TextContent(
                            type="text",
                            text=f"Added {len(uris)} tracks to playlist. Snapshot ID: {result.get('snapshot_id')}"
                        )]
                    case "remove":
                        result = spotify_client.remove_playlist_items(
                            playlist_id=playlist_id,
                            uris=cast(List[str], uris),
                            snapshot_id=arguments.get("snapshot_id")
                        )
                        return [types.TextContent(
                            type="text",
                            text=f"Removed {len(uris)} tracks from playlist. Snapshot ID: {result.get('snapshot_id')}"
                        )]
                    case "update":
                        result = spotify_client.update_playlist_items(
                            playlist_id=playlist_id,
                            uris=cast(List[str], uris),
                            range_start=arguments.get("range_start"),
                            insert_before=arguments.get("insert_before"),
                            range_length=arguments.get("range_length"),
                            snapshot_id=arguments.get("snapshot_id")
                        )
                        return [types.TextContent(
                            type="text",
                            text=f"Updated playlist items. Snapshot ID: {result.get('snapshot_id')}"
                        )]
                    case _:
                        return [types.TextContent(
                            type="text",
                            text=f"Unknown playlist items action: {action}. Supported actions are: add, remove, update"
                        )]

            case "UserPlaylists":
                playlists = spotify_client.get_user_playlists(
                    user_id=get_str_arg(arguments, "user_id"),
                    limit=get_int_arg(arguments, "limit", 20),
                    offset=get_int_arg(arguments, "offset", 0)
                )
                return [types.TextContent(
                    type="text",
                    text=json.dumps(playlists, indent=2)
                )]

            case "PlaylistCover":
                action = get_str_arg(arguments, "action")
                playlist_id = get_str_arg(arguments, "playlist_id")
                if not playlist_id:
                    return [types.TextContent(
                        type="text",
                        text="playlist_id is required"
                    )]

                match action:
                    case "get":
                        images = spotify_client.get_playlist_cover_image(playlist_id)
                        return [types.TextContent(
                            type="text",
                            text=json.dumps(images, indent=2)
                        )]
                    case "upload":
                        image_data = get_str_arg(arguments, "image_data")
                        if not image_data:
                            return [types.TextContent(
                                type="text",
                                text="image_data is required for upload action"
                            )]
                        spotify_client.upload_playlist_cover_image(playlist_id, image_data)
                        return [types.TextContent(
                            type="text",
                            text="Playlist cover image uploaded successfully."
                        )]
                    case _:
                        return [types.TextContent(
                            type="text",
                            text=f"Unknown playlist cover action: {action}. Supported actions are: get, upload"
                        )]

            case _:
                error_msg = f"Unknown tool: {name}"
                logger.error(error_msg)
                return [types.TextContent(
                    type="text",
                    text=error_msg
                )]

    except SpotifyException as se:
        error_msg = f"Spotify Client error occurred: {str(se)}"
        logger.error(error_msg, exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"An error occurred with the Spotify Client: {str(se)}"
        )]
    except Exception as e:
        error_msg = f"Unexpected error occurred: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise


async def monitor_playback_state() -> None:
    """Monitor playback state and send notifications when it changes."""
    global _last_playback_state
    
    logger.info("Starting playback state monitoring")
    
    while True:
        try:
            # Get current playback state
            current_playback = spotify_client.sp.current_playback()
            
            # Create a comparable state representation
            if current_playback:
                current_state = {
                    "is_playing": current_playback.get("is_playing", False),
                    "track_id": current_playback.get("item", {}).get("id") if current_playback.get("item") else None,
                    "progress_ms": current_playback.get("progress_ms", 0),
                    "device_name": current_playback.get("device", {}).get("name"),
                    "shuffle_state": current_playback.get("shuffle_state"),
                    "repeat_state": current_playback.get("repeat_state"),
                    "volume_percent": current_playback.get("device", {}).get("volume_percent")
                }
            else:
                current_state = {"is_playing": False, "track_id": None}
            
            # Check if state has changed significantly
            if _last_playback_state is None or _has_significant_change(_last_playback_state, current_state):
                logger.info(f"Playback state changed: {current_state}")
                
                # Send notification about resource update
                try:
                    await server.send_resource_updated("spotify://playback/current")
                    logger.info("Sent playback state change notification")
                except Exception as e:
                    logger.error(f"Failed to send notification: {e}")
                
                _last_playback_state = current_state
            
            # Wait before next poll (every 5 seconds)
            await asyncio.sleep(5)
            
        except Exception as e:
            logger.error(f"Error in playback monitoring: {e}", exc_info=True)
            await asyncio.sleep(10)  # Wait longer if there's an error


def _has_significant_change(old_state: Dict[str, Any], new_state: Dict[str, Any]) -> bool:
    """Check if there's a significant change in playback state worth notifying about."""
    # Always notify if play/pause state changes
    if old_state.get("is_playing") != new_state.get("is_playing"):
        return True
    
    # Always notify if track changes
    if old_state.get("track_id") != new_state.get("track_id"):
        return True
    
    # Always notify if device changes
    if old_state.get("device_name") != new_state.get("device_name"):
        return True
    
    # Notify if shuffle or repeat state changes
    if old_state.get("shuffle_state") != new_state.get("shuffle_state"):
        return True
    
    if old_state.get("repeat_state") != new_state.get("repeat_state"):
        return True
    
    # Notify if volume changes significantly (more than 5%)
    old_volume = old_state.get("volume_percent") or 0
    new_volume = new_state.get("volume_percent") or 0
    if abs(old_volume - new_volume) > 5:
        return True
    
    # Don't notify for small progress changes (less than 10 seconds difference)
    old_progress = old_state.get("progress_ms") or 0
    new_progress = new_state.get("progress_ms") or 0
    if abs(old_progress - new_progress) > 10000:  # 10 seconds
        return True
    
    return False


async def start_notifications() -> None:
    """Start the notification monitoring task."""
    global _notification_task
    
    if _notification_task is None or _notification_task.done():
        _notification_task = asyncio.create_task(monitor_playback_state())
        logger.info("Started notification monitoring task")


async def stop_notifications() -> None:
    """Stop the notification monitoring task."""
    global _notification_task
    
    if _notification_task and not _notification_task.done():
        _notification_task.cancel()
        try:
            await _notification_task
        except asyncio.CancelledError:
            pass
        logger.info("Stopped notification monitoring task")


async def main() -> None:
    logger.info("Starting Spotify MCP server")
    try:
        options = server.create_initialization_options()
        async with stdio_server() as (read_stream, write_stream):
            logger.info("Server initialized successfully")
            
            # Start notification monitoring
            await start_notifications()
            
            try:
                await server.run(
                    read_stream,
                    write_stream,
                    options
                )
            finally:
                # Clean up notification monitoring
                await stop_notifications()
                
    except Exception as e:
        logger.error(f"Server error occurred: {str(e)}", exc_info=True)
        raise
