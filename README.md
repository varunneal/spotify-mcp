# spotify-mcp MCP server

[![smithery badge](https://smithery.ai/badge/@varunneal/spotify-mcp)](https://smithery.ai/server/@varunneal/spotify-mcp)

MCP project to connect Claude with Spotify. Built on top of [spotipy-dev's API](https://github.com/spotipy-dev/spotipy/tree/2.24.0).

## Features

### Core Playback
- **Playback Control**: Start, pause, skip tracks
- **Queue Management**: Add tracks to queue, view current queue
- **Real-time State**: Current user profile and playback status via MCP resources

### Search & Discovery  
- **Search**: Find tracks, albums, artists, playlists with pagination support
- **Item Details**: Get detailed info for tracks, artists, playlists

### Playlist Management
- **Create & Modify**: Create playlists, update details (name, description, privacy)
- **Track Management**: Add/remove tracks, bulk operations (up to 100 tracks)
- **Large Playlist Support**: Full pagination for playlists with 1000+ tracks

### Advanced Features
- **Comprehensive Pagination**: Handle large datasets efficiently with limit/offset parameters
- **Batch Operations**: Process multiple tracks in single API calls
- **Smart Workflows**: AI-guided prompts for playlist creation and music discovery
- **Error Recovery**: Robust error handling with helpful user guidance

## Demo

Make sure to turn on audio

<details>
  <summary>
    Video
  </summary>
  https://github.com/user-attachments/assets/20ee1f92-f3e3-4dfa-b945-ca57bc1e0894
  </summary>
</details>

## Configuration

### Getting Spotify API Keys

Create an account on [developer.spotify.com](https://developer.spotify.com/). Navigate to [the dashboard](https://developer.spotify.com/dashboard).
Create an app with redirect_uri as http://localhost:8888. (You can choose any port you want but you must use http and localhost).
I set "APIs used" to "Web Playback SDK".

### Run this project locally

This project is not yet set up for ephemeral environments (e.g. `uvx` usage).
Run this project locally by cloning this repo

```bash
git clone https://github.com/varunneal/spotify-mcp.git
```

Add this tool as a mcp server.

On MacOS: `~/Library/Application\ Support/Claude/claude_desktop_config.json`
On Windows: `%APPDATA%/Claude/claude_desktop_config.json`

  ```json
  "spotify": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/spotify_mcp",
        "run",
        "spotify-mcp"
      ],
      "env": {
        "SPOTIFY_CLIENT_ID": YOUR_CLIENT_ID,
        "SPOTIFY_CLIENT_SECRET": YOUR_CLIENT_SECRET,
        "SPOTIFY_REDIRECT_URI": "http://localhost:8888"
      }
    }
  ```

### Troubleshooting

Please open an issue if you can't get this MCP working. Here are some tips:

1. Make sure `uv` is updated. I recommend version `>=0.54`.
2. Make sure claude has execution permisisons for the project: `chmod -R 755`.
3. Ensure you have Spotify premium (needed for running developer API).

## Architecture

Built with modern **FastMCP framework** featuring:
- **13 focused tools** with single-purpose design  
- **Type-safe APIs** with automatic validation via Pydantic
- **Comprehensive test coverage** (67 tests passing)
- **Production-ready** OAuth token management and error handling

**Available Tools**: `playback_control`, `search_tracks`, `add_to_queue`, `get_queue`, `get_track_info`, `get_artist_info`, `get_playlist_info`, `get_playlist_tracks`, `create_playlist`, `add_tracks_to_playlist`, `get_user_playlists`, `remove_tracks_from_playlist`, `modify_playlist_details`

## Usage Examples

**"Create a chill study playlist with 20 tracks"** → Uses search with pagination + playlist creation + bulk track addition

**"Show me the first 50 tracks from my 'Liked Songs'"** → Leverages pagination for large playlists  

**"Find similar artists to Radiohead and add their top tracks to my queue"** → Combines search + artist info + queue management

## Limitations

Some Spotify features have been [deprecated from the API](https://techcrunch.com/2024/11/27/spotify-cuts-developer-access-to-several-of-its-recommendation-features/), but all core music management and playback features remain fully functional.

## Deployment

(todo)

### Installing via Smithery

To install spotify-mcp for Claude Desktop automatically via [Smithery](https://smithery.ai/server/@varunneal/spotify-mcp):

```bash
npx -y @smithery/cli install @varunneal/spotify-mcp --client claude
```

### Building and Publishing

To prepare the package for distribution:

1. Sync dependencies and update lockfile:

```bash
uv sync
```

2. Build package distributions:

```bash
uv build
```

This will create source and wheel distributions in the `dist/` directory.

3. Publish to PyPI:

```bash
uv publish
```

Note: You'll need to set PyPI credentials via environment variables or command flags:

- Token: `--token` or `UV_PUBLISH_TOKEN`
- Or username/password: `--username`/`UV_PUBLISH_USERNAME` and `--password`/`UV_PUBLISH_PASSWORD`

### Debugging

Since MCP servers run over stdio, debugging can be challenging. For the best debugging
experience, we strongly recommend using the [MCP Inspector](https://github.com/modelcontextprotocol/inspector).

You can launch the MCP Inspector via [`npm`](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm) with this command:

```bash
npx @modelcontextprotocol/inspector uv --directory /Users/varun/Documents/Python/spotify_mcp run spotify-mcp
```

Upon launching, the Inspector will display a URL that you can access in your browser to begin debugging.
