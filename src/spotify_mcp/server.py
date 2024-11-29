import asyncio
import os
import logging
from enum import Enum
import json
from typing import List, Optional, Tuple
from datetime import datetime
from pathlib import Path

from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server, stdio_server
from pydantic import AnyUrl
import mcp.server.stdio
from pydantic import BaseModel, Field
from spotipy import SpotifyException

from . import spotify_api

# Set up logging configuration
log_dir = Path("/Users/varun/Documents/Python/spotify_mcp/logging")
log_dir.mkdir(parents=True, exist_ok=True)

# Create a formatter that includes timestamp
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# Set up file handler for general logs
log_file = log_dir / f"spotify_mcp_{datetime.now().strftime('%Y%m%d')}.log"
file_handler = logging.FileHandler(log_file)
file_handler.setFormatter(formatter)

# Set up file handler specifically for errors
error_log_file = log_dir / f"spotify_mcp_errors_{datetime.now().strftime('%Y%m%d')}.log"
error_file_handler = logging.FileHandler(error_log_file)
error_file_handler.setFormatter(formatter)
error_file_handler.setLevel(logging.ERROR)

# Configure logger
logger = logging.getLogger("spotify_mcp")
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(error_file_handler)

server = Server("spotify-mcp")
spotify_client = spotify_api.Client(logger)


class ToolModel(BaseModel):
    @classmethod
    def as_tool(cls):
        return types.Tool(
            name=cls.__name__,
            description=cls.__doc__,
            inputSchema=cls.model_json_schema()
        )


class GetCurrentTrack(ToolModel):
    """Get information about user's current track."""
    pass


class StartPlayback(ToolModel):
    """Controls song playback. If song_id is omitted, resumes current playback."""
    song_id: str | None = None


print(StartPlayback.model_json_schema())


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available tools."""
    logger.info("Listing available tools")
    tools = [
        GetCurrentTrack.as_tool(),
        StartPlayback.as_tool()
    ]
    logger.info(f"Available tools: {[tool.name for tool in tools]}")
    return tools


@server.call_tool()
async def handle_call_tool(
        name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool execution requests."""
    logger.info(f"Tool called: {name} with arguments: {arguments}")

    try:
        match name:
            case "GetCurrentTrack":
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

            case "StartPlayback":
                logger.info(f"Starting playback with arguments: {arguments}")
                spotify_client.start_playback(**arguments)
                logger.info("Playback started successfully")
                return [types.TextContent(
                    type="text",
                    text="Playback starting with no errors."
                )]

            case _:
                error_msg = f"Unknown tool: {name}"
                logger.error(error_msg)
                raise ValueError(error_msg)

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


async def main():
    logger.info("Starting Spotify MCP server")
    try:
        options = server.create_initialization_options()
        async with stdio_server() as (read_stream, write_stream):
            logger.info("Server initialized successfully")
            await server.run(
                read_stream,
                write_stream,
                options
            )
    except Exception as e:
        logger.error(f"Server error occurred: {str(e)}", exc_info=True)
        raise