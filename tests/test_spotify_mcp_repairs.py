import unittest
from unittest.mock import Mock

from spotify_mcp import utils
from spotify_mcp.spotify_api import Client


class TestPlaylistParsing(unittest.TestCase):
    def test_parse_playlist_without_embedded_track_items(self):
        playlist = {
            "name": "Search Result",
            "id": "playlist-id",
            "owner": {"display_name": "palmer"},
            "tracks": {
                "total": 42,
                "href": "https://api.spotify.com/v1/playlists/playlist-id/tracks",
            },
        }

        parsed = utils.parse_playlist(playlist, "palmer", detailed=True)

        self.assertEqual(parsed["id"], "playlist-id")
        self.assertEqual(parsed["total_tracks"], 42)
        self.assertEqual(parsed["tracks"], [])

    def test_parse_playlist_without_tracks_key(self):
        playlist = {
            "name": "Created Playlist",
            "id": "created-id",
            "owner": {"id": "user-id"},
        }

        parsed = utils.parse_playlist(playlist, "user-id")

        self.assertEqual(parsed["id"], "created-id")
        self.assertEqual(parsed["owner"], "user-id")
        self.assertEqual(parsed["total_tracks"], 0)

    def test_parse_search_playlist_results(self):
        results = {
            "playlists": {
                "items": [
                    {
                        "name": "Playlist",
                        "id": "playlist-id",
                        "owner": {"display_name": "palmer"},
                        "tracks": {"total": 1},
                    }
                ]
            }
        }

        parsed = utils.parse_search_results(results, "playlist", "palmer")

        self.assertEqual(parsed["playlists"][0]["id"], "playlist-id")


class TestArtistInfoFallback(unittest.TestCase):
    def test_artist_info_returns_metadata_when_albums_fail(self):
        client = Client.__new__(Client)
        client.logger = Mock()
        client.sp = Mock()
        client.sp.artist.return_value = {
            "name": "Daft Punk",
            "id": "artist-id",
            "genres": ["electronic"],
        }
        client.sp.artist_albums.side_effect = Exception("Invalid limit")
        client.sp.artist_top_tracks.return_value = {
            "tracks": [
                {
                    "name": "One More Time",
                    "id": "track-id",
                    "artists": [{"name": "Daft Punk", "id": "artist-id"}],
                }
            ]
        }

        parsed = client.get_info("spotify:artist:artist-id")

        self.assertEqual(parsed["id"], "artist-id")
        self.assertEqual(parsed["top_tracks"][0]["id"], "track-id")
        self.assertEqual(parsed["albums"], [])
        self.assertIn("albums_error", parsed)


class TestPlaylistMutation(unittest.TestCase):
    def test_get_playlist_tracks_reads_playlist_items_endpoint(self):
        client = Client.__new__(Client)
        client.sp = Mock()
        client.sp.playlist_items.return_value = {
            "items": [
                {
                    "item": {
                        "name": "One More Time",
                        "id": "track-id",
                        "artists": [{"name": "Daft Punk"}],
                    }
                }
            ]
        }

        tracks = client.get_playlist_tracks("playlist-id")

        client.sp.playlist_items.assert_called_once_with("playlist-id", limit=50)
        self.assertEqual(tracks[0]["id"], "track-id")

    def test_add_tracks_normalizes_ids_and_returns_response(self):
        client = Client.__new__(Client)
        client.logger = Mock()
        client.sp = Mock()
        client.sp.playlist_add_items.return_value = {"snapshot_id": "snapshot"}
        client.sp.playlist_items.return_value = {
            "items": [{"item": {"id": "track-id"}}]
        }

        response = client.add_tracks_to_playlist("playlist-id", ["track-id"])

        client.sp.playlist_add_items.assert_called_once_with(
            "playlist-id",
            ["spotify:track:track-id"],
            position=None,
        )
        self.assertEqual(response["snapshot_id"], "snapshot")

    def test_add_tracks_raises_spotify_errors(self):
        client = Client.__new__(Client)
        client.logger = Mock()
        client.sp = Mock()
        client.sp.playlist_add_items.side_effect = RuntimeError("forbidden")

        with self.assertRaises(RuntimeError):
            client.add_tracks_to_playlist("playlist-id", ["track-id"])

    def test_remove_tracks_normalizes_ids_and_returns_response(self):
        client = Client.__new__(Client)
        client.logger = Mock()
        client.sp = Mock()
        client.sp.playlist_remove_all_occurrences_of_items.return_value = {
            "snapshot_id": "snapshot"
        }
        client.sp.playlist_items.return_value = {"items": []}

        response = client.remove_tracks_from_playlist("playlist-id", ["track-id"])

        client.sp.playlist_remove_all_occurrences_of_items.assert_called_once_with(
            "playlist-id",
            ["spotify:track:track-id"],
        )
        self.assertEqual(response["snapshot_id"], "snapshot")


if __name__ == "__main__":
    unittest.main()
