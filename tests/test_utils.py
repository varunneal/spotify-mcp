"""
Tests for utility functions.
"""

import pytest
from spotify_mcp.utils import parse_track, parse_artist, parse_album, parse_playlist


class TestParseTrack:
    """Test track parsing utility."""
    
    def test_parse_basic_track(self, sample_track_data):
        """Test parsing a basic track."""
        result = parse_track(sample_track_data)
        
        assert result["name"] == "Never Gonna Give You Up"
        assert result["id"] == "4iV5W9uYEdYUVa79Axb7Rh"
        assert result["artist"] == "Rick Astley"  # Single artist becomes 'artist'
    
    def test_parse_track_missing_fields(self):
        """Test parsing track with missing optional fields."""
        minimal_track = {
            "id": "test123",
            "name": "Test Track",
            "artists": [{"name": "Test Artist"}]
        }
        
        result = parse_track(minimal_track)
        
        assert result["name"] == "Test Track"
        assert result["id"] == "test123"
        assert result["artist"] == "Test Artist"
    
    def test_parse_track_multiple_artists(self):
        """Test parsing track with multiple artists."""
        track_data = {
            "id": "test123",
            "name": "Collaboration",
            "artists": [
                {"name": "Artist One"},
                {"name": "Artist Two"},
                {"name": "Artist Three"}
            ]
        }
        
        result = parse_track(track_data)
        
        assert result["artists"] == ["Artist One", "Artist Two", "Artist Three"]
        assert "artist" not in result  # Multiple artists use 'artists' key
    
    def test_parse_track_none_input(self):
        """Test parsing None input."""
        result = parse_track(None)
        assert result is None
    
    def test_parse_track_detailed(self, sample_track_data):
        """Test parsing track with detailed flag."""
        # Add album data to sample
        track_with_album = sample_track_data.copy()
        track_with_album["album"] = {
            "name": "Test Album",
            "id": "album123",
            "artists": [{"name": "Rick Astley"}]
        }
        track_with_album["track_number"] = 1
        track_with_album["duration_ms"] = 213573
        
        result = parse_track(track_with_album, detailed=True)
        
        assert result["track_number"] == 1
        assert result["duration_ms"] == 213573
        assert result["album"] is not None


class TestParseArtist:
    """Test artist parsing utility."""
    
    def test_parse_basic_artist(self):
        """Test parsing a basic artist."""
        artist_data = {
            "id": "0gxyHStUsqpMadRV0Di1Qt",
            "name": "Rick Astley"
        }
        
        result = parse_artist(artist_data)
        
        assert result["name"] == "Rick Astley"
        assert result["id"] == "0gxyHStUsqpMadRV0Di1Qt"
    
    def test_parse_artist_detailed(self):
        """Test parsing artist with detailed flag."""
        artist_data = {
            "id": "0gxyHStUsqpMadRV0Di1Qt",
            "name": "Rick Astley",
            "genres": ["dance pop", "new wave pop"]
        }
        
        result = parse_artist(artist_data, detailed=True)
        
        assert result["name"] == "Rick Astley"
        assert result["id"] == "0gxyHStUsqpMadRV0Di1Qt"
        assert result["genres"] == ["dance pop", "new wave pop"]
    
    def test_parse_artist_none_input(self):
        """Test parsing None input."""
        result = parse_artist(None)
        assert result is None


class TestParseAlbum:
    """Test album parsing utility."""
    
    def test_parse_basic_album(self):
        """Test parsing a basic album."""
        album_data = {
            "id": "6XzKGcM6laRkTrME3rQvJw",
            "name": "Whenever You Need Somebody",
            "artists": [{"name": "Rick Astley"}]
        }
        
        result = parse_album(album_data)
        
        assert result["name"] == "Whenever You Need Somebody"
        assert result["id"] == "6XzKGcM6laRkTrME3rQvJw"
        assert result["artist"] == "Rick Astley"  # Single artist becomes 'artist'
    
    def test_parse_album_multiple_artists(self):
        """Test parsing album with multiple artists."""
        album_data = {
            "id": "test123",
            "name": "Collaboration Album",
            "artists": [
                {"name": "Artist One"},
                {"name": "Artist Two"}
            ]
        }
        
        result = parse_album(album_data)
        
        assert result["artists"] == ["Artist One", "Artist Two"]
        assert "artist" not in result  # Multiple artists use 'artists' key
    
    def test_parse_album_detailed(self):
        """Test parsing album with detailed flag."""
        album_data = {
            "id": "test123",
            "name": "Test Album",
            "artists": [{"name": "Test Artist", "id": "artist123"}],
            "total_tracks": 10,
            "release_date": "2023-01-01",
            "tracks": {
                "items": [
                    {"name": "Track 1", "id": "track1", "artists": [{"name": "Test Artist"}]},
                    {"name": "Track 2", "id": "track2", "artists": [{"name": "Test Artist"}]}
                ]
            }
        }
        
        result = parse_album(album_data, detailed=True)
        
        assert result["total_tracks"] == 10
        assert result["release_date"] == "2023-01-01"
        assert len(result["tracks"]) == 2
        assert result["tracks"][0]["name"] == "Track 1"
    
    def test_parse_album_none_input(self):
        """Test parsing None input."""
        result = parse_album(None)
        assert result is None


class TestParsePlaylist:
    """Test playlist parsing utility."""
    
    def test_parse_basic_playlist(self, sample_playlist_data):
        """Test parsing a basic playlist."""
        result = parse_playlist(sample_playlist_data)
        
        assert result["name"] == "RapCaviar"
        assert result["id"] == "37i9dQZF1DX0XUsuxWHRQd"
        assert result["owner"] == "Spotify"
    
    def test_parse_playlist_detailed(self):
        """Test parsing playlist with detailed flag."""
        playlist_data = {
            "id": "test123",
            "name": "Test Playlist",
            "owner": {"display_name": "Test User"},
            "description": "A test playlist",
            "tracks": {
                "items": [
                    {"track": {"name": "Track 1", "id": "track1", "artists": [{"name": "Artist 1"}]}},
                    {"track": {"name": "Track 2", "id": "track2", "artists": [{"name": "Artist 2"}]}}
                ]
            }
        }
        
        result = parse_playlist(playlist_data, detailed=True)
        
        assert result["name"] == "Test Playlist"
        assert result["description"] == "A test playlist"
        assert result["owner"] == "Test User"
        assert len(result["tracks"]) == 2
        assert result["tracks"][0]["name"] == "Track 1"
        assert result["tracks"][1]["name"] == "Track 2"
    
    def test_parse_playlist_none_input(self):
        """Test parsing None input."""
        result = parse_playlist(None)
        assert result is None