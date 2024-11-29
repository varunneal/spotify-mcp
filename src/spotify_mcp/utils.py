import json
import os
from typing import Optional, List, Dict
from urllib.parse import quote

import spotipy
from dotenv import load_dotenv
from spotipy import SpotifyException
from spotipy.oauth2 import SpotifyOAuth


import functools
import inspect
from typing import Callable, Any, TypeVar, cast

T = TypeVar('T')


def parse_track(track_item: dict) -> dict:
    narrowed_item = {
        'name': track_item['name'],
        'id': track_item['id'],
    }

    if track_item.get('is_playing', False):
        narrowed_item['is_playing'] = True
    if not track_item.get('is_playable', True):
        narrowed_item['is_playable'] = False

    artists = [a['name'] for a in track_item['artists']]

    if len(artists) == 1:
        narrowed_item['artist'] = artists[0]
    else:
        narrowed_item['artists'] = artists

    return narrowed_item


def parse_search_results(results: Dict, qtype: str):
    _results = []
    if qtype == 'track':
        for idx, item in enumerate(results['tracks']['items']):
            _results.append(parse_track(item))
            # print(item['name'], item.keys())
        return _results

def build_search_query(base_query: str,
                       artist: Optional[str] = None,
                       track: Optional[str] = None,
                       album: Optional[str] = None,
                       year: Optional[str] = None,
                       year_range: Optional[tuple[int, int]] = None,
                       # upc: Optional[str] = None,
                       # isrc: Optional[str] = None,
                       genre: Optional[str] = None,
                       is_hipster: bool = False,
                       is_new: bool = False
                       ) -> str:
    """
    Build a search query string with optional filters.

    Args:
        base_query: Base search term
        artist: Artist name filter
        track: Track name filter
        album: Album name filter
        year: Specific year filter
        year_range: Tuple of (start_year, end_year) for year range filter
        genre: Genre filter
        is_hipster: Filter for lowest 10% popularity albums
        is_new: Filter for albums released in past two weeks

    Returns:
        Encoded query string with applied filters
    """
    filters = []

    if artist:
        filters.append(f"artist:{artist}")
    if track:
        filters.append(f"track:{track}")
    if album:
        filters.append(f"album:{album}")
    if year:
        filters.append(f"year:{year}")
    if year_range:
        filters.append(f"year:{year_range[0]}-{year_range[1]}")
    if genre:
        filters.append(f"genre:{genre}")
    if is_hipster:
        filters.append("tag:hipster")
    if is_new:
        filters.append("tag:new")

    query_parts = [base_query] + filters
    return quote(" ".join(query_parts))


def validate(func: Callable[..., T]) -> Callable[..., T]:
    """
    Decorator for Spotify API methods that handles authentication and device validation.
    - Checks and refreshes authentication if needed
    - Validates active device and retries with candidate device if needed
    """

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        # Handle authentication
        if not self.auth_ok():
            self.auth_refresh()

        # Handle device validation
        if not self.is_active_device():
            kwargs['device'] = self._get_candidate_device()

        return func(self, *args, **kwargs)

    return wrapper

