import json
import os
from typing import Optional, Dict
import logging
from urllib.parse import quote
from . import utils

import spotipy

from dotenv import load_dotenv
from spotipy import SpotifyException
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import CacheFileHandler

load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")

# print(CLIENT_ID, CLIENT_SECRET, REDIRECT_URI)

# if not (CLIENT_ID or CLIENT_SECRET or REDIRECT_URI):
#     raise ValueError("Client ID and Secret environment variable required")

SCOPES = ["user-read-currently-playing", "user-read-playback-state", "user-read-currently-playing",  # spotify connect
          "app-remote-control", "streaming",  # playback
          "playlist-read-private", "playlist-read-collaborative", "playlist-modify-private", "playlist-modify-public",
          # playlists
          "user-read-playback-position", "user-top-read", "user-read-recently-played",  # listening history
          "user-library-modify", "user-library-read",  # library

          ]


class Client:
    def __init__(self, logger: logging.Logger):
        """Initialize Spotify client with necessary permissions"""
        self.logger = logger

        # Define the scopes we need for playback control
        scope = "user-library-read,user-read-playback-state,user-modify-playback-state,user-read-currently-playing"

        try:
            # Create authenticated Spotify client
            self.sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
                scope=scope,
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
                redirect_uri=REDIRECT_URI))

            self.auth_manager: SpotifyOAuth = self.sp.auth_manager
            self.cache_handler: CacheFileHandler = self.auth_manager.cache_handler
        except Exception as e:
            self.logger.error(f"Failed to initialize Spotify client: {str(e)}", exc_info=True)
            raise

    def auth_ok(self) -> bool:
        try:
            result = self.auth_manager.is_token_expired(self.cache_handler.get_cached_token())
            self.logger.info(f"Auth check result: {'valid' if not result else 'expired'}")
            return result
        except Exception as e:
            self.logger.error(f"Error checking auth status: {str(e)}", exc_info=True)
            raise

    def auth_refresh(self):
        self.auth_manager.validate_token(self.cache_handler.get_cached_token())

    def get_liked_songs(self):
        results = self.sp.current_user_saved_tracks()
        for idx, item in enumerate(results['items']):
            track = item['track']
            print(idx, track['artists'][0]['name'], " – ", track['name'])

    def search(self, query, qtype='track', limit=10):
        results = self.sp.search(q=query, limit=limit, type=qtype)
        return utils.parse_search_results(results, qtype)

    def get_current_track(self) -> Optional[Dict]:
        """Get information about the currently playing track"""
        try:
            current = self.sp.current_playback()
            if not current:
                self.logger.info("No playback session found")
                return None
            if current.get('currently_playing_type') != 'track':
                self.logger.info("Current playback is not a track")
                return None

            track_info = utils.parse_track(current['item'])
            self.logger.info(
                f"Current track: {track_info.get('name', 'Unknown')} by {track_info.get('artist', 'Unknown')}")
            return track_info
        except Exception as e:
            self.logger.error("Error getting current track info", exc_info=True)
            raise

    def get_devices(self) -> dict:
        return self.sp.devices()['devices']

    def is_active_device(self):
        return any([device.get('is_active', False) for device in self.get_devices()])

    def _get_candidate_device(self):
        devices = self.get_devices()
        for device in devices:
            if device.get('is_active', False):
                return device
        print(f"No active device, assigning {devices[0]['name']}.")
        return devices[0]

    @utils.validate
    def start_playback(self, song_id=None, device=None):
        """Play a specific song by its Spotify ID."""
        try:
            if not song_id:
                curr_track = self.get_current_track()
                if curr_track and curr_track.get('is_playing', False):
                    self.logger.info("No song ID provided and playback already active.")
                    return

            uris = [f'spotify:track:{song_id}'] if song_id else None
            device_id = device.get('id') if device else None

            result = self.sp.start_playback(uris=uris, device_id=device_id)
            self.logger.info(f"Playback started successfully{' for song_id: ' + song_id if song_id else ''}")
            return result
        except Exception as e:
            self.logger.error(f"Error starting playback: {str(e)}", exc_info=True)
            raise

    def pause_playback(self):
        self.sp.pause_playback()

    def next_track(self):
        self.sp.next_track()

    def previous_track(self):
        self.sp.previous_track()

    def seek_to_position(self, position_ms):
        self.sp.seek_track(position_ms=position_ms)

    def set_volume(self, volume_percent):
        self.sp.volume(volume_percent)



