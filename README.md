# spotify-mcp MCP server

MCP project to connect Claude with Spotify. Built on top of [spotipy-dev's API](https://github.com/spotipy-dev/spotipy/tree/2.24.0).

## Features

- Start, pause, and skip playback
- Search for tracks/albums/artists/playlists
- Get info about a track/album/artist/playlist
- Manage the Spotify queue
- Manage, create, and update playlists

## Demo

Make sure to turn on audio

<details>
  <summary>
    Video
  </summary>
  https://github.com/user-attachments/assets/20ee1f92-f3e3-4dfa-b945-ca57bc1e0894
</details>

## Configuration

### Getting Spotify API Keys

Create an account on [developer.spotify.com](https://developer.spotify.com/). Navigate to [the dashboard](https://developer.spotify.com/dashboard). 
Create an app with redirect_uri as http://127.0.0.1:8080/callback. 
You can choose any port you want but you must use http and an explicit loopback address (IPv4 or IPv6).

See [here](https://developer.spotify.com/documentation/web-api/concepts/redirect_uri) for more info/troubleshooting. 
You may have to restart your MCP environment (e.g. Claude Desktop) once or twice before it works.

### Run this project locally

This project is not yet set up for ephemeral environments (e.g. `uvx` usage).
Run this project locally by cloning this repo

```bash
git clone https://github.com/varunneal/spotify-mcp.git
```

Add this tool as a mcp server. 

Claude Desktop on MacOS: `~/Library/Application\ Support/Claude/claude_desktop_config.json`

Claude Desktop on Windows: `%APPDATA%/Claude/claude_desktop_config.json`

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
        "SPOTIFY_REDIRECT_URI": "http://127.0.0.1:8080/callback"
      }
    }
  ```

### Troubleshooting

Please open an issue if you can't get this MCP working. Here are some tips:

1. Make sure `uv` is updated. I recommend version `>=0.54`.
2. Make sure claude has execution permisisons for the project: `chmod -R 755`.
3. Ensure you have Spotify premium (needed for running developer API). 

This MCP will emit logs to std err (as specified in the MCP) spec. On Mac the Claude Desktop app should emit these logs
to `~/Library/Logs/Claude`. 
On other platforms [you can find logs here](https://modelcontextprotocol.io/quickstart/user#getting-logs-from-claude-for-desktop).


You can launch the MCP Inspector via [`npm`](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm) with this command:

```bash
npx @modelcontextprotocol/inspector uv --directory /path/to/spotify_mcp run spotify-mcp
```

Upon launching, the Inspector will display a URL that you can access in your browser to begin debugging.

## TODO

Unfortunately, a bunch of cool features have [now been deprecated](https://techcrunch.com/2024/11/27/spotify-cuts-developer-access-to-several-of-its-recommendation-features/)
from the Spotify API. Most new features will be relatively minor or for the health of the project:

- tests.
- adding API support for managing playlists.
- adding API support for paginated search results/playlists/albums.

PRs appreciated! Thanks to @jamiew, @davidpadbury, @manncodes, @hyuma7, @aanurraj, and others for contributions.  

## Deployment

(todo)

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
