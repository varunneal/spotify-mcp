import json
import sys

import mcp.types as types
from mcp.server import Server
import mcp.server.stdio
from spotipy import SpotifyException

from . import spotify_api
from .tool_models import (
    GetInfo,
    History,
    Playback,
    Playlist,
    Queue,
    Search,
    SmartPlay,
    TasteProfile,
    ToolModel,
)
from .utils import normalize_redirect_uri


def setup_logger():
    class Logger:
        def info(self, message):
            print(f"[INFO] {message}", file=sys.stderr)

        def error(self, message):
            print(f"[ERROR] {message}", file=sys.stderr)

    return Logger()


logger = setup_logger()
# Normalize the redirect URI to meet Spotify's requirements
if spotify_api.REDIRECT_URI:
    spotify_api.REDIRECT_URI = normalize_redirect_uri(spotify_api.REDIRECT_URI)
spotify_client = spotify_api.Client(logger)

server = Server("spotify-mcp")


@server.list_prompts()
async def handle_list_prompts() -> list[types.Prompt]:
    return []


@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    return []


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available tools."""
    logger.info("Listing available tools")
    # await server.request_context.session.send_notification("are you recieving this notification?")
    tools = [
        Playback.as_tool(),
        Search.as_tool(),
        Queue.as_tool(),
        GetInfo.as_tool(),
        Playlist.as_tool(),
        History.as_tool(),
        TasteProfile.as_tool(),
        SmartPlay.as_tool(),
    ]
    logger.info(f"Available tools: {[tool.name for tool in tools]}")
    return tools


@server.call_tool()
async def handle_call_tool(
        name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool execution requests."""
    logger.info(f"Tool called: {name} with arguments: {arguments}")
    assert name[:7] == "Spotify", f"Unknown tool: {name}"
    try:
        match name[7:]:
            case "Playback":
                action = arguments.get("action")
                match action:
                    case "get":
                        logger.info("Attempting to get current track")
                        curr_track = spotify_client.get_current_track()
                        if curr_track:
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
                        spotify_client.start_playback(spotify_uri=arguments.get("spotify_uri"))
                        logger.info("Playback started successfully")
                        return [types.TextContent(
                            type="text",
                            text="Playback starting."
                        )]
                    case "pause":
                        logger.info("Attempting to pause playback")
                        spotify_client.pause_playback()
                        logger.info("Playback paused successfully")
                        return [types.TextContent(
                            type="text",
                            text="Playback paused."
                        )]
                    case "skip":
                        num_skips = int(arguments.get("num_skips", 1))
                        logger.info(f"Skipping {num_skips} tracks.")
                        spotify_client.skip_track(n=num_skips)
                        return [types.TextContent(
                            type="text",
                            text="Skipped to next track."
                        )]
                    case "previous":
                        logger.info("Skipping to previous track.")
                        spotify_client.previous_track()
                        return [types.TextContent(
                            type="text",
                            text="Skipped to previous track."
                        )]

            case "Search":
                logger.info(f"Performing search with arguments: {arguments}")
                search_results = spotify_client.search(
                    query=arguments.get("query", ""),
                    qtype=arguments.get("qtype", "track"),
                    limit=arguments.get("limit", 10)
                )
                logger.info("Search completed successfully.")
                return [types.TextContent(
                    type="text",
                    text=json.dumps(search_results, indent=2)
                )]

            case "Queue":
                logger.info(f"Queue operation with arguments: {arguments}")
                action = arguments.get("action")

                match action:
                    case "add":
                        track_id = arguments.get("track_id")
                        if not track_id:
                            logger.error("track_id is required for add to queue.")
                            return [types.TextContent(
                                type="text",
                                text="track_id is required for add action"
                            )]
                        spotify_client.add_to_queue(track_id)
                        return [types.TextContent(
                            type="text",
                            text=f"Track added to queue."
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
                            text=f"Unknown queue action: {action}. Supported actions are: add, remove, and get."
                        )]

            case "GetInfo":
                logger.info(f"Getting item info with arguments: {arguments}")
                item_info = spotify_client.get_info(
                    item_uri=arguments.get("item_uri")
                )
                return [types.TextContent(
                    type="text",
                    text=json.dumps(item_info, indent=2)
                )]

            case "Playlist":
                logger.info(f"Playlist operation with arguments: {arguments}")
                action = arguments.get("action")
                match action:
                    case "get":
                        logger.info(f"Getting current user's playlists with arguments: {arguments}")
                        playlists = spotify_client.get_current_user_playlists()
                        return [types.TextContent(
                            type="text",
                            text=json.dumps(playlists, indent=2)
                        )]
                    case "get_tracks":
                        logger.info(f"Getting tracks in playlist with arguments: {arguments}")
                        if not arguments.get("playlist_id"):
                            logger.error("playlist_id is required for get_tracks action.")
                            return [types.TextContent(
                                type="text",
                                text="playlist_id is required for get_tracks action."
                            )]
                        tracks = spotify_client.get_playlist_tracks(arguments.get("playlist_id"))
                        return [types.TextContent(
                            type="text",
                            text=json.dumps(tracks, indent=2)
                        )]
                    case "add_tracks":
                        logger.info(f"Adding tracks to playlist with arguments: {arguments}")
                        track_ids = arguments.get("track_ids")
                        if isinstance(track_ids, str):
                            try:
                                track_ids = json.loads(track_ids)  # Convert JSON string to Python list
                            except json.JSONDecodeError:
                                logger.error("track_ids must be a list or a valid JSON array.")
                                return [types.TextContent(
                                    type="text",
                                    text="Error: track_ids must be a list or a valid JSON array."
                                )]

                        spotify_client.add_tracks_to_playlist(
                            playlist_id=arguments.get("playlist_id"),
                            track_ids=track_ids
                        )
                        return [types.TextContent(
                            type="text",
                            text="Tracks added to playlist."
                        )]
                    case "remove_tracks":
                        logger.info(f"Removing tracks from playlist with arguments: {arguments}")
                        track_ids = arguments.get("track_ids")
                        if isinstance(track_ids, str):
                            try:
                                track_ids = json.loads(track_ids)  # Convert JSON string to Python list
                            except json.JSONDecodeError:
                                logger.error("track_ids must be a list or a valid JSON array.")
                                return [types.TextContent(
                                    type="text",
                                    text="Error: track_ids must be a list or a valid JSON array."
                                )]

                        spotify_client.remove_tracks_from_playlist(
                            playlist_id=arguments.get("playlist_id"),
                            track_ids=track_ids
                        )
                        return [types.TextContent(
                            type="text",
                            text="Tracks removed from playlist."
                        )]

                    case "change_details":
                        logger.info(f"Changing playlist details with arguments: {arguments}")
                        if not arguments.get("playlist_id"):
                            logger.error("playlist_id is required for change_details action.")
                            return [types.TextContent(
                                type="text",
                                text="playlist_id is required for change_details action."
                            )]
                        if not arguments.get("name") and not arguments.get("description"):
                            logger.error("At least one of name, description or public is required.")
                            return [types.TextContent(
                                type="text",
                                text="At least one of name, description, public, or collaborative is required."
                            )]

                        spotify_client.change_playlist_details(
                            playlist_id=arguments.get("playlist_id"),
                            name=arguments.get("name"),
                            description=arguments.get("description")
                        )
                        return [types.TextContent(
                            type="text",
                            text="Playlist details changed."
                        )]

                    case "create":
                        logger.info(f"Creating playlist with arguments: {arguments}")
                        if not arguments.get("name"):
                            logger.error("name is required for create action.")
                            return [types.TextContent(
                                type="text",
                                text="name is required for create action."
                            )]
                        
                        playlist = spotify_client.create_playlist(
                            name=arguments.get("name"),
                            description=arguments.get("description"),
                            public=arguments.get("public", True)
                        )
                        return [types.TextContent(
                            type="text",
                            text=json.dumps(playlist, indent=2)
                        )]

                    case _:
                        return [types.TextContent(
                            type="text",
                            text=f"Unknown playlist action: {action}."
                                 "Supported actions are: get, get_tracks, add_tracks, remove_tracks, change_details, create."
                        )]

            case "History":
                logger.info(f"History operation with arguments: {arguments}")
                items = spotify_client.get_recently_played(
                    limit=int(arguments.get("limit", 20)),
                    after=arguments.get("after"),
                    before=arguments.get("before"),
                )
                if not items:
                    return [types.TextContent(type="text", text="No recently played tracks found.")]
                return [types.TextContent(type="text", text=json.dumps(items, indent=2))]

            case "TasteProfile":
                logger.info(f"TasteProfile operation with arguments: {arguments}")
                action = arguments.get("action", "profile")
                time_range = arguments.get("time_range", "medium_term")
                limit = int(arguments.get("limit", 20))
                refresh = bool(arguments.get("refresh", False))
                if action == "profile":
                    profile = spotify_client.get_taste_profile(
                        time_range=time_range, limit=limit, refresh=refresh
                    )
                    public = {k: v for k, v in profile.items() if not k.startswith("_")}
                    return [types.TextContent(type="text", text=json.dumps(public, indent=2))]
                if action in ("tracks", "artists"):
                    items = spotify_client.get_top_items(
                        entity=action, time_range=time_range, limit=limit
                    )
                    return [types.TextContent(type="text", text=json.dumps(items, indent=2))]
                return [types.TextContent(
                    type="text",
                    text=f"Unknown TasteProfile action: {action}. Supported: profile, tracks, artists."
                )]

            case "SmartPlay":
                logger.info(f"SmartPlay operation with arguments: {arguments}")
                result = spotify_client.smart_play(
                    query=arguments.get("query", ""),
                    prefer=arguments.get("prefer"),
                    auto_play=bool(arguments.get("auto_play", True)),
                    limit=int(arguments.get("limit", 10)),
                )
                return [types.TextContent(
                    type="text",
                    text=json.dumps(result, indent=2, default=str)
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
        logger.error(error_msg)
        return [types.TextContent(
            type="text",
            text=f"An error occurred with the Spotify Client: {str(se)}"
        )]
    except Exception as e:
        error_msg = f"Unexpected error occurred: {str(e)}"
        logger.error(error_msg)
        return [types.TextContent(
            type="text",
            text=error_msg
        )]


async def main():
    try:
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options()
            )
    except Exception as e:
        logger.error(f"Server error occurred: {str(e)}")
        raise
