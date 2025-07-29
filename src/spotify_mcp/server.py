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
from .errors import SpotifyMCPError, SpotifyMCPErrorCode, handle_spotify_error


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


class AdvancedSearch(ToolModel):
    """Advanced search with filters, recommendations, and intelligent discovery."""
    query: str = Field(description="Base search query")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Search filters: artist, album, year, year_range, genre, etc.")
    include_recommendations: bool = Field(default=False, description="Include AI-powered recommendations based on search results")
    qtype: Optional[str] = Field(default="track", description="Type of items to search for")
    limit: Optional[int] = Field(default=20, description="Maximum number of items to return")
    market: Optional[str] = Field(default=None, description="Market/country code for localized results")


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


class BatchTrackInfo(ToolModel):
    """Get detailed information for multiple tracks at once (up to 50 tracks). Includes audio features, popularity, and market availability."""
    track_ids: List[str] = Field(description="List of Spotify track IDs (up to 50)")
    include_audio_features: bool = Field(default=False, description="Include audio features analysis")
    market: Optional[str] = Field(default=None, description="Market code for track availability")


class BatchPlaylistOperations(ToolModel):
    """Perform batch operations on playlists - efficiently add/remove/replace multiple tracks in one API call (up to 100 tracks)."""
    action: str = Field(description="Action: 'add_tracks', 'remove_tracks', 'replace_tracks'")
    playlist_id: str = Field(description="ID of the playlist")
    track_uris: List[str] = Field(description="List of Spotify track URIs (up to 100)")
    position: Optional[int] = Field(default=None, description="Position to insert tracks (for add_tracks)")
    snapshot_id: Optional[str] = Field(default=None, description="Playlist snapshot ID for consistency")


class RecommendationEngine(ToolModel):
    """Get AI-powered music recommendations with advanced audio feature targeting. Perfect for playlist creation and music discovery."""
    seed_tracks: Optional[List[str]] = Field(default=None, description="Up to 5 seed track IDs")
    seed_artists: Optional[List[str]] = Field(default=None, description="Up to 5 seed artist IDs") 
    seed_genres: Optional[List[str]] = Field(default=None, description="Up to 5 seed genres")
    limit: int = Field(default=20, description="Number of recommendations (1-100)")
    market: Optional[str] = Field(default=None, description="Market for track availability")
    target_acousticness: Optional[float] = Field(default=None, description="Target acousticness (0.0-1.0)")
    target_danceability: Optional[float] = Field(default=None, description="Target danceability (0.0-1.0)")
    target_energy: Optional[float] = Field(default=None, description="Target energy (0.0-1.0)")
    target_valence: Optional[float] = Field(default=None, description="Target valence/positivity (0.0-1.0)")
    target_tempo: Optional[float] = Field(default=None, description="Target tempo (BPM)")
    min_popularity: Optional[int] = Field(default=None, description="Minimum popularity (0-100)")
    max_popularity: Optional[int] = Field(default=None, description="Maximum popularity (0-100)")


class UserAnalytics(ToolModel):
    """Get user listening analytics, top content, and musical preferences. Provides insights into listening patterns and taste."""
    analysis_type: str = Field(description="Type: 'top_artists', 'top_tracks', 'recently_played', 'listening_stats'")
    time_range: str = Field(default="medium_term", description="Time range: 'short_term', 'medium_term', 'long_term'")
    limit: int = Field(default=20, description="Number of items to return (max 50)")
    include_audio_features: bool = Field(default=False, description="Include audio feature analysis")


class PaginatedSearch(ToolModel):
    """Perform paginated search across large result sets. Efficiently handles searches with thousands of results."""
    query: str = Field(description="Search query")
    qtype: str = Field(default="track", description="Search type: track, artist, album, or playlist")
    limit: int = Field(default=20, description="Items per page (max 50)")
    offset: int = Field(default=0, description="Starting position (for pagination)")
    market: Optional[str] = Field(default=None, description="Market code for availability filtering")
    get_all_pages: bool = Field(default=False, description="Fetch all available results (use carefully for large datasets)")
    max_results: int = Field(default=1000, description="Maximum results when get_all_pages=True")


class PlaylistPagination(ToolModel):
    """Get playlist items with pagination support for large playlists (10,000+ tracks)."""
    playlist_id: str = Field(description="Playlist ID")
    limit: int = Field(default=50, description="Items per page (max 100)")
    offset: int = Field(default=0, description="Starting position")
    get_all_tracks: bool = Field(default=False, description="Fetch all tracks in playlist")
    include_audio_features: bool = Field(default=False, description="Include audio features for tracks")
    fields: Optional[str] = Field(default=None, description="Specific fields to retrieve (Spotify field filter)")


class LibraryOperations(ToolModel):
    """Advanced library operations with pagination and batch processing."""
    operation: str = Field(description="Operation: 'get_saved_tracks', 'get_saved_albums', 'get_followed_artists', 'save_tracks', 'remove_tracks'")
    limit: int = Field(default=20, description="Items per page (max 50)")
    offset: int = Field(default=0, description="Starting position for pagination")
    track_ids: Optional[List[str]] = Field(default=None, description="Track IDs for save/remove operations (up to 50)")
    get_all_items: bool = Field(default=False, description="Fetch entire library (use carefully)")
    include_audio_features: bool = Field(default=False, description="Include audio features for tracks")


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


@server.list_prompts()
async def handle_list_prompts() -> list[types.Prompt]:
    """List available MCP prompts for common workflows."""
    logger.info("Listing available prompts")
    prompts = [
        types.Prompt(
            name="create_mood_playlist",
            description="Create a playlist based on mood, genre, and preferences",
            arguments=[
                types.PromptArgument(
                    name="mood",
                    description="Target mood (e.g., happy, sad, energetic, chill)",
                    required=True
                ),
                types.PromptArgument(
                    name="genre",
                    description="Preferred genre (optional)",
                    required=False
                ),
                types.PromptArgument(
                    name="decade",
                    description="Preferred decade (e.g., 2020s, 90s, 80s)",
                    required=False
                )
            ]
        ),
        types.Prompt(
            name="discover_similar_music",
            description="Discover music similar to a given artist or track",
            arguments=[
                types.PromptArgument(
                    name="reference",
                    description="Artist name or track name to base recommendations on",
                    required=True
                ),
                types.PromptArgument(
                    name="discovery_level",
                    description="How adventurous: mainstream, balanced, or deep_cuts",
                    required=False
                )
            ]
        ),
        types.Prompt(
            name="party_playlist_generator",
            description="Generate a party playlist with crowd-pleasing tracks",
            arguments=[
                types.PromptArgument(
                    name="party_type",
                    description="Type of party (house_party, dance_party, dinner_party, etc.)",
                    required=True
                ),
                types.PromptArgument(
                    name="duration_hours",
                    description="Desired playlist duration in hours",
                    required=False
                )
            ]
        ),
        types.Prompt(
            name="workout_playlist_builder",
            description="Build an energizing workout playlist",
            arguments=[
                types.PromptArgument(
                    name="workout_type",
                    description="Type of workout (cardio, strength, yoga, running, etc.)",
                    required=True
                ),
                types.PromptArgument(
                    name="intensity",
                    description="Intensity level (low, medium, high)",
                    required=False
                )
            ]
        ),
        types.Prompt(
            name="focus_music_curator",
            description="Curate instrumental/ambient music for focus and productivity",
            arguments=[
                types.PromptArgument(
                    name="focus_type",
                    description="Type of focus work (coding, studying, writing, creative)",
                    required=True
                ),
                types.PromptArgument(
                    name="noise_level",
                    description="Preferred noise level (minimal, ambient, moderate)",
                    required=False
                )
            ]
        )
    ]
    logger.info(f"Available prompts: {[p.name for p in prompts]}")
    return prompts


@server.get_prompt()
async def handle_get_prompt(name: str, arguments: Optional[Dict[str, str]]) -> types.GetPromptResult:
    """Handle prompt requests with dynamic content generation."""
    logger.info(f"Getting prompt: {name} with arguments: {arguments}")
    
    try:
        if name == "create_mood_playlist":
            mood = arguments.get("mood", "happy") if arguments else "happy"
            genre = arguments.get("genre", "") if arguments else ""
            decade = arguments.get("decade", "") if arguments else ""
            
            genre_filter = f" genre:{genre}" if genre else ""
            year_filter = f" year:{decade}" if decade else ""
            
            prompt_content = f"""Create a {mood} mood playlist with the following approach:

1. Search for {mood} music{genre_filter}{year_filter}:
   - Use AdvancedSearch with query: "{mood} music" 
   - Apply filters: {{"genre": "{genre}", "year": "{decade}"}} if specified
   - Set include_recommendations: true for AI-powered suggestions

2. Build the playlist:
   - Create a new playlist with name: "{mood.title()} Vibes{f' - {genre.title()}' if genre else ''}"
   - Add 20-30 tracks that match the {mood} mood
   - Include a mix of popular and discovery tracks

3. Enhance the experience:
   - Add a descriptive playlist description
   - Consider track flow and energy progression
   - End with a satisfying conclusion track

The goal is to create a cohesive {mood} experience that resonates emotionally."""

            return types.GetPromptResult(
                description=f"Workflow for creating a {mood} mood playlist",
                messages=[
                    types.PromptMessage(
                        role="user",
                        content=types.TextContent(type="text", text=prompt_content)
                    )
                ]
            )
            
        elif name == "discover_similar_music":
            reference = arguments.get("reference", "your favorite artist") if arguments else "your favorite artist"
            discovery_level = arguments.get("discovery_level", "balanced") if arguments else "balanced"
            
            discovery_settings = {
                "mainstream": "focus on popular tracks and well-known artists",
                "balanced": "mix popular and lesser-known tracks",
                "deep_cuts": "prioritize lesser-known tracks and emerging artists"
            }
            
            prompt_content = f"""Discover music similar to "{reference}" with {discovery_level} discovery approach:

1. Initial Search:
   - Use Search tool with query: "{reference}"
   - Identify the artist/track ID for recommendations

2. Get Recommendations:
   - Use AdvancedSearch with include_recommendations: true
   - Base recommendations on the reference track/artist
   - Strategy: {discovery_settings.get(discovery_level, discovery_settings["balanced"])}

3. Expand Discovery:
   - Search for related artists and genres
   - Use filters to find music from similar time periods
   - Look for collaborations and remixes

4. Create Discovery Collection:
   - Organize findings into a "Similar to {reference}" playlist
   - Include the original reference for context
   - Add 15-25 discovery tracks

This approach will help you explore music that shares DNA with "{reference}" while expanding your musical horizons."""

            return types.GetPromptResult(
                description=f"Music discovery workflow based on {reference}",
                messages=[
                    types.PromptMessage(
                        role="user", 
                        content=types.TextContent(type="text", text=prompt_content)
                    )
                ]
            )
            
        elif name == "party_playlist_generator":
            party_type = arguments.get("party_type", "house_party") if arguments else "house_party"
            duration = arguments.get("duration_hours", "3") if arguments else "3"
            
            tracks_needed = int(float(duration) * 15)  # ~15 tracks per hour
            
            prompt_content = f"""Generate a {party_type} playlist for {duration} hours:

1. Party Analysis:
   - Party type: {party_type}
   - Duration: {duration} hours (~{tracks_needed} tracks)
   - Target audience: mixed crowd, wide appeal

2. Music Selection Strategy:
   - Start: Welcoming, moderate energy tracks
   - Middle: Peak energy, crowd favorites, danceable hits
   - End: Wind-down tracks, sing-alongs

3. Search Approach:
   - Use AdvancedSearch with query: "party dance hits"
   - Include filters for different decades (80s, 90s, 2000s, 2010s, 2020s)
   - Set include_recommendations: true for crowd-pleasers

4. Playlist Construction:
   - Name: "{party_type.replace('_', ' ').title()} Mix"
   - Mix genres: pop, dance, hip-hop, rock classics
   - Avoid explicit content for mixed crowds
   - Test energy flow and transitions

Goal: Create an irresistible {party_type} soundtrack that keeps everyone engaged."""

            return types.GetPromptResult(
                description=f"Party playlist generator for {party_type}",
                messages=[
                    types.PromptMessage(
                        role="user",
                        content=types.TextContent(type="text", text=prompt_content)
                    )
                ]
            )
            
        elif name == "workout_playlist_builder":
            workout_type = arguments.get("workout_type", "cardio") if arguments else "cardio"
            intensity = arguments.get("intensity", "high") if arguments else "high"
            
            prompt_content = f"""Build an energizing {workout_type} playlist with {intensity} intensity:

1. Workout Analysis:
   - Type: {workout_type}
   - Intensity: {intensity}
   - BPM target: {"120-140" if workout_type == "cardio" else "100-130" if workout_type == "strength" else "80-100"}

2. Music Strategy:
   - Warm-up: Building energy (5 tracks)
   - Main workout: Peak energy, driving beats (15-20 tracks)
   - Cool-down: Recovery tempo (3-5 tracks)

3. Search Queries:
   - "workout motivation {intensity} energy"
   - "pump up {workout_type} music"
   - Use AdvancedSearch with genre filters: electronic, hip-hop, rock

4. Playlist Features:
   - Name: "{workout_type.title()} Power - {intensity.title()}"
   - Seamless energy progression
   - Motivational lyrics and driving beats
   - 45-60 minute duration

Transform your {workout_type} session with the perfect sonic fuel."""

            return types.GetPromptResult(
                description=f"Workout playlist builder for {workout_type}",
                messages=[
                    types.PromptMessage(
                        role="user",
                        content=types.TextContent(type="text", text=prompt_content)
                    )
                ]
            )
            
        elif name == "focus_music_curator":
            focus_type = arguments.get("focus_type", "coding") if arguments else "coding"
            noise_level = arguments.get("noise_level", "ambient") if arguments else "ambient"
            
            prompt_content = f"""Curate focus music for {focus_type} with {noise_level} sound level:

1. Focus Requirements:
   - Activity: {focus_type}
   - Sound level: {noise_level}
   - Goal: Enhance concentration without distraction

2. Music Characteristics:
   - Minimal vocals or instrumental only
   - Consistent tempo and mood
   - Non-intrusive but engaging
   - 1-3 hour duration for deep work

3. Search Strategy:
   - Query: "{focus_type} focus instrumental ambient"
   - Genres: ambient, electronic, classical, lo-fi
   - Use AdvancedSearch filters: instrumental preference
   - Include nature sounds and white noise elements

4. Curation Process:
   - Test tracks for distraction level
   - Organize by energy level (low to moderate)
   - Create seamless transitions
   - Name: "Deep Focus - {focus_type.title()}"

Build the perfect sonic environment for productive {focus_type} sessions."""

            return types.GetPromptResult(
                description=f"Focus music curation for {focus_type}",
                messages=[
                    types.PromptMessage(
                        role="user",
                        content=types.TextContent(type="text", text=prompt_content)
                    )
                ]
            )
            
        else:
            error = SpotifyMCPError.validation_error("name", f"Unknown prompt: {name}")
            raise error
            
    except Exception as e:
        logger.error(f"Error generating prompt {name}: {e}")
        raise SpotifyMCPError(
            SpotifyMCPErrorCode.UNKNOWN_ERROR,
            f"Failed to generate prompt: {str(e)}"
        )


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
        AdvancedSearch.as_tool(),
        Queue.as_tool(),
        GetInfo.as_tool(),
        PlaylistManage.as_tool(),
        PlaylistItems.as_tool(),
        UserPlaylists.as_tool(),
        PlaylistCover.as_tool(),
        BatchTrackInfo.as_tool(),
        BatchPlaylistOperations.as_tool(),
        RecommendationEngine.as_tool(),
        UserAnalytics.as_tool(),
        PaginatedSearch.as_tool(),
        PlaylistPagination.as_tool(),
        LibraryOperations.as_tool(),
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
                            error = SpotifyMCPError.validation_error("track_id", "must be a string if provided")
                            return [error.to_mcp_error()]
                        
                        try:
                            # Check for active device first
                            if not spotify_client.is_active_device():
                                raise SpotifyMCPError.no_active_device()
                            
                            spotify_client.start_playback(track_id=str(track_id) if track_id else None)
                            logger.info("Playback started successfully")
                            return [types.TextContent(
                                type="text",
                                text="Playback started successfully."
                            )]
                        except SpotifyException as e:
                            error = SpotifyMCPError.from_spotify_exception(e)
                            return [error.to_mcp_error()]
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
                    error = SpotifyMCPError.validation_error("query", "is required for search")
                    return [error.to_mcp_error()]
                
                if len(query.strip()) < 2:
                    error = SpotifyMCPError.validation_error("query", "must be at least 2 characters long")
                    return [error.to_mcp_error()]
                
                try:
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
                except SpotifyException as e:
                    error = SpotifyMCPError.from_spotify_exception(e)
                    return [error.to_mcp_error()]

            case "AdvancedSearch":
                logger.info(f"Performing advanced search with arguments: {arguments}")
                query = get_str_arg(arguments, "query")
                if not query:
                    error = SpotifyMCPError.validation_error("query", "is required for search")
                    return [error.to_mcp_error()]
                
                if len(query.strip()) < 2:
                    error = SpotifyMCPError.validation_error("query", "must be at least 2 characters long")
                    return [error.to_mcp_error()]
                
                try:
                    # Build advanced search query with filters
                    filters = arguments.get("filters", {}) or {}
                    
                    # Import utils.build_search_query here to avoid circular imports
                    from .utils import build_search_query
                    
                    enhanced_query = build_search_query(
                        query,
                        artist=filters.get("artist"),
                        track=filters.get("track"), 
                        album=filters.get("album"),
                        year=filters.get("year"),
                        year_range=tuple(filters["year_range"]) if filters.get("year_range") and len(filters["year_range"]) == 2 else None,
                        genre=filters.get("genre"),
                        is_hipster=filters.get("is_hipster", False),
                        is_new=filters.get("is_new", False)
                    )
                    
                    # Perform the search
                    search_results = spotify_client.search(
                        query=enhanced_query,
                        qtype=get_str_arg(arguments, "qtype", "track"),
                        limit=get_int_arg(arguments, "limit", 20)
                    )
                    
                    # Add recommendations if requested
                    if arguments.get("include_recommendations", False):
                        try:
                            # Get track IDs from search results for recommendations
                            track_ids = []
                            if "tracks" in search_results:
                                track_ids = [track.get("id") for track in search_results["tracks"][:5] if track.get("id")]
                            
                            if track_ids:
                                recommendations = spotify_client.recommendations(tracks=track_ids[:5], limit=10)
                                if recommendations and "tracks" in recommendations:
                                    from .utils import parse_search_results
                                    parsed_recs = parse_search_results({"tracks": {"items": recommendations["tracks"]}}, "track")
                                    search_results["recommendations"] = parsed_recs.get("tracks", [])
                        except Exception as e:
                            logger.warning(f"Failed to get recommendations: {e}")
                            # Don't fail the entire search if recommendations fail
                    
                    logger.info("Advanced search completed successfully")
                    return [types.TextContent(
                        type="text",
                        text=json.dumps(search_results, indent=2)
                    )]
                    
                except SpotifyException as e:
                    error = SpotifyMCPError.from_spotify_exception(e)
                    return [error.to_mcp_error()]

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
                    error = SpotifyMCPError.validation_error("item_id", "is required")
                    return [error.to_mcp_error()]
                
                try:
                    item_info = spotify_client.get_info(
                        item_id=item_id,
                        qtype=get_str_arg(arguments, "qtype", "track")
                    )
                    return [types.TextContent(
                        type="text",
                        text=json.dumps(item_info, indent=2)
                    )]
                except SpotifyException as e:
                    error = SpotifyMCPError.from_spotify_exception(e)
                    return [error.to_mcp_error()]

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

            case "BatchTrackInfo":
                track_ids = arguments.get("track_ids", [])
                if not track_ids or not isinstance(track_ids, list):
                    error = SpotifyMCPError.validation_error("track_ids", "must be a non-empty list")
                    return [error.to_mcp_error()]
                
                if len(track_ids) > 50:
                    error = SpotifyMCPError.validation_error("track_ids", "cannot exceed 50 tracks per request")
                    return [error.to_mcp_error()]
                
                include_audio_features = bool(arguments.get("include_audio_features", False))
                market = arguments.get("market")
                
                # Get basic track info
                tracks_info = spotify_client.sp.tracks(track_ids, market=market)
                
                result = {
                    "tracks": tracks_info.get("tracks", []),
                    "total_tracks": len(track_ids),
                    "market": market
                }
                
                # Add audio features if requested
                if include_audio_features:
                    audio_features = spotify_client.sp.audio_features(track_ids)
                    result["audio_features"] = audio_features
                
                return [types.TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]

            case "BatchPlaylistOperations":
                action = get_str_arg(arguments, "action")
                playlist_id = get_str_arg(arguments, "playlist_id")
                track_uris = arguments.get("track_uris", [])
                
                if not playlist_id:
                    error = SpotifyMCPError.validation_error("playlist_id", "is required")
                    return [error.to_mcp_error()]
                
                if not track_uris or not isinstance(track_uris, list):
                    error = SpotifyMCPError.validation_error("track_uris", "must be a non-empty list")
                    return [error.to_mcp_error()]
                
                if len(track_uris) > 100:
                    error = SpotifyMCPError.validation_error("track_uris", "cannot exceed 100 tracks per request")
                    return [error.to_mcp_error()]
                
                match action:
                    case "add_tracks":
                        position = arguments.get("position")
                        result = spotify_client.sp.playlist_add_items(
                            playlist_id, track_uris, position=position
                        )
                        return [types.TextContent(
                            type="text",
                            text=f"Added {len(track_uris)} tracks to playlist. Snapshot ID: {result.get('snapshot_id')}"
                        )]
                    case "remove_tracks":
                        snapshot_id = arguments.get("snapshot_id")
                        result = spotify_client.sp.playlist_remove_all_occurrences_of_items(
                            playlist_id, track_uris, snapshot_id=snapshot_id
                        )
                        return [types.TextContent(
                            type="text",
                            text=f"Removed {len(track_uris)} tracks from playlist. Snapshot ID: {result.get('snapshot_id')}"
                        )]
                    case "replace_tracks":
                        result = spotify_client.sp.playlist_replace_items(playlist_id, track_uris)
                        return [types.TextContent(
                            type="text",
                            text=f"Replaced playlist with {len(track_uris)} tracks. Snapshot ID: {result.get('snapshot_id')}"
                        )]
                    case _:
                        return [types.TextContent(
                            type="text",
                            text=f"Unknown batch operation: {action}. Supported actions are: add_tracks, remove_tracks, replace_tracks"
                        )]

            case "Recommendations":
                seed_tracks = arguments.get("seed_tracks", [])
                seed_artists = arguments.get("seed_artists", [])
                seed_genres = arguments.get("seed_genres", [])
                
                # Validate seeds (must have at least one, max 5 total)
                total_seeds = len(seed_tracks) + len(seed_artists) + len(seed_genres)
                if total_seeds == 0:
                    error = SpotifyMCPError.validation_error("seeds", "must provide at least one seed (track, artist, or genre)")
                    return [error.to_mcp_error()]
                
                if total_seeds > 5:
                    error = SpotifyMCPError.validation_error("seeds", "total seeds cannot exceed 5")
                    return [error.to_mcp_error()]
                
                # Build recommendation parameters
                rec_params = {
                    "seed_tracks": seed_tracks[:5],
                    "seed_artists": seed_artists[:5], 
                    "seed_genres": seed_genres[:5],
                    "limit": min(arguments.get("limit", 20), 100),
                    "market": arguments.get("market")
                }
                
                # Add audio feature targets
                audio_targets = [
                    "target_acousticness", "target_danceability", "target_energy",
                    "target_valence", "target_tempo", "min_popularity", "max_popularity"
                ]
                for target in audio_targets:
                    if target in arguments and arguments[target] is not None:
                        rec_params[target] = arguments[target]
                
                recommendations = spotify_client.sp.recommendations(**rec_params)
                
                return [types.TextContent(
                    type="text",
                    text=json.dumps(recommendations, indent=2)
                )]

            case "UserAnalytics":
                analysis_type = get_str_arg(arguments, "analysis_type")
                time_range = get_str_arg(arguments, "time_range", "medium_term")
                limit = min(get_int_arg(arguments, "limit", 20), 50)
                include_audio_features = bool(arguments.get("include_audio_features", False))
                
                match analysis_type:
                    case "top_artists":
                        top_artists = spotify_client.sp.current_user_top_artists(
                            limit=limit, time_range=time_range
                        )
                        result = {"type": "top_artists", "time_range": time_range, "data": top_artists}
                    case "top_tracks":
                        top_tracks = spotify_client.sp.current_user_top_tracks(
                            limit=limit, time_range=time_range
                        )
                        result = {"type": "top_tracks", "time_range": time_range, "data": top_tracks}
                        
                        if include_audio_features and top_tracks.get("items"):
                            track_ids = [track["id"] for track in top_tracks["items"] if track.get("id")]
                            if track_ids:
                                audio_features = spotify_client.sp.audio_features(track_ids)
                                result["audio_features"] = audio_features
                    case "recently_played":
                        recent = spotify_client.sp.current_user_recently_played(limit=limit)
                        result = {"type": "recently_played", "data": recent}
                        
                        if include_audio_features and recent.get("items"):
                            track_ids = [item["track"]["id"] for item in recent["items"] if item.get("track", {}).get("id")]
                            if track_ids:
                                audio_features = spotify_client.sp.audio_features(track_ids)
                                result["audio_features"] = audio_features
                    case "listening_stats":
                        # Combine top artists and tracks for comprehensive stats
                        top_artists = spotify_client.sp.current_user_top_artists(limit=10, time_range=time_range)
                        top_tracks = spotify_client.sp.current_user_top_tracks(limit=20, time_range=time_range)
                        recent = spotify_client.sp.current_user_recently_played(limit=50)
                        
                        result = {
                            "type": "listening_stats",
                            "time_range": time_range,
                            "top_artists": top_artists,
                            "top_tracks": top_tracks,
                            "recent_listening": recent
                        }
                        
                        if include_audio_features and top_tracks.get("items"):
                            track_ids = [track["id"] for track in top_tracks["items"] if track.get("id")]
                            if track_ids:
                                audio_features = spotify_client.sp.audio_features(track_ids)
                                result["audio_features"] = audio_features
                    case _:
                        return [types.TextContent(
                            type="text",
                            text=f"Unknown analysis type: {analysis_type}. Supported types are: top_artists, top_tracks, recently_played, listening_stats"
                        )]
                
                return [types.TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]

            case "PaginatedSearch":
                query = get_str_arg(arguments, "query")
                if not query:
                    error = SpotifyMCPError.validation_error("query", "is required")
                    return [error.to_mcp_error()]
                
                qtype = get_str_arg(arguments, "qtype", "track")
                limit = min(get_int_arg(arguments, "limit", 20), 50)
                offset = get_int_arg(arguments, "offset", 0)
                market = arguments.get("market")
                get_all_pages = bool(arguments.get("get_all_pages", False))
                max_results = min(get_int_arg(arguments, "max_results", 1000), 10000)
                
                if get_all_pages:
                    # Fetch all results with pagination
                    all_results = {"items": [], "total": 0, "pages_fetched": 0}
                    current_offset = offset
                    
                    while len(all_results["items"]) < max_results:
                        search_results = spotify_client.sp.search(
                            q=query, type=qtype, limit=limit, offset=current_offset, market=market
                        )
                        
                        search_key = f"{qtype}s"
                        if search_key not in search_results:
                            break
                            
                        page_items = search_results[search_key]["items"]
                        if not page_items:
                            break
                            
                        all_results["items"].extend(page_items)
                        all_results["total"] = search_results[search_key]["total"]
                        all_results["pages_fetched"] += 1
                        
                        current_offset += limit
                        
                        # Stop if we've reached the end
                        if len(page_items) < limit or current_offset >= search_results[search_key]["total"]:
                            break
                    
                    # Trim to max_results
                    all_results["items"] = all_results["items"][:max_results]
                    all_results["returned_items"] = len(all_results["items"])
                    
                    return [types.TextContent(
                        type="text",
                        text=json.dumps(all_results, indent=2)
                    )]
                else:
                    # Single page search
                    search_results = spotify_client.sp.search(
                        q=query, type=qtype, limit=limit, offset=offset, market=market
                    )
                    return [types.TextContent(
                        type="text",
                        text=json.dumps(search_results, indent=2)
                    )]

            case "PlaylistPagination":
                playlist_id = get_str_arg(arguments, "playlist_id")
                if not playlist_id:
                    error = SpotifyMCPError.validation_error("playlist_id", "is required")
                    return [error.to_mcp_error()]
                
                limit = min(get_int_arg(arguments, "limit", 50), 100)
                offset = get_int_arg(arguments, "offset", 0)
                get_all_tracks = bool(arguments.get("get_all_tracks", False))
                include_audio_features = bool(arguments.get("include_audio_features", False))
                fields = arguments.get("fields")
                
                if get_all_tracks:
                    # Fetch all tracks from playlist
                    all_tracks = {"items": [], "total": 0, "pages_fetched": 0}
                    current_offset = offset
                    
                    while True:
                        playlist_tracks = spotify_client.sp.playlist_items(
                            playlist_id, limit=limit, offset=current_offset, fields=fields
                        )
                        
                        if not playlist_tracks["items"]:
                            break
                            
                        all_tracks["items"].extend(playlist_tracks["items"])
                        all_tracks["total"] = playlist_tracks["total"]
                        all_tracks["pages_fetched"] += 1
                        
                        current_offset += limit
                        
                        if len(playlist_tracks["items"]) < limit or current_offset >= playlist_tracks["total"]:
                            break
                    
                    result = all_tracks
                    
                    # Add audio features if requested
                    if include_audio_features and result["items"]:
                        track_ids = []
                        for item in result["items"]:
                            if item.get("track", {}).get("id"):
                                track_ids.append(item["track"]["id"])
                        
                        if track_ids:
                            # Process in batches of 100
                            audio_features = []
                            for i in range(0, len(track_ids), 100):
                                batch = track_ids[i:i+100]
                                batch_features = spotify_client.sp.audio_features(batch)
                                audio_features.extend(batch_features)
                            result["audio_features"] = audio_features
                    
                    return [types.TextContent(
                        type="text",
                        text=json.dumps(result, indent=2)
                    )]
                else:
                    # Single page
                    playlist_tracks = spotify_client.sp.playlist_items(
                        playlist_id, limit=limit, offset=offset, fields=fields
                    )
                    
                    if include_audio_features and playlist_tracks["items"]:
                        track_ids = [item["track"]["id"] for item in playlist_tracks["items"] 
                                   if item.get("track", {}).get("id")]
                        if track_ids:
                            audio_features = spotify_client.sp.audio_features(track_ids)
                            playlist_tracks["audio_features"] = audio_features
                    
                    return [types.TextContent(
                        type="text",
                        text=json.dumps(playlist_tracks, indent=2)
                    )]

            case "LibraryOperations":
                operation = get_str_arg(arguments, "operation")
                if not operation:
                    error = SpotifyMCPError.validation_error("operation", "is required")
                    return [error.to_mcp_error()]
                
                limit = min(get_int_arg(arguments, "limit", 20), 50)
                offset = get_int_arg(arguments, "offset", 0)
                track_ids = arguments.get("track_ids", [])
                get_all_items = bool(arguments.get("get_all_items", False))
                include_audio_features = bool(arguments.get("include_audio_features", False))
                
                match operation:
                    case "get_saved_tracks":
                        if get_all_items:
                            all_tracks = {"items": [], "total": 0, "pages_fetched": 0}
                            current_offset = offset
                            
                            while True:
                                saved_tracks = spotify_client.sp.current_user_saved_tracks(
                                    limit=limit, offset=current_offset
                                )
                                
                                if not saved_tracks["items"]:
                                    break
                                    
                                all_tracks["items"].extend(saved_tracks["items"])
                                all_tracks["total"] = saved_tracks["total"]
                                all_tracks["pages_fetched"] += 1
                                
                                current_offset += limit
                                
                                if len(saved_tracks["items"]) < limit or current_offset >= saved_tracks["total"]:
                                    break
                            
                            result = all_tracks
                        else:
                            result = spotify_client.sp.current_user_saved_tracks(limit=limit, offset=offset)
                        
                        if include_audio_features and result["items"]:
                            track_ids_for_features = [item["track"]["id"] for item in result["items"] 
                                                    if item.get("track", {}).get("id")]
                            if track_ids_for_features:
                                # Process in batches for large collections
                                audio_features = []
                                for i in range(0, len(track_ids_for_features), 100):
                                    batch = track_ids_for_features[i:i+100]
                                    batch_features = spotify_client.sp.audio_features(batch)
                                    audio_features.extend(batch_features)
                                result["audio_features"] = audio_features
                        
                        return [types.TextContent(
                            type="text",
                            text=json.dumps(result, indent=2)
                        )]
                    
                    case "get_saved_albums":
                        if get_all_items:
                            all_albums = {"items": [], "total": 0, "pages_fetched": 0}
                            current_offset = offset
                            
                            while True:
                                saved_albums = spotify_client.sp.current_user_saved_albums(
                                    limit=limit, offset=current_offset
                                )
                                
                                if not saved_albums["items"]:
                                    break
                                    
                                all_albums["items"].extend(saved_albums["items"])
                                all_albums["total"] = saved_albums["total"]
                                all_albums["pages_fetched"] += 1
                                
                                current_offset += limit
                                
                                if len(saved_albums["items"]) < limit or current_offset >= saved_albums["total"]:
                                    break
                            
                            result = all_albums
                        else:
                            result = spotify_client.sp.current_user_saved_albums(limit=limit, offset=offset)
                        
                        return [types.TextContent(
                            type="text",
                            text=json.dumps(result, indent=2)
                        )]
                    
                    case "get_followed_artists":
                        # Note: Spotify's followed artists endpoint doesn't support offset pagination
                        followed = spotify_client.sp.current_user_followed_artists(limit=limit)
                        return [types.TextContent(
                            type="text",
                            text=json.dumps(followed, indent=2)
                        )]
                    
                    case "save_tracks":
                        if not track_ids or not isinstance(track_ids, list):
                            error = SpotifyMCPError.validation_error("track_ids", "required for save_tracks operation")
                            return [error.to_mcp_error()]
                        
                        if len(track_ids) > 50:
                            error = SpotifyMCPError.validation_error("track_ids", "cannot exceed 50 tracks per request")
                            return [error.to_mcp_error()]
                        
                        spotify_client.sp.current_user_saved_tracks_add(track_ids)
                        return [types.TextContent(
                            type="text",
                            text=f"Saved {len(track_ids)} tracks to library"
                        )]
                    
                    case "remove_tracks":
                        if not track_ids or not isinstance(track_ids, list):
                            error = SpotifyMCPError.validation_error("track_ids", "required for remove_tracks operation")
                            return [error.to_mcp_error()]
                        
                        if len(track_ids) > 50:
                            error = SpotifyMCPError.validation_error("track_ids", "cannot exceed 50 tracks per request")
                            return [error.to_mcp_error()]
                        
                        spotify_client.sp.current_user_saved_tracks_delete(track_ids)
                        return [types.TextContent(
                            type="text",
                            text=f"Removed {len(track_ids)} tracks from library"
                        )]
                    
                    case _:
                        return [types.TextContent(
                            type="text",
                            text=f"Unknown library operation: {operation}. Supported operations are: get_saved_tracks, get_saved_albums, get_followed_artists, save_tracks, remove_tracks"
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
