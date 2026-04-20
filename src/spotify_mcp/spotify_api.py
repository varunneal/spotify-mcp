import logging
import os
import time
from typing import Optional, Dict, List

import spotipy
from dotenv import load_dotenv
from spotipy.cache_handler import CacheFileHandler
from spotipy.oauth2 import SpotifyOAuth

from . import utils

load_dotenv()

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")

# Normalize the redirect URI to meet Spotify's requirements
if REDIRECT_URI:
    REDIRECT_URI = utils.normalize_redirect_uri(REDIRECT_URI)

TASTE_CACHE_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days

SCOPES = [
    # spotify connect
    "user-read-currently-playing", "user-read-playback-state", "user-modify-playback-state",
    # playback
    "app-remote-control", "streaming",
    # playlists
    "playlist-read-private", "playlist-read-collaborative",
    "playlist-modify-private", "playlist-modify-public",
    # listening history
    "user-read-playback-position", "user-top-read", "user-read-recently-played",
    # library
    "user-library-modify", "user-library-read",
]


class Client:
    def __init__(self, logger: logging.Logger):
        """Initialize Spotify client with necessary permissions"""
        self.logger = logger

        scope = ",".join(SCOPES)

        try:
            self.sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
                scope=scope,
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
                redirect_uri=REDIRECT_URI))

            self.auth_manager: SpotifyOAuth = self.sp.auth_manager
            self.cache_handler: CacheFileHandler = self.auth_manager.cache_handler
        except Exception as e:
            self.logger.error(f"Failed to initialize Spotify client: {str(e)}")
            raise

        self.username = None
        self._taste_cache: Dict[str, Dict] = {}  # keyed by time_range

    @utils.validate
    def set_username(self, device=None):
        self.username = self.sp.current_user()['display_name']

    @utils.ensure_auth
    def search(self, query: str, qtype: str = 'track', limit=10):
        """
        Searches based of query term.
        - query: query term
        - qtype: the types of items to return. One or more of 'artist', 'album',  'track', 'playlist'.
                 If multiple types are desired, pass in a comma separated string; e.g. 'track,album'
        - limit: max # items to return
        """
        if self.username is None:
            self.set_username()
        results = self.sp.search(q=query, limit=limit, type=qtype)
        if not results:
            raise ValueError("No search results found.")
        return utils.parse_search_results(results, qtype, self.username)

    def recommendations(self, artists: Optional[List] = None, tracks: Optional[List] = None, limit=20):
        # doesnt work
        recs = self.sp.recommendations(seed_artists=artists, seed_tracks=tracks, limit=limit)
        return recs

    def get_info(self, item_uri: str) -> dict:
        """
        Returns more info about item.
        - item_uri: uri. Looks like 'spotify:track:xxxxxx', 'spotify:album:xxxxxx', etc.
        """
        _, qtype, item_id = item_uri.split(":")
        match qtype:
            case 'track':
                return utils.parse_track(self.sp.track(item_id), detailed=True)
            case 'album':
                album_info = utils.parse_album(self.sp.album(item_id), detailed=True)
                return album_info
            case 'artist':
                artist_info = utils.parse_artist(self.sp.artist(item_id), detailed=True)
                albums = self.sp.artist_albums(item_id)
                top_tracks = self.sp.artist_top_tracks(item_id)['tracks']
                albums_and_tracks = {
                    'albums': albums,
                    'tracks': {'items': top_tracks}
                }
                parsed_info = utils.parse_search_results(albums_and_tracks, qtype="album,track")
                artist_info['top_tracks'] = parsed_info['tracks']
                artist_info['albums'] = parsed_info['albums']

                return artist_info
            case 'playlist':
                if self.username is None:
                    self.set_username()
                playlist = self.sp.playlist(item_id)
                self.logger.info(f"playlist info is {playlist}")
                # sp.playlist() only returns the first 100 tracks; paginate the rest.
                total = playlist['tracks']['total']
                all_items = list(playlist['tracks']['items'])
                while len(all_items) < total:
                    page = self.sp.playlist_items(
                        item_id,
                        offset=len(all_items),
                        limit=100,
                        additional_types=('track',),
                    )
                    if not page or not page.get('items'):
                        break
                    all_items.extend(page['items'])
                playlist['tracks']['items'] = all_items
                playlist['tracks']['total'] = len(all_items)
                playlist_info = utils.parse_playlist(playlist, self.username, detailed=True)

                return playlist_info

        raise ValueError(f"Unknown qtype {qtype}")

    def get_current_track(self) -> Optional[Dict]:
        """Get information about the currently playing track"""
        try:
            # current_playback vs current_user_playing_track?
            current = self.sp.current_user_playing_track()
            if not current:
                self.logger.info("No playback session found")
                return None
            if current.get('currently_playing_type') != 'track':
                self.logger.info("Current playback is not a track")
                return None

            track_info = utils.parse_track(current['item'])
            if 'is_playing' in current:
                track_info['is_playing'] = current['is_playing']

            self.logger.info(
                f"Current track: {track_info.get('name', 'Unknown')} by {track_info.get('artist', 'Unknown')}")
            return track_info
        except Exception as e:
            self.logger.error("Error getting current track info.")
            raise

    @utils.validate
    def start_playback(self, spotify_uri=None, device=None):
        """
        Starts spotify playback of uri. If spotify_uri is omitted, resumes current playback.
        - spotify_uri: ID of resource to play, or None. Typically looks like 'spotify:track:xxxxxx' or 'spotify:album:xxxxxx'.
        """
        try:
            self.logger.info(f"Starting playback for spotify_uri: {spotify_uri} on {device}")
            if not spotify_uri:
                if self.is_track_playing():
                    self.logger.info("No track_id provided and playback already active.")
                    return
                if not self.get_current_track():
                    raise ValueError("No track_id provided and no current playback to resume.")

            if spotify_uri is not None:
                if spotify_uri.startswith('spotify:track:'):
                    uris = [spotify_uri]
                    context_uri = None
                else:
                    uris = None
                    context_uri = spotify_uri
            else:
                uris = None
                context_uri = None

            device_id = device.get('id') if device else None

            self.logger.info(f"Starting playback of on {device}: context_uri={context_uri}, uris={uris}")
            result = self.sp.start_playback(uris=uris, context_uri=context_uri, device_id=device_id)
            self.logger.info(f"Playback result: {result}")
            return result
        except Exception as e:
            self.logger.error(f"Error starting playback: {str(e)}.")
            raise

    @utils.validate
    def pause_playback(self, device=None):
        """Pauses playback."""
        playback = self.sp.current_playback()
        if playback and playback.get('is_playing'):
            self.sp.pause_playback(device.get('id') if device else None)

    @utils.validate
    def add_to_queue(self, track_id: str, device=None):
        """
        Adds track to queue.
        - track_id: ID of track to play.
        """
        self.sp.add_to_queue(track_id, device.get('id') if device else None)

    @utils.validate
    def get_queue(self, device=None):
        """Returns the current queue of tracks."""
        queue_info = self.sp.queue()
        queue_info['currently_playing'] = self.get_current_track()

        queue_info['queue'] = [utils.parse_track(track) for track in queue_info.pop('queue')]

        return queue_info

    def get_liked_songs(self):
        # todo
        results = self.sp.current_user_saved_tracks()
        for idx, item in enumerate(results['items']):
            track = item['track']
            print(idx, track['artists'][0]['name'], " – ", track['name'])

    def is_track_playing(self) -> bool:
        """Returns if a track is actively playing."""
        curr_track = self.get_current_track()
        if not curr_track:
            return False
        if curr_track.get('is_playing'):
            return True
        return False

    def get_current_user_playlists(self, limit=50) -> List[Dict]:
        """
        Get current user's playlists.
        - limit: Max number of playlists to return.
        """
        playlists = self.sp.current_user_playlists()
        if not playlists:
            raise ValueError("No playlists found.")
        return [utils.parse_playlist(playlist, self.username) for playlist in playlists['items']]
    
    @utils.ensure_username
    def get_playlist_tracks(self, playlist_id: str, limit: Optional[int] = None) -> List[Dict]:
        """
        Get tracks from a playlist, paginating until all tracks are fetched.
        - playlist_id: ID of the playlist to get tracks from.
        - limit: Optional cap on total tracks returned. None = all.
        """
        all_items: List[Dict] = []
        page = self.sp.playlist_items(
            playlist_id,
            offset=0,
            limit=100,
            additional_types=('track',),
        )
        if not page:
            raise ValueError("No playlist found.")
        while page and page.get('items'):
            all_items.extend(page['items'])
            if limit is not None and len(all_items) >= limit:
                all_items = all_items[:limit]
                break
            if not page.get('next'):
                break
            page = self.sp.playlist_items(
                playlist_id,
                offset=len(all_items),
                limit=100,
                additional_types=('track',),
            )
        return utils.parse_tracks(all_items)
    
    @utils.ensure_username
    def add_tracks_to_playlist(self, playlist_id: str, track_ids: List[str], position: Optional[int] = None):
        """
        Add tracks to a playlist.
        - playlist_id: ID of the playlist to modify.
        - track_ids: List of track IDs to add.
        - position: Position to insert the tracks at (optional).
        """
        if not playlist_id:
            raise ValueError("No playlist ID provided.")
        if not track_ids:
            raise ValueError("No track IDs provided.")
        
        try:
            response = self.sp.playlist_add_items(playlist_id, track_ids, position=position)
            self.logger.info(f"Response from adding tracks: {track_ids} to playlist {playlist_id}: {response}")
        except Exception as e:
            self.logger.error(f"Error adding tracks to playlist: {str(e)}")

    @utils.ensure_username
    def remove_tracks_from_playlist(self, playlist_id: str, track_ids: List[str]):
        """
        Remove tracks from a playlist.
        - playlist_id: ID of the playlist to modify.
        - track_ids: List of track IDs to remove.
        """
        if not playlist_id:
            raise ValueError("No playlist ID provided.")
        if not track_ids:
            raise ValueError("No track IDs provided.")
        
        try:
            response = self.sp.playlist_remove_all_occurrences_of_items(playlist_id, track_ids)
            self.logger.info(f"Response from removing tracks: {track_ids} from playlist {playlist_id}: {response}")
        except Exception as e:
            self.logger.error(f"Error removing tracks from playlist: {str(e)}")

    @utils.ensure_username
    def create_playlist(self, name: str, description: Optional[str] = None, public: bool = True):
        """
        Create a new playlist.
        - name: Name for the playlist.
        - description: Description for the playlist.
        - public: Whether the playlist should be public.
        """
        if not name:
            raise ValueError("Playlist name is required.")
        
        try:
            user = self.sp.current_user()
            user_id = user['id']
            
            playlist = self.sp.user_playlist_create(
                user=user_id,
                name=name,
                public=public,
                description=description
            )
            self.logger.info(f"Created playlist: {name} (ID: {playlist['id']})")
            return utils.parse_playlist(playlist, self.username, detailed=True)
        except Exception as e:
            self.logger.error(f"Error creating playlist: {str(e)}")
            raise

    @utils.ensure_username
    def change_playlist_details(self, playlist_id: str, name: Optional[str] = None, description: Optional[str] = None):
        """
        Change playlist details.
        - playlist_id: ID of the playlist to modify.
        - name: New name for the playlist.
        - public: Whether the playlist should be public.
        - description: New description for the playlist.
        """
        if not playlist_id:
            raise ValueError("No playlist ID provided.")
        
        try:
            response = self.sp.playlist_change_details(playlist_id, name=name, description=description)
            self.logger.info(f"Response from changing playlist details: {response}")
        except Exception as e:
            self.logger.error(f"Error changing playlist details: {str(e)}")
       
    def get_devices(self) -> dict:
        return self.sp.devices()['devices']

    def is_active_device(self):
        return any([device.get('is_active') for device in self.get_devices()])

    def _get_candidate_device(self):
        devices = self.get_devices()
        if not devices:
            raise ConnectionError("No active device. Is Spotify open?")
        for device in devices:
            if device.get('is_active'):
                return device
        self.logger.info(f"No active device, assigning {devices[0]['name']}.")
        return devices[0]

    def auth_ok(self) -> bool:
        try:
            token = self.cache_handler.get_cached_token()
            if token is None:
                self.logger.info("Auth check result: no token exists")
                return False
                
            is_expired = self.auth_manager.is_token_expired(token)
            self.logger.info(f"Auth check result: {'valid' if not is_expired else 'expired'}")
            return not is_expired  # Return True if token is NOT expired
        except Exception as e:
            self.logger.error(f"Error checking auth status: {str(e)}")
            return False  # Return False on error rather than raising

    def auth_refresh(self):
        self.auth_manager.validate_token(self.cache_handler.get_cached_token())

    def skip_track(self, n=1):
        # todo: Better error handling
        for _ in range(n):
            self.sp.next_track()

    def previous_track(self):
        self.sp.previous_track()

    @utils.ensure_auth
    def get_recently_played(self, limit: int = 20, after: Optional[int] = None,
                            before: Optional[int] = None) -> List[Dict]:
        """Return the user's recently played tracks.
        - limit: 1..50 (Spotify hard cap).
        - after: unix-ms cursor, return items played after this timestamp.
        - before: unix-ms cursor, return items played before this timestamp.
        - after and before are mutually exclusive per Spotify API.
        """
        if after is not None and before is not None:
            raise ValueError("Pass either `after` or `before`, not both.")
        limit = max(1, min(limit, 50))
        resp = self.sp.current_user_recently_played(limit=limit, after=after, before=before)
        if not resp or not resp.get('items'):
            return []
        return [utils.parse_recently_played_item(i) for i in resp['items']]

    @utils.ensure_auth
    def get_top_items(self, entity: str, time_range: str = 'medium_term',
                      limit: int = 20) -> List[Dict]:
        """Return the user's top tracks or artists for a given time range.
        - entity: 'tracks' or 'artists'.
        - time_range: 'short_term' (~4 weeks), 'medium_term' (~6 months), or 'long_term'.
        """
        if entity not in ('tracks', 'artists'):
            raise ValueError(f"entity must be 'tracks' or 'artists', got {entity!r}")
        if time_range not in ('short_term', 'medium_term', 'long_term'):
            raise ValueError(f"invalid time_range {time_range!r}")
        limit = max(1, min(limit, 50))
        if entity == 'tracks':
            resp = self.sp.current_user_top_tracks(limit=limit, offset=0, time_range=time_range)
            return [utils.parse_track(t) for t in (resp.get('items') or [])]
        resp = self.sp.current_user_top_artists(limit=limit, offset=0, time_range=time_range)
        return [utils.parse_top_artist(a) for a in (resp.get('items') or [])]

    @utils.ensure_auth
    def get_taste_profile(self, time_range: str = 'medium_term', limit: int = 20,
                          refresh: bool = False) -> Dict:
        """Build (and cache for 30 days) a compact taste profile for the user.
        Returns {time_range, top_artists, top_tracks, genres, _top_artist_ids, _cached_at}.
        Underscore-prefixed keys are for internal use (smart_play) and stripped before
        external JSON responses.
        """
        if time_range not in ('short_term', 'medium_term', 'long_term'):
            raise ValueError(f"invalid time_range {time_range!r}")
        limit = max(1, min(limit, 50))
        now = time.time()
        if not refresh and time_range in self._taste_cache:
            cached = self._taste_cache[time_range]
            if now - cached.get('_cached_at', 0) < TASTE_CACHE_TTL_SECONDS:
                self.logger.info(f"get_taste_profile: cache hit for time_range={time_range}")
                return cached
        self.logger.info(f"get_taste_profile: fetching fresh profile for time_range={time_range}")
        top_artists_raw = (self.sp.current_user_top_artists(
            limit=limit, time_range=time_range) or {}).get('items') or []
        top_tracks_raw = (self.sp.current_user_top_tracks(
            limit=limit, time_range=time_range) or {}).get('items') or []
        profile: Dict = {
            'time_range': time_range,
            'top_artists': [utils.parse_top_artist(a) for a in top_artists_raw],
            'top_tracks': [utils.parse_track(t) for t in top_tracks_raw],
            'genres': utils.genre_histogram(top_artists_raw, limit=limit),
            '_top_artist_ids': {a['id'] for a in top_artists_raw},
            '_cached_at': now,
        }
        self._taste_cache[time_range] = profile
        return profile

    @utils.ensure_auth
    def smart_play(self, query: str, prefer: Optional[str] = None,
                   auto_play: bool = True, limit: int = 10) -> Dict:
        """Pick the best Spotify item for a natural-language query and (optionally)
        start playback. Ranks by name overlap, editorial curation (playlists), and
        the user's taste profile (top artists). Graceful degrade on taste/device failure.
        """
        from . import ranking

        if not query or not query.strip():
            return {'error': 'query is required'}
        if prefer is not None and prefer not in ('track', 'album', 'playlist'):
            return {'error': f"prefer must be 'track', 'album', or 'playlist', got {prefer!r}"}
        limit = max(1, min(limit, 20))

        # 1. Taste signal (graceful degrade).
        top_artist_ids: set = set()
        taste_available = False
        try:
            profile = self.get_taste_profile(time_range='medium_term', limit=20)
            top_artist_ids = set(profile.get('_top_artist_ids') or set())
            taste_available = True
        except Exception as e:
            self.logger.info(f"smart_play: taste unavailable ({e}); ranking without taste signal")

        # 2. Raw search — need artist IDs unavailable on parsed track/album output.
        if self.username is None:
            self.set_username()
        raw = self.sp.search(q=query, limit=limit, type='track,album,playlist')
        if not raw:
            return {'error': f"No search results for query {query!r}.", 'taste_available': taste_available}

        # Build (type, id) -> artist_ids lookup from raw response.
        artist_ids_by_key: Dict[tuple, List[str]] = {}
        for t in ((raw.get('tracks') or {}).get('items') or []):
            if t and t.get('id'):
                artist_ids_by_key[('track', t['id'])] = [
                    a['id'] for a in (t.get('artists') or []) if a.get('id')
                ]
        for a in ((raw.get('albums') or {}).get('items') or []):
            if a and a.get('id'):
                artist_ids_by_key[('album', a['id'])] = [
                    ar['id'] for ar in (a.get('artists') or []) if ar.get('id')
                ]

        # 3. Parse + flatten candidates, inject _artist_ids in-memory.
        parsed = utils.parse_search_results(raw, qtype='track,album,playlist', username=self.username)
        candidates: List[tuple] = []
        seen: set = set()

        def push(item: Dict, ctype: str):
            if not item or not item.get('id'):
                return
            key = (ctype, item['id'])
            if key in seen:
                return
            ids = artist_ids_by_key.get(key)
            if ids is not None:
                item['_artist_ids'] = ids
            candidates.append((item, ctype))
            seen.add(key)

        for t in parsed.get('tracks') or []:
            push(t, 'track')
        for a in parsed.get('albums') or []:
            push(a, 'album')
        for p in parsed.get('playlists') or []:
            push(p, 'playlist')

        if not candidates:
            return {
                'error': f"No candidates found for query {query!r}. Try a more specific query.",
                'taste_available': taste_available,
            }

        # 4. Rank.
        ranked = ranking.rank_candidates(candidates, query, top_artist_ids, prefer)
        top = ranked[0]
        uri = f"spotify:{top['type']}:{top['candidate']['id']}"

        # 5. Auto-play (graceful degrade on device / playback failure).
        auto_played = False
        auto_play_error: Optional[str] = None
        if auto_play:
            try:
                self.start_playback(spotify_uri=uri)
                auto_played = True
            except Exception as e:
                auto_play_error = str(e)
                self.logger.info(f"smart_play: auto-play failed: {e}")

        def public(c: Dict) -> Dict:
            return {k: v for k, v in c.items() if not k.startswith('_')}

        def shape(s: Dict) -> Dict:
            cand = s['candidate']
            return {
                'type': s['type'],
                'id': cand['id'],
                'name': cand.get('name'),
                'uri': f"spotify:{s['type']}:{cand['id']}",
                'score': round(s['score'], 3),
                'candidate': public(cand),
            }

        return {
            'query': query,
            'chosen': shape(top),
            'runners_up': [shape(s) for s in ranked[1:5]],
            'rationale': ranking.format_rationale(top),
            'auto_played': auto_played,
            'auto_play_error': auto_play_error,
            'taste_available': taste_available,
        }

    def seek_to_position(self, position_ms):
        self.sp.seek_track(position_ms=position_ms)

    def set_volume(self, volume_percent):
        self.sp.volume(volume_percent)
