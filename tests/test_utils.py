"""Tests for spotify_mcp.utils module."""
from typing import Dict, Any

import pytest

from spotify_mcp.utils import (
    parse_track,
    parse_artist,
    parse_album,
    parse_playlist,
    parse_search_results,
    build_search_query
)


class TestParseTrack:
    """Tests for parse_track function."""
    
    def test_parse_track_basic(self, sample_track_data: Dict[str, Any]) -> None:
        """Test basic track parsing."""
        result = parse_track(sample_track_data)
        
        assert result is not None
        assert result["name"] == "Test Song"
        assert result["id"] == "4iV5W9uYEdYUVa79Axb7Rh"
        assert result["artist"] == "Test Artist"
    
    def test_parse_track_detailed(self, sample_track_data: Dict[str, Any]) -> None:
        """Test detailed track parsing."""
        result = parse_track(sample_track_data, detailed=True)
        
        assert result is not None
        assert result["name"] == "Test Song"
        assert result["track_number"] == 1
        assert result["duration_ms"] == 240000
        assert "album" in result
    
    def test_parse_track_none_input(self) -> None:
        """Test parse_track with None input."""
        result = parse_track(None)
        assert result is None
    
    def test_parse_track_multiple_artists(self) -> None:
        """Test parse_track with multiple artists."""
        track_data = {
            "id": "test_id",
            "name": "Test Song",
            "artists": [
                {"name": "Artist 1", "id": "artist1"},
                {"name": "Artist 2", "id": "artist2"}
            ],
            "album": {"name": "Test Album", "id": "album_id", "artists": []}
        }
        
        result = parse_track(track_data)
        
        assert result is not None
        assert "artists" in result
        assert len(result["artists"]) == 2


class TestParseArtist:
    """Tests for parse_artist function."""
    
    def test_parse_artist_basic(self) -> None:
        """Test basic artist parsing."""
        artist_data = {
            "id": "artist_id",
            "name": "Test Artist"
        }
        
        result = parse_artist(artist_data)
        
        assert result is not None
        assert result["name"] == "Test Artist"
        assert result["id"] == "artist_id"
    
    def test_parse_artist_detailed(self) -> None:
        """Test detailed artist parsing."""
        artist_data = {
            "id": "artist_id",
            "name": "Test Artist",
            "genres": ["pop", "rock"]
        }
        
        result = parse_artist(artist_data, detailed=True)
        
        assert result is not None
        assert result["genres"] == ["pop", "rock"]
    
    def test_parse_artist_none_input(self) -> None:
        """Test parse_artist with None input."""
        result = parse_artist(None)
        assert result is None


class TestParsePlaylist:
    """Tests for parse_playlist function."""
    
    def test_parse_playlist_basic(self, sample_playlist_data: Dict[str, Any]) -> None:
        """Test basic playlist parsing."""
        result = parse_playlist(sample_playlist_data)
        
        assert result is not None
        assert result["name"] == "Test Playlist"
        assert result["id"] == "test_playlist_id"
        assert result["owner"] == "Test User"
    
    def test_parse_playlist_detailed(self, sample_playlist_data: Dict[str, Any]) -> None:
        """Test detailed playlist parsing."""
        result = parse_playlist(sample_playlist_data, detailed=True)
        
        assert result is not None
        assert result["description"] == "A test playlist"
        assert "tracks" in result
        assert len(result["tracks"]) == 1
    
    def test_parse_playlist_none_input(self) -> None:
        """Test parse_playlist with None input."""
        result = parse_playlist(None)
        assert result is None


class TestBuildSearchQuery:
    """Tests for build_search_query function."""
    
    def test_build_search_query_basic(self) -> None:
        """Test basic search query building."""
        result = build_search_query("test song")
        assert "test%20song" in result
    
    def test_build_search_query_with_filters(self) -> None:
        """Test search query with filters."""
        result = build_search_query(
            "test song",
            artist="test artist",
            year="2023"
        )
        
        assert "artist%3Atest%20artist" in result
        assert "year%3A2023" in result
    
    def test_build_search_query_year_range(self) -> None:
        """Test search query with year range."""
        result = build_search_query(
            "test song",
            year_range=(2020, 2023)
        )
        
        assert "year%3A2020-2023" in result
    
    def test_build_search_query_tags(self) -> None:
        """Test search query with special tags."""
        result = build_search_query(
            "test song",
            is_hipster=True,
            is_new=True
        )
        
        assert "tag%3Ahipster" in result
        assert "tag%3Anew" in result


class TestParseSearchResults:
    """Tests for parse_search_results function."""
    
    def test_parse_search_results_tracks(self, sample_track_data: Dict[str, Any]) -> None:
        """Test parsing search results for tracks."""
        search_data = {
            "tracks": {
                "items": [sample_track_data]
            }
        }
        
        result = parse_search_results(search_data, "track")
        
        assert "tracks" in result
        assert len(result["tracks"]) == 1
        assert result["tracks"][0]["name"] == "Test Song"
    
    def test_parse_search_results_multiple_types(self, sample_track_data: Dict[str, Any]) -> None:
        """Test parsing search results for multiple types."""
        search_data = {
            "tracks": {"items": [sample_track_data]},
            "artists": {"items": [{"id": "artist_id", "name": "Test Artist"}]}
        }
        
        result = parse_search_results(search_data, "track,artist")
        
        assert "tracks" in result
        assert "artists" in result
        assert len(result["tracks"]) == 1
        assert len(result["artists"]) == 1
    
    def test_parse_search_results_none_input(self) -> None:
        """Test parse_search_results with None input."""
        result = parse_search_results(None, "track")
        assert result == {}
    
    def test_parse_search_results_invalid_type(self) -> None:
        """Test parse_search_results with invalid type."""
        search_data = {"tracks": {"items": []}}
        
        with pytest.raises(ValueError, match="uknown qtype"):
            parse_search_results(search_data, "invalid_type")