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
def search_tracks(query: str, qtype: str = "track", limit: int = 10) -> List[Track]:
    """Search Spotify for tracks, albums, artists, or playlists.
    
    Args:
        query: Search query
        qtype: Type ('track', 'album', 'artist', 'playlist')
        limit: Max results
    """
    try:
        result = spotify_client.search(q=query, type=qtype, limit=limit)
        
        tracks = []
        if qtype == "track" and result.get("tracks", {}).get("items"):
            tracks = [parse_track(item) for item in result["tracks"]["items"]]
        else:
            # Convert other types to track-like format for consistency
            items_key = f"{qtype}s"
            if result.get(items_key, {}).get("items"):
                for item in result[items_key]["items"]:
                    track = Track(
                        name=item["name"],
                        id=item["id"],
                        artist=item.get("artists", [{}])[0].get("name", "Unknown") if qtype != "artist" else item["name"],
                        external_urls=item.get("external_urls")
                    )
                    tracks.append(track)
        
        return tracks
        
    except SpotifyException as e:
        raise convert_spotify_error(e)


@mcp.tool()
def manage_queue(action: str, track_id: Optional[str] = None) -> Dict[str, Any]:
    """Manage playback queue.
    
    Args:
        action: Action ('add' or 'get')
        track_id: Track ID (for 'add')
    """
    try:
        if action == "add":
            if not track_id:
                raise ValueError("track_id required for add action")
            spotify_client.add_to_queue(f"spotify:track:{track_id}")
            return {"status": "success", "message": f"Added track to queue"}
            
        elif action == "get":
            result = spotify_client.queue()
            
            queue_tracks = []
            if result.get("queue"):
                queue_tracks = [parse_track(item) for item in result["queue"]]
            
            return {
                "currently_playing": parse_track(result["currently_playing"]).model_dump() if result.get("currently_playing") else None,
                "queue": [track.model_dump() for track in queue_tracks]
            }
        else:
            raise ValueError(f"Invalid action: {action}")
            
    except SpotifyException as e:
        raise convert_spotify_error(e)


@mcp.tool() 
def get_item_info(item_id: str, qtype: str = "track") -> Dict[str, Any]:
    """Get detailed information about a Spotify item.
    
    Args:
        item_id: Item ID
        qtype: Type ('track', 'album', 'artist', 'playlist')
    """
    try:
        if qtype == "track":
            result = spotify_client.track(item_id)
            return parse_track(result).model_dump()
            
        elif qtype == "artist":
            result = spotify_client.artist(item_id)
            top_tracks = spotify_client.artist_top_tracks(item_id)
            
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
            
        elif qtype == "playlist":
            result = spotify_client.playlist(item_id)
            tracks_result = spotify_client.playlist_tracks(item_id, limit=50)
            
            tracks = []
            for item in tracks_result.get("items", []):
                if item["track"]:
                    tracks.append(parse_track(item["track"]))
            
            playlist = Playlist(
                name=result["name"],
                id=result["id"],
                owner=result.get("owner", {}).get("display_name"),
                description=result.get("description"),
                tracks=tracks,
                total_tracks=result.get("tracks", {}).get("total"),
                public=result.get("public")
            )
            
            return playlist.model_dump()
            
        else:
            raise ValueError(f"Unsupported item type: {qtype}")
            
    except SpotifyException as e:
        raise convert_spotify_error(e)


@mcp.tool()
def create_playlist(name: str, description: str = "", public: bool = True) -> Playlist:
    """Create a new Spotify playlist.
    
    Args:
        name: Playlist name
        description: Playlist description
        public: Whether playlist is public
    """
    try:
        user = spotify_client.current_user()
        result = spotify_client.user_playlist_create(
            user["id"], name, public=public, description=description
        )
        
        return Playlist(
            name=result["name"],
            id=result["id"],
            owner=result.get("owner", {}).get("display_name"),
            description=result.get("description"),
            tracks=[],
            total_tracks=0,
            public=result.get("public")
        )
        
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
def get_user_playlists(limit: int = 20) -> List[Playlist]:
    """Get current user's playlists.
    
    Args:
        limit: Max playlists to return
    """
    try:
        result = spotify_client.current_user_playlists(limit=limit)
        
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
            
        return playlists
        
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

Use search_tracks to find songs, then create_playlist and add_tracks_to_playlist to build it.

Consider:
1. Energy level for {mood} mood
2. {f"Focus on {genre}" if genre else "Genre variety"}
3. {f"Songs from {decade}" if decade else "Mix of eras"}
4. 15-20 songs with good flow"""


if __name__ == "__main__":
    mcp.run()