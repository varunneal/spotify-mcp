from typing import List, Optional

import mcp.types as types
from pydantic import BaseModel, Field


class ToolModel(BaseModel):
    @classmethod
    def as_tool(cls):
        return types.Tool(
            name="Spotify" + cls.__name__,
            description=cls.__doc__,
            inputSchema=cls.model_json_schema()
        )


class Playback(ToolModel):
    """Manages the current playback with the following actions:
    - get: Get information about user's current track.
    - start: Starts playing new item or resumes current playback if called with no uri.
    - pause: Pauses current playback.
    - skip: Skips current track.
    - previous: Skips to the previous track in playback history.
    """
    action: str = Field(description="Action to perform: 'get', 'start', 'pause', 'skip', or 'previous'.")
    spotify_uri: Optional[str] = Field(default=None, description="Spotify uri of item to play for 'start' action. " +
                                                                 "If omitted, resumes current playback.")
    num_skips: Optional[int] = Field(default=1, description="Number of tracks to skip for `skip` action.")


class Queue(ToolModel):
    """Manage the playback queue - get the queue or add tracks."""
    action: str = Field(description="Action to perform: 'add' or 'get'.")
    track_id: Optional[str] = Field(default=None, description="Track ID to add to queue (required for add action)")


class GetInfo(ToolModel):
    """Get detailed information about a Spotify item (track, album, artist, or playlist)."""
    item_uri: str = Field(description="URI of the item to get information about. " +
                                      "If 'playlist' or 'album', returns its tracks. " +
                                      "If 'artist', returns albums and top tracks.")


class Search(ToolModel):
    """Search for tracks, albums, artists, or playlists on Spotify."""
    query: str = Field(description="query term")
    qtype: Optional[str] = Field(default="track",
                                 description="Type of items to search for (track, album, artist, playlist, " +
                                             "or comma-separated combination)")
    limit: Optional[int] = Field(default=10, description="Maximum number of items to return")


class Playlist(ToolModel):
    """Manage Spotify playlists.
    - get: Get a list of user's playlists.
    - get_tracks: Get tracks in a specific playlist.
    - add_tracks: Add tracks to a specific playlist.
    - remove_tracks: Remove tracks from a specific playlist.
    - change_details: Change details of a specific playlist.
    - create: Create a new playlist.
    """
    action: str = Field(
        description="Action to perform: 'get', 'get_tracks', 'add_tracks', 'remove_tracks', 'change_details', 'create'.")
    playlist_id: Optional[str] = Field(default=None, description="ID of the playlist to manage.")
    track_ids: Optional[List[str]] = Field(default=None, description="List of track IDs to add/remove.")
    name: Optional[str] = Field(default=None, description="Name for the playlist (required for create and change_details).")
    description: Optional[str] = Field(default=None, description="Description for the playlist.")
    public: Optional[bool] = Field(default=True, description="Whether the playlist should be public (for create action).")


class History(ToolModel):
    """Get the user's recently played tracks with optional time cursors."""
    limit: Optional[int] = Field(default=20, description="Max items (1-50).")
    after: Optional[int] = Field(default=None, description="Unix ms cursor; return items played after this timestamp.")
    before: Optional[int] = Field(default=None, description="Unix ms cursor; return items played before this timestamp. Mutually exclusive with `after`.")


class TasteProfile(ToolModel):
    """Inspect the user's listening taste: top artists, top tracks, and genre histogram.
    - profile: full profile (top artists + tracks + genre histogram).
    - tracks: only top tracks.
    - artists: only top artists.
    """
    action: Optional[str] = Field(default="profile", description="'profile', 'tracks', or 'artists'.")
    time_range: Optional[str] = Field(default="medium_term", description="'short_term' (~4 weeks), 'medium_term' (~6 months), or 'long_term' (years).")
    limit: Optional[int] = Field(default=20, description="Max items (1-50).")
    refresh: Optional[bool] = Field(default=False, description="Bypass the 30-day cache (only applies to 'profile' action).")


class SmartPlay(ToolModel):
    """Pick and (by default) start playback of the best Spotify item for a natural-language query.
    Ranks candidates by name overlap, editorial curation, and the user's taste profile.
    Example: query='chill focus beats for late night'.
    """
    query: str = Field(description="Natural-language description of what to play.")
    prefer: Optional[str] = Field(default=None, description="Bias toward 'track', 'album', or 'playlist'.")
    auto_play: Optional[bool] = Field(default=True, description="If true, immediately start playback of the top pick.")
    limit: Optional[int] = Field(default=10, description="Candidates per type from Spotify search (1-20).")
