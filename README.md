# spotify-mcp MCP server

MCP project to connect Claude with Spotify. Built on top of [spotipy-dev's API](https://github.com/spotipy-dev/spotipy/tree/2.24.0). 

## Quickstart

### Create Spotify API access
Create an account on [developer.spotify.com](https://developer.spotify.com/). Navigate to [the dashboard](https://developer.spotify.com/dashboard). 
Create an app with redirect_uri as http://localhost:8888. (You can choose any port you want but you must use http and localhost). 
I set "APIs used" to "Web Playback SDK". 


## Set up spotify-mcp locally
Clone this project in whatever location you want. 

On MacOS: `~/Library/Application\ Support/Claude/claude_desktop_config.json`
On Windows: `%APPDATA%/Claude/claude_desktop_config.json`

Add this tool as a mcp server. 
<details>
  <summary>Development/Unpublished Servers Configuration</summary>
  ```
  "spotify": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/spotify_mcp",
        "run",
        "spotify-mcp"
      ],
      "env": {
        "CLIENT_ID": YOUR_CLIENT_ID,
        "CLIENT_SECRET": YOUR_CLIENT_SECRET,
        "REDIRECT_URI": "http://localhost:8888"
      }
    }
  ```
</details>


## Set up spotify-mcp via published server config
TODO
<details>
  <summary>Published Servers Configuration</summary>
  ```
  "mcpServers": {
    "spotify-mcp": {
      "command": "uvx",
      "args": [
        "spotify-mcp"
      ]
    }
  }
  ```
</details>

## Development

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