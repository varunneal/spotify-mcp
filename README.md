# spotify-mcp MCP server

MCP project to connect Claude with Spotify. Built on top of [spotipy-dev's API](https://github.com/spotipy-dev/spotipy/tree/2.24.0).

## Features

- Start, pause, and skip playback
- Search for tracks/albums/artists/playlists
- Get info about a track/album/artist/playlist
- Manage the Spotify queue
- Manage, create, and update playlists

## Demo

<details>
  <summary>
    Video -- turn on audio
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

### Locating MCP Config

For Cursor, Claude Desktop, or any other MCP-enabled client you will have to locate your config.

- Claude Desktop location on MacOS: `~/Library/Application\ Support/Claude/claude_desktop_config.json`

- Claude Desktop location on Windows: `%APPDATA%/Claude/claude_desktop_config.json`


### Run this project with uvx

Add this snippet to your MCP Config.

```json
{
  "mcpServers": {
    "spotify": {
      "command": "uvx",
      "args": [
        "--python", "3.12",
        "--from", "git+https://github.com/varunneal/spotify-mcp",
        "spotify-mcp"
      ],
      "env": {
        "SPOTIFY_CLIENT_ID": YOUR_CLIENT_ID,
        "SPOTIFY_CLIENT_SECRET": YOUR_CLIENT_SECRET,
        "SPOTIFY_REDIRECT_URI": "http://127.0.0.1:8080/callback"
      }
    }
  }
}
```

### Run this project locally

Using UVX will open the spotify redirect URI for every tool call. To avoid this, you can run this project locally by cloning this repo:

```bash
git clone https://github.com/varunneal/spotify-mcp.git
```

Add it to your MCP Config like this:

  ```json
  "spotify": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/spotify-mcp",
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
2. If cloning locally, enable execution permisisons for the project: `chmod -R 755`.
3. Ensure you have Spotify premium (needed for running developer API). 

This MCP will emit logs to std err (as specified in the MCP) spec. On Mac the Claude Desktop app should emit these logs
to `~/Library/Logs/Claude`. 
On other platforms [you can find logs here](https://modelcontextprotocol.io/quickstart/user#getting-logs-from-claude-for-desktop).


You can launch the MCP Inspector via [`npm`](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm) with this command:

```bash
npx @modelcontextprotocol/inspector uv --directory /path/to/spotify-mcp run spotify-mcp
```

Upon launching, the Inspector will display a URL that you can access in your browser to begin debugging.

## TODO

Unfortunately, a bunch of cool features have [now been deprecated](https://techcrunch.com/2024/11/27/spotify-cuts-developer-access-to-several-of-its-recommendation-features/)
from the Spotify API. Most new features will be relatively minor or for the health of the project:

- tests.
- ~~adding API support for managing playlists.~~
- adding API support for paginated search results/playlists/albums.

PRs appreciated! Thanks to @jamiew, @davidpadbury, @manncodes, @hyuma7, @aanurraj, @JJGO and others for contributions.  

[//]: # (## Deployment)

[//]: # (&#40;todo&#41;)

[//]: # (### Building and Publishing)

[//]: # ()
[//]: # (To prepare the package for distribution:)

[//]: # ()
[//]: # (1. Sync dependencies and update lockfile:)

[//]: # ()
[//]: # (```bash)

[//]: # (uv sync)

[//]: # (```)

[//]: # ()
[//]: # (2. Build package distributions:)

[//]: # ()
[//]: # (```bash)

[//]: # (uv build)

[//]: # (```)

[//]: # ()
[//]: # (This will create source and wheel distributions in the `dist/` directory.)

[//]: # ()
[//]: # (3. Publish to PyPI:)

[//]: # ()
[//]: # (```bash)

[//]: # (uv publish)

[//]: # (```)

[//]: # ()
[//]: # (Note: You'll need to set PyPI credentials via environment variables or command flags:)

[//]: # ()
[//]: # (- Token: `--token` or `UV_PUBLISH_TOKEN`)

[//]: # (- Or username/password: `--username`/`UV_PUBLISH_USERNAME` and `--password`/`UV_PUBLISH_PASSWORD`)
