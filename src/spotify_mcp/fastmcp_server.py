"""
Modern FastMCP-based Spotify MCP Server.
Clean, simple implementation using FastMCP's automatic features.
"""

import json
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel
from spotipy import SpotifyException

import spotify_mcp.spotify_api as spotify_api
from spotify_mcp.errors import convert_spotify_error


# Create FastMCP app
mcp = FastMCP("Spotify MCP")

# Initialize Spotify client  
_client_wrapper = spotify_api.Client()
spotify_client = _client_wrapper.sp  # Use spotipy client directly


# Data models for structured output
class Track(BaseModel):
    """A Spotify track with metadata."""
    name: str
    id: str
    artist: str
    artists: Optional[List[str]] = None
    album: Optional[str] = None
    duration_ms: Optional[int] = None
    popularity: Optional[int] = None
    external_urls: Optional[Dict[str, str]] = None


class PlaybackState(BaseModel):
    """Current playback state."""
    is_playing: bool
    track: Optional[Track] = None
    device: Optional[str] = None
    volume: Optional[int] = None
    shuffle: bool = False
    repeat: str = "off"
    progress_ms: Optional[int] = None


class Playlist(BaseModel):
    """A Spotify playlist."""
    name: str
    id: str
    owner: Optional[str] = None
    description: Optional[str] = None
    tracks: Optional[List[Track]] = None
    total_tracks: Optional[int] = None
    public: Optional[bool] = None


class Artist(BaseModel):
    """A Spotify artist."""
    name: str
    id: str
    genres: Optional[List[str]] = None
    popularity: Optional[int] = None
    followers: Optional[int] = None


def parse_track(item: Dict[str, Any]) -> Track:
    """Parse Spotify track data into Track model."""
    return Track(
        name=item["name"],
        id=item["id"],
        artist=item["artists"][0]["name"] if item.get("artists") else "Unknown",
        artists=[a["name"] for a in item.get("artists", [])],
        album=item.get("album", {}).get("name"),
        duration_ms=item.get("duration_ms"),
        popularity=item.get("popularity"),
        external_urls=item.get("external_urls")
    )


def get_playlist_tracks_paginated(playlist_id: str, limit: Optional[int] = None, offset: int = 0) -> List[Track]:
    """Get playlist tracks with proper pagination support.
    
    Args:
        playlist_id: Spotify playlist ID
        limit: Maximum number of tracks to return (None for all)
        offset: Number of tracks to skip
    
    Returns:
        List of Track objects
    """
    tracks = []
    current_offset = offset
    batch_size = min(limit, 100) if limit else 100  # Spotify API max is 100 per request
    remaining = limit
    
    while True:
        # Determine how many to fetch in this batch
        batch_limit = min(batch_size, remaining) if remaining else batch_size
        
        # Get playlist tracks with pagination
        tracks_result = spotify_client.playlist_tracks(
            playlist_id,
            limit=batch_limit,
            offset=current_offset
        )
        
        if not tracks_result or not tracks_result.get('items'):
            break
            
        # Parse and add tracks
        batch_tracks = []
        for item in tracks_result['items']:
            if item and item.get('track'):
                batch_tracks.append(parse_track(item['track']))
                
        tracks.extend(batch_tracks)
        
        # Update remaining count if we have a limit
        if remaining:
            remaining -= len(batch_tracks)
            if remaining <= 0:
                break
        
        # Check if we've reached the end
        if len(tracks_result['items']) < batch_limit or not tracks_result.get('next'):
            break
            
        current_offset += len(tracks_result['items'])
        
        # Safety check to prevent infinite loops
        if current_offset > 10000:
            break
    
    return tracks


# === TOOLS ===

@mcp.tool()
def playback_control(action: str, track_id: Optional[str] = None, num_skips: int = 1) -> PlaybackState:
    """Control Spotify playback.
    
    Args:
        action: Action ('get', 'start', 'pause', 'skip')
        track_id: Track ID to play (for 'start')
        num_skips: Number of tracks to skip
    """
    try:
        if action == "get":
            result = spotify_client.current_user_playing_track()
        elif action == "start":
            if track_id:
                spotify_client.start_playback(uris=[f"spotify:track:{track_id}"])
            else:
                spotify_client.start_playback()
            result = spotify_client.current_user_playing_track()
        elif action == "pause":
            spotify_client.pause_playback()
            result = spotify_client.current_user_playing_track()
        elif action == "skip":
            for _ in range(num_skips):
                spotify_client.next_track()
            result = spotify_client.current_user_playing_track()
        else:
            raise ValueError(f"Invalid action: {action}")
        
        # Parse result
        track = None
        if result and result.get("item"):
            track = parse_track(result["item"])
            
        return PlaybackState(
            is_playing=result.get("is_playing", False) if result else False,
            track=track,
            device=result.get("device", {}).get("name") if result and result.get("device") else None,
            volume=result.get("device", {}).get("volume_percent") if result and result.get("device") else None,
            shuffle=result.get("shuffle_state", False) if result else False,
            repeat=result.get("repeat_state", "off") if result else "off",
            progress_ms=result.get("progress_ms") if result else None
        )
        
    except SpotifyException as e:
        raise convert_spotify_error(e)


@mcp.tool()
def search_tracks(query: str, qtype: str = "track", limit: int = 10, offset: int = 0) -> Dict[str, Any]:
    """Search Spotify for tracks, albums, artists, or playlists.
    
    Args:
        query: Search query
        qtype: Type ('track', 'album', 'artist', 'playlist')
        limit: Max results per page (1-50, default 10)
        offset: Number of results to skip for pagination (default 0)
        
    Returns:
        Dict with 'items' (list of tracks) and pagination info ('total', 'limit', 'offset')
        
    Note: For large result sets, use offset to paginate through results.
    Example: offset=0 gets results 1-10, offset=10 gets results 11-20, etc.
    """
    try:
        # Validate limit (Spotify API accepts 1-50)
        limit = max(1, min(50, limit))
        
        result = spotify_client.search(q=query, type=qtype, limit=limit, offset=offset)
        
        tracks = []
        items_key = f"{qtype}s"
        result_section = result.get(items_key, {})
        
        if qtype == "track" and result_section.get("items"):
            tracks = [parse_track(item) for item in result_section["items"]]
        else:
            # Convert other types to track-like format for consistency
            if result_section.get("items"):
                for item in result_section["items"]:
                    track = Track(
                        name=item["name"],
                        id=item["id"],
                        artist=item.get("artists", [{}])[0].get("name", "Unknown") if qtype != "artist" else item["name"],
                        external_urls=item.get("external_urls")
                    )
                    tracks.append(track)
        
        return {
            "items": tracks,
            "total": result_section.get("total", 0),
            "limit": result_section.get("limit", limit),
            "offset": result_section.get("offset", offset),
            "next": result_section.get("next"),
            "previous": result_section.get("previous")
        }
        
    except SpotifyException as e:
        raise convert_spotify_error(e)


@mcp.tool()
def add_to_queue(track_id: str) -> Dict[str, str]:
    """Add a track to the playback queue.
    
    Args:
        track_id: Spotify track ID to add to queue
        
    Returns:
        Dict with status and message
    """
    try:
        spotify_client.add_to_queue(f"spotify:track:{track_id}")
        return {"status": "success", "message": f"Added track to queue"}
    except SpotifyException as e:
        raise convert_spotify_error(e)


@mcp.tool()
def get_queue() -> Dict[str, Any]:
    """Get the current playback queue.
    
    Returns:
        Dict with currently_playing track and queue of upcoming tracks
    """
    try:
        result = spotify_client.queue()
        
        queue_tracks = []
        if result.get("queue"):
            queue_tracks = [parse_track(item) for item in result["queue"]]
        
        return {
            "currently_playing": parse_track(result["currently_playing"]).model_dump() if result.get("currently_playing") else None,
            "queue": [track.model_dump() for track in queue_tracks]
        }
    except SpotifyException as e:
        raise convert_spotify_error(e)


@mcp.tool()
def get_track_info(track_id: str) -> Dict[str, Any]:
    """Get detailed information about a Spotify track.
    
    Args:
        track_id: Spotify track ID
        
    Returns:
        Dict with complete track metadata
    """
    try:
        result = spotify_client.track(track_id)
        return parse_track(result).model_dump()
    except SpotifyException as e:
        raise convert_spotify_error(e)


@mcp.tool()
def get_artist_info(artist_id: str) -> Dict[str, Any]:
    """Get detailed information about a Spotify artist.
    
    Args:
        artist_id: Spotify artist ID
        
    Returns:
        Dict with artist info and top tracks
    """
    try:
        result = spotify_client.artist(artist_id)
        top_tracks = spotify_client.artist_top_tracks(artist_id)
        
        artist = Artist(
            name=result["name"],
            id=result["id"],
            genres=result.get("genres", []),
            popularity=result.get("popularity"),
            followers=result.get("followers", {}).get("total")
        )
        
        tracks = [parse_track(track) for track in top_tracks.get("tracks", [])[:10]]
        
        return {
            "artist": artist.model_dump(),
            "top_tracks": [track.model_dump() for track in tracks]
        }
    except SpotifyException as e:
        raise convert_spotify_error(e)


@mcp.tool()
def get_playlist_info(playlist_id: str) -> Dict[str, Any]:
    """Get basic information about a Spotify playlist.
    
    Args:
        playlist_id: Spotify playlist ID
        
    Returns:
        Dict with playlist metadata (no tracks - use get_playlist_tracks for tracks)
        
    Note: This returns playlist info only. For tracks, use get_playlist_tracks 
    which supports full pagination for large playlists.
    """
    try:
        result = spotify_client.playlist(playlist_id, fields="id,name,description,owner,public,tracks.total")
        
        playlist = Playlist(
            name=result["name"],
            id=result["id"],
            owner=result.get("owner", {}).get("display_name"),
            description=result.get("description"),
            tracks=None,  # No tracks - use get_playlist_tracks
            total_tracks=result.get("tracks", {}).get("total"),
            public=result.get("public")
        )
        
        return playlist.model_dump()
    except SpotifyException as e:
        raise convert_spotify_error(e)


@mcp.tool()
def create_playlist(name: str, description: str = "", public: bool = True) -> Dict[str, Any]:
    """Create a new Spotify playlist.
    
    Args:
        name: Playlist name
        description: Playlist description (default: empty)
        public: Whether playlist is public (default: True)
        
    Returns:
        Dict with created playlist information
    """
    try:
        user = spotify_client.current_user()
        result = spotify_client.user_playlist_create(
            user["id"], name, public=public, description=description
        )
        
        playlist = Playlist(
            name=result["name"],
            id=result["id"],
            owner=result.get("owner", {}).get("display_name"),
            description=result.get("description"),
            tracks=[],
            total_tracks=0,
            public=result.get("public")
        )
        
        return playlist.model_dump()
        
    except SpotifyException as e:
        raise convert_spotify_error(e)


@mcp.tool()
def add_tracks_to_playlist(playlist_id: str, track_uris: List[str]) -> Dict[str, str]:
    """Add tracks to a playlist.
    
    Args:
        playlist_id: Playlist ID
        track_uris: List of track URIs (up to 100)
    """
    try:
        # Convert track IDs to URIs if needed
        uris = [uri if uri.startswith("spotify:track:") else f"spotify:track:{uri}" for uri in track_uris]
        
        spotify_client.playlist_add_items(playlist_id, uris)
        return {"status": "success", "message": f"Added {len(uris)} tracks to playlist"}
        
    except SpotifyException as e:
        raise convert_spotify_error(e)


@mcp.tool()
def get_user_playlists(limit: int = 20, offset: int = 0) -> Dict[str, Any]:
    """Get current user's playlists with pagination support.
    
    Args:
        limit: Max playlists to return per page (1-50, default 20)
        offset: Number of playlists to skip for pagination (default 0)
        
    Returns:
        Dict with 'items' (list of playlists) and pagination info ('total', 'limit', 'offset')
        
    Note: For users with many playlists, use offset to paginate through results.
    Example: offset=0 gets playlists 1-20, offset=20 gets playlists 21-40, etc.
    """
    try:
        # Validate limit (Spotify API accepts 1-50)
        limit = max(1, min(50, limit))
        
        result = spotify_client.current_user_playlists(limit=limit, offset=offset)
        
        playlists = []
        for item in result.get("items", []):
            playlist = Playlist(
                name=item["name"],
                id=item["id"],
                owner=item.get("owner", {}).get("display_name"),
                description=item.get("description"),
                total_tracks=item.get("tracks", {}).get("total"),
                public=item.get("public")
            )
            playlists.append(playlist)
            
        return {
            "items": playlists,
            "total": result.get("total", 0),
            "limit": result.get("limit", limit),
            "offset": result.get("offset", offset),
            "next": result.get("next"),
            "previous": result.get("previous")
        }
        
    except SpotifyException as e:
        raise convert_spotify_error(e)


@mcp.tool()
def get_playlist_tracks(playlist_id: str, limit: Optional[int] = None, offset: int = 0) -> Dict[str, Any]:
    """Get tracks from a playlist with full pagination support.
    
    Args:
        playlist_id: Playlist ID
        limit: Max tracks to return (None for all tracks, up to 10,000 safety limit)
        offset: Number of tracks to skip for pagination (default 0)
        
    Returns:
        Dict with 'items' (list of tracks), 'total', 'limit', 'offset'
        
    Note: Large playlists require pagination. Use limit/offset to get specific ranges:
    - Get first 100: limit=100, offset=0
    - Get next 100: limit=100, offset=100  
    - Get all tracks: limit=None (use with caution on very large playlists)
    """
    try:
        tracks = get_playlist_tracks_paginated(playlist_id, limit, offset)
        
        # Get total track count from playlist info
        playlist_info = spotify_client.playlist(playlist_id, fields="tracks.total")
        total_tracks = playlist_info.get("tracks", {}).get("total", len(tracks))
        
        return {
            "items": tracks,
            "total": total_tracks,
            "limit": limit,
            "offset": offset,
            "returned": len(tracks)
        }
        
    except SpotifyException as e:
        raise convert_spotify_error(e)


@mcp.tool()
def remove_tracks_from_playlist(playlist_id: str, track_uris: List[str]) -> Dict[str, str]:
    """Remove tracks from a playlist.
    
    Args:
        playlist_id: Playlist ID
        track_uris: List of track URIs to remove
    """
    try:
        # Convert track IDs to URIs if needed
        uris = [uri if uri.startswith("spotify:track:") else f"spotify:track:{uri}" for uri in track_uris]
        
        spotify_client.playlist_remove_all_occurrences_of_items(playlist_id, uris)
        return {"status": "success", "message": f"Removed {len(uris)} tracks from playlist"}
        
    except SpotifyException as e:
        raise convert_spotify_error(e)


@mcp.tool()
def modify_playlist_details(playlist_id: str, name: Optional[str] = None, description: Optional[str] = None, public: Optional[bool] = None) -> Dict[str, str]:
    """Modify playlist details.
    
    Args:
        playlist_id: Playlist ID
        name: New playlist name (optional)
        description: New playlist description (optional)
        public: Whether playlist should be public (optional)
    """
    try:
        if not name and not description and public is None:
            raise ValueError("At least one of name, description, or public must be provided")
            
        spotify_client.playlist_change_details(
            playlist_id, 
            name=name, 
            description=description,
            public=public
        )
        return {"status": "success", "message": "Playlist details updated successfully"}
        
    except SpotifyException as e:
        raise convert_spotify_error(e)


# === RESOURCES ===

@mcp.resource("spotify://user/current")
def current_user() -> str:
    """Current user's profile."""
    try:
        user = spotify_client.current_user()
        return json.dumps({
            "id": user.get("id"),
            "display_name": user.get("display_name"),
            "followers": user.get("followers", {}).get("total"),
            "country": user.get("country"),
            "product": user.get("product")
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.resource("spotify://playback/current")
def current_playback_resource() -> str:
    """Current playback state."""
    try:
        playback = spotify_client.current_user_playing_track()
        if not playback:
            return json.dumps({"status": "no_playback"})
            
        track_info = playback.get("item", {})
        return json.dumps({
            "is_playing": playback.get("is_playing", False),
            "track": {
                "name": track_info.get("name"),
                "artist": track_info.get("artists", [{}])[0].get("name"),
                "album": track_info.get("album", {}).get("name"),
                "id": track_info.get("id")
            } if track_info else None,
            "device": playback.get("device", {}).get("name"),
            "progress_ms": playback.get("progress_ms")
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


# === PROMPTS ===

@mcp.prompt()
def create_mood_playlist(mood: str, genre: str = "", decade: str = "") -> str:
    """Create a playlist based on mood and preferences."""
    prompt = f"Create a Spotify playlist for a {mood} mood"
    
    if genre:
        prompt += f" with {genre} music"
    if decade:
        prompt += f" from the {decade}"
        
    return f"""{prompt}.

Workflow:
1. Use search_tracks with different queries to find diverse songs
   - For large search results, use offset parameter to get more options
   - Example: search_tracks("upbeat pop", limit=20, offset=0) then offset=20 for more
2. Create playlist with create_playlist
3. Add tracks with add_tracks_to_playlist (supports up to 100 tracks per call)

Pagination Tips:
- Search results are paginated (limit=1-50, use offset for more results)  
- For variety, try multiple search queries with different offsets
- Large playlists: batch add tracks in groups of 50-100

Consider:
1. Energy level for {mood} mood
2. {f"Focus on {genre}" if genre else "Genre variety"}
3. {f"Songs from {decade}" if decade else "Mix of eras"}
4. 15-20 songs with good flow"""


@mcp.prompt()
def analyze_large_playlist(playlist_id: str, analysis_type: str = "overview") -> str:
    """Analyze a large playlist efficiently using pagination."""
    return f"""Analyze playlist {playlist_id} with focus on {analysis_type}.

For large playlists (>100 tracks), use pagination to analyze efficiently:

Step 1: Get overview
- Use get_item_info(playlist_id, "playlist") for basic info and first 50 tracks
- Check total_tracks to understand playlist size

Step 2: Full analysis (if needed)
- For playlists >100 tracks, use get_playlist_tracks with pagination:
  - get_playlist_tracks(playlist_id, limit=100, offset=0) for first 100
  - get_playlist_tracks(playlist_id, limit=100, offset=100) for next 100
  - Continue until you have all tracks or sufficient sample

Step 3: Analysis
Based on analysis_type:
- "overview": Basic stats, genres, mood distribution  
- "detailed": Track-by-track analysis, recommendations
- "duplicates": Find duplicate tracks across large playlist
- "mood": Analyze mood/energy progression through playlist

Pagination Benefits:
- Memory efficient for 1000+ track playlists
- Can stop early if sufficient data collected
- Allows progressive analysis with user feedback"""


@mcp.prompt()  
def discover_music_systematically(seed_query: str, exploration_depth: str = "medium") -> str:
    """Systematically discover music using search pagination."""
    return f"""Discover music related to "{seed_query}" with {exploration_depth} exploration.

Search Strategy with Pagination:
1. Initial search: search_tracks("{seed_query}", limit=20, offset=0)
2. Diverse results: Use different offsets to explore deeper:
   - Popular results: offset=0-20 
   - Hidden gems: offset=20-40, offset=40-60
   - Deep cuts: offset=80-100+

3. Related searches with pagination:
   - Artist names from initial results
   - Album names from initial results  
   - Genre + decade combinations
   - Similar mood/energy descriptors

Exploration Depth:
- "light": 2-3 search queries, 20 results each
- "medium": 5-6 search queries, explore offsets 0-40
- "deep": 10+ search queries, explore offsets 0-100+

Pagination Best Practices:
- Start with limit=20 for quick overview
- Use offset to avoid duplicate results
- Try different query variations rather than just advancing offset
- Stop when you find enough quality matches

Output: Curated list of 15-25 discovered tracks with variety"""


if __name__ == "__main__":
    mcp.run()