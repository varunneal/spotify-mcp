# spotify-mcp MCP server

MCP project to connect Claude with Spotify. Built on top of [spotipy-dev's API](https://github.com/spotipy-dev/spotipy/tree/2.24.0).

## Features
- Start, pause, and skip playback
- Search for tracks/albums/artists/playlists
- Get info about a track/album/artist/playlist
- Manage the Spotify queue

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


## TODO

Unfortunately, a bunch of cool features have [now been deprecated](https://techcrunch.com/2024/11/27/spotify-cuts-developer-access-to-several-of-its-recommendation-features/) 
from the Spotify API. Most new features will be relatively minor or for the health of the project:
- tests.
- adding API support for managing playlists.
- adding API support for paginated search results/playlists/albums.

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

### Debugging

Since MCP servers run over stdio, debugging can be challenging. For the best debugging
experience, we strongly recommend using the [MCP Inspector](https://github.com/modelcontextprotocol/inspector).


You can launch the MCP Inspector via [`npm`](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm) with this command:

```bash
npx @modelcontextprotocol/inspector uv --directory /Users/varun/Documents/Python/spotify_mcp run spotify-mcp
```


Upon launching, the Inspector will display a URL that you can access in your browser to begin debugging.
