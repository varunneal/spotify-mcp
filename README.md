# spotify-mcp (Daniel's fork)

MCP server connecting Claude (and any other MCP client) with Spotify. Built on top of
[spotipy-dev's API](https://github.com/spotipy-dev/spotipy).

This is a **maintained fork** of [`varunneal/spotify-mcp`](https://github.com/varunneal/spotify-mcp)
(upstream marked inactive as of March 2026). The original project's README is preserved as
[`README.original.md`](./README.original.md).

---

## What's new in this fork

The upstream tools (Playback, Search, Queue, GetInfo, Playlist) are unchanged in behavior.
On top of them this fork adds:

| Addition | Type | What it does |
|---|---|---|
| **`previous` action** on `SpotifyPlayback` | Feature | Jump back to the previous track. Upstream was missing this. |
| OAuth scope alignment | Fix | Runtime scope is now derived from the declared `SCOPES` list, so additions (e.g. `user-top-read`, `user-read-recently-played`, `user-modify-playback-state`) actually take effect. You may need to re-authorize once (delete `.cache` in the project root). |
| **`SpotifyHistory`** | New tool | Recently-played tracks with optional time cursors. |
| **`SpotifyTasteProfile`** | New tool | Top artists + top tracks + genre histogram, cached per `time_range` for 30 days. |
| **`SpotifySmartPlay`** | New tool (flagship) | Natural-language query → Spotify search → candidate ranking (name overlap + editorial curation + taste signal) → auto-play. |

All new tools degrade gracefully: if taste can't be fetched, `SmartPlay` still ranks candidates
(just without the taste bonus); if no device is active, `auto_played: false` is returned with
a populated `auto_play_error` instead of crashing.

---

## Tool reference with example prompts

Every tool is a top-level MCP tool named `Spotify<Name>`. Once the server is wired into your
MCP client, ask for any of the following in plain English — the client decides which tool to call.

### `SpotifyPlayback` — control playback

Actions: `get`, `start`, `pause`, `skip`, **`previous`** (new).

```
Play "After Hours" by The Weeknd.
Pause the music.
Skip this song.
Skip the next 3 tracks.
Go back to the previous song.
What's currently playing?
```

### `SpotifySearch` — search the catalog

```
Search for tracks matching "dreamy shoegaze 2024".
Find albums by Mitski.
Look up the playlist "Deep Focus".
```

### `SpotifyQueue` — inspect or append to the queue

Actions: `add`, `get`.

```
Add "Bad Guy" to the queue.
Show me what's in the queue right now.
Queue up three songs by Radiohead then show the queue.
```

### `SpotifyGetInfo` — details for a URI

```
Tell me more about spotify:album:2noRn2Aes5aoNVsU6iWThc.
Give me the track list and release date for that album.
```

### `SpotifyPlaylist` — manage playlists

Actions: `get`, `get_tracks`, `add_tracks`, `remove_tracks`, `change_details`, `create`.

```
List my playlists.
Show the tracks in my "Late Night Focus" playlist.
Create a private playlist called "Road Trip 2026" with description "summer driving mix".
Add these three tracks to "Road Trip 2026": <paste IDs>.
Remove that last track from "Road Trip 2026".
Rename "Road Trip 2026" to "Summer 2026 Driving Mix".
```

### `SpotifyHistory` — recently played (new)

Parameters: `limit` (1–50, default 20), `after` / `before` (unix-ms cursors, mutually exclusive).

```
What are the last 10 songs I listened to?
Add the song I heard right before the current one to my liked playlist.
Show me everything I played in the last hour.
What was I listening to around 9pm last night?
```

**Typical item:**
```json
{
  "track": {"name": "Nightcall", "id": "...", "artist": "Kavinsky"},
  "played_at": "2026-04-19T23:41:02.000Z",
  "context_uri": "spotify:playlist:...",
  "context_type": "playlist"
}
```

### `SpotifyTasteProfile` — top artists, tracks, genres (new)

Actions: `profile` (default), `tracks`, `artists`.
Parameters: `time_range` (`short_term` ≈ 4 weeks / `medium_term` ≈ 6 months / `long_term`),
`limit` (1–50), `refresh` (bool — bypass the 30-day cache).

```
Summarize my listening taste.
What are my top 10 artists of the last month?
Show my top tracks for the last 6 months.
Refresh my taste profile (bypass the cache) and list my top genres.
Which genres dominate my long-term listening?
```

**`profile` response shape:**
```json
{
  "time_range": "medium_term",
  "top_artists": [{"id": "...", "name": "...", "genres": [...], "popularity": 72}, ...],
  "top_tracks":  [{"id": "...", "name": "...", "artist": "..."}, ...],
  "genres":      [{"name": "indietronica", "count": 4}, ...]
}
```

The cache stores an extra `_top_artist_ids` set used internally by `SmartPlay`; those keys
are stripped before the JSON response.

### `SpotifySmartPlay` — natural-language, taste-weighted auto-play (new, flagship)

Parameters:
- `query` (required): natural-language description.
- `prefer` (optional): bias toward `"track"`, `"album"`, or `"playlist"`.
- `auto_play` (default `true`): immediately start the top pick.
- `limit` (default 10, 1–20): candidates per type pulled from search.

Scoring breakdown (all additive, fully transparent via `rationale`):
- **Name overlap** — query tokens ∩ candidate name.
- **Prefer bonus** — `+0.30` if candidate type equals `prefer`.
- **Curation bonus** — playlists only: Spotify-owned editorial, sensible track count.
- **Taste bonus** — candidate's artists ∩ your top artists (`+0.50`).

```
Play something chill for late-night focus.
Put on something moody and atmospheric — prefer a playlist.
Queue up a high-energy album for running, I want an album not a playlist.
Play that new Mitski track — but just the track, not a full album.
Find me a playlist that matches my current mood: rainy afternoon, cozy.
```

**Response shape (abbreviated):**
```json
{
  "query": "chill focus beats for late night",
  "chosen": {
    "type": "playlist",
    "id": "37i9dQZF1DWZeKCadgRdKQ",
    "name": "Deep Focus",
    "uri": "spotify:playlist:37i9dQZF1DWZeKCadgRdKQ",
    "score": 1.2
  },
  "runners_up": [...],
  "rationale": "name_overlap +0.67 curation +0.60 taste +0.00 = 1.20",
  "auto_played": true,
  "auto_play_error": null,
  "taste_available": true
}
```

---

## Configuration

### Spotify API keys

Create a Spotify developer account at [developer.spotify.com](https://developer.spotify.com/),
then create an app in the [dashboard](https://developer.spotify.com/dashboard) with redirect URI
`http://127.0.0.1:8080/callback` (any port, but it must be `http` and an explicit loopback
address — IPv4 or IPv6). See the
[Spotify redirect URI docs](https://developer.spotify.com/documentation/web-api/concepts/redirect_uri)
for troubleshooting.

Spotify **Premium** is required — several endpoints (playback control, queue, recently-played)
are Premium-only.

### MCP client config

Locate your MCP client config:

- Claude Desktop (macOS): `~/Library/Application\ Support/Claude/claude_desktop_config.json`
- Claude Desktop (Windows): `%APPDATA%/Claude/claude_desktop_config.json`
- Cursor, Zed, others: see their respective docs.

#### Run with `uvx` (from this fork)

```json
{
  "mcpServers": {
    "spotify": {
      "command": "uvx",
      "args": [
        "--python", "3.12",
        "--from", "git+https://github.com/Danieloni1/spotify-mcp",
        "spotify-mcp"
      ],
      "env": {
        "SPOTIFY_CLIENT_ID": "YOUR_CLIENT_ID",
        "SPOTIFY_CLIENT_SECRET": "YOUR_CLIENT_SECRET",
        "SPOTIFY_REDIRECT_URI": "http://127.0.0.1:8080/callback"
      }
    }
  }
}
```

#### Run locally (recommended for development)

```bash
git clone https://github.com/Danieloni1/spotify-mcp.git
```

```json
{
  "mcpServers": {
    "spotify": {
      "command": "uv",
      "args": ["--directory", "/path/to/spotify-mcp", "run", "spotify-mcp"],
      "env": {
        "SPOTIFY_CLIENT_ID": "YOUR_CLIENT_ID",
        "SPOTIFY_CLIENT_SECRET": "YOUR_CLIENT_SECRET",
        "SPOTIFY_REDIRECT_URI": "http://127.0.0.1:8080/callback"
      }
    }
  }
}
```

### Re-authorization after scope changes

This fork expands the OAuth scopes (adds `user-top-read`, `user-read-recently-played`,
`user-modify-playback-state`). If you previously used the upstream project and already have a
cached token, delete it and re-authorize:

```bash
rm /path/to/spotify-mcp/.cache
```

Then restart your MCP client — the next tool call will open the Spotify auth page.

### Restarting the MCP server without restarting Claude Desktop

Toggle the server off/on in Claude Desktop's **Developer** settings, or from a terminal:

```bash
pkill -f spotify-mcp
```

The client will respawn it on the next tool call.

---

## Troubleshooting

1. `uv` must be up to date — `>=0.54` recommended.
2. If cloning locally, ensure execute permissions: `chmod -R 755 /path/to/spotify-mcp`.
3. Spotify Premium is required for playback/queue/history endpoints.
4. Logs go to stderr. Claude Desktop on macOS writes them to `~/Library/Logs/Claude`; for other
   platforms see the [MCP user guide](https://modelcontextprotocol.io/quickstart/user#getting-logs-from-claude-for-desktop).
5. Inspect the server directly:
   ```bash
   npx @modelcontextprotocol/inspector uv --directory /path/to/spotify-mcp run spotify-mcp
   ```

---

## Roadmap

- Pagination for search results, playlists, and albums (upstream-deferred, still open here).
- Tests for `ranking.py` and `smart_play` scoring regressions.
- Iteration on `SmartPlay` ranking weights based on real-world use.

Some upstream features (`/recommendations`, audio features, related-artists, featured-playlists)
[were deprecated by Spotify in November 2024](https://techcrunch.com/2024/11/27/spotify-cuts-developer-access-to-several-of-its-recommendation-features/)
and won't come back to this fork.

## Credits

Fork maintained by [@Danieloni1](https://github.com/Danieloni1). Upstream project by
[@varunneal](https://github.com/varunneal) and contributors (@jamiew, @davidpadbury,
@manncodes, @hyuma7, @aanurraj, @JJGO, and others). See [`README.original.md`](./README.original.md)
for the upstream README at fork time.
