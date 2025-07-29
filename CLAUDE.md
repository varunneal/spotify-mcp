# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Running the Server
- `uv run spotify-mcp` - Start the MCP server (requires Spotify API credentials in environment)
- `uv sync` - Sync dependencies and update lockfile
- `uv sync --dev` - Sync development dependencies (includes pytest, mypy)
- `uv build` - Build package distributions for PyPI
- `uv publish` - Publish to PyPI (requires credentials)

### Testing & Type Checking
- `uv run pytest` - Run all unit tests
- `uv run pytest -v` - Run tests with verbose output
- `uv run pytest tests/test_utils.py` - Run specific test file
- `uv run pytest -k "test_parse_track"` - Run tests matching pattern
- `uv run mypy src/` - Run type checking on source code
- `uv run mypy src/ --show-error-codes` - Type checking with error codes

### Debugging
- `npx @modelcontextprotocol/inspector uv --directory /path/to/spotify_mcp run spotify-mcp` - Launch MCP Inspector for debugging

### Required Environment Variables
- `SPOTIFY_CLIENT_ID` - Spotify API Client ID
- `SPOTIFY_CLIENT_SECRET` - Spotify API Client Secret  
- `SPOTIFY_REDIRECT_URI` - Default: http://localhost:8888
- `LOGGING_PATH` - Optional: Path for log files

### Environment Configuration Priority
The application uses a sophisticated three-tier configuration system:
1. **Environment variables** (highest priority) - for MCP/production usage
2. **`.env` file** - for local development (optional, create in project root)
3. **pyproject.toml defaults** - fallback values configured in `[tool.spotify-mcp.env]`

This means you can:
- **MCP usage**: External env vars take precedence (no setup needed)
- **Local development**: Either set env vars, create a `.env` file, OR edit `pyproject.toml` defaults
- **Testing**: Zero setup required (uses `pytest-env` configuration)
- **New contributors**: Can get started immediately using `pyproject.toml` defaults

### Setting Up Development Credentials
Option 1 - Edit `pyproject.toml` (simplest):
```toml
[tool.spotify-mcp.env]
SPOTIFY_CLIENT_ID = "your_actual_client_id"
SPOTIFY_CLIENT_SECRET = "your_actual_client_secret"
```

Option 2 - Create `.env` file:
```bash
SPOTIFY_CLIENT_ID=your_actual_client_id
SPOTIFY_CLIENT_SECRET=your_actual_client_secret
```

Option 3 - Environment variables:
```bash
export SPOTIFY_CLIENT_ID=your_actual_client_id
export SPOTIFY_CLIENT_SECRET=your_actual_client_secret
```

## Architecture

This is a Model Context Protocol (MCP) server that integrates Claude with Spotify's Web API. Built using Python with `uv` as the package manager.

### Core Components

#### `src/spotify_mcp/server.py` 
- Main MCP server implementation using the `mcp` library
- Defines 8 MCP tools as Pydantic models that expose Spotify functionality:
  - `SpotifyPlayback` - Control playback (get/start/pause/skip)
  - `SpotifySearch` - Search tracks/albums/artists/playlists
  - `SpotifyQueue` - Manage playback queue (add/get)
  - `SpotifyGetInfo` - Get detailed item information
  - `SpotifyPlaylistManage` - Create/update/get playlist details
  - `SpotifyPlaylistItems` - Add/remove/update playlist tracks
  - `SpotifyUserPlaylists` - Get user playlists
  - `SpotifyPlaylistCover` - Manage playlist cover images

#### `src/spotify_mcp/spotify_api.py`
- Spotify API client wrapper using `spotipy` library
- Handles OAuth authentication with comprehensive scopes
- Implements all Spotify operations with error handling and logging
- Uses `@validate` decorator for auth/device validation

#### `src/spotify_mcp/utils.py`
- Data parsing utilities to normalize Spotify API responses
- Functions: `parse_track()`, `parse_artist()`, `parse_album()`, `parse_playlist()`
- Search query builder with advanced filters
- `@validate` decorator for authentication and device management

### Authentication Flow
- Uses SpotifyOAuth with required scopes for playback, playlists, and library access
- Token caching handled automatically by spotipy
- Device validation ensures active Spotify device for playback operations

### Deployment Options
1. **Local development**: Clone repo and run with `uv`
2. **Claude Desktop**: Add to MCP configuration with environment variables
3. **Smithery**: Automated installation via `npx @smithery/cli install`

### Dependencies
- **mcp**: Model Context Protocol framework
- **spotipy**: Spotify Web API wrapper (pinned to v2.24.0)
- **python-dotenv**: Environment variable loading
- **pydantic**: Data validation for MCP tools

## API Usage Analysis & Improvement Plan

### Current MCP Protocol Usage

**What We're Doing Well:**
- ✅ Implementing JSON-RPC 2.0 based MCP tools via Python SDK
- ✅ Using Pydantic models for tool input validation and schema generation
- ✅ Proper MCP server lifecycle management with stdio transport
- ✅ Tool discovery through `list_tools()` and execution via `call_tool()`
- ✅ Structured error handling with MCP-compliant responses

**Current Limitations:**
- ❌ Only using MCP Tools - missing Resources and Prompts capabilities
- ❌ No MCP-native OAuth/authentication flow implementation
- ❌ Limited use of MCP's real-time notification system
- ❌ Missing context-aware parameter completion
- ❌ No resource subscription or dynamic updates

### Current Spotify API Usage

**What We're Doing Well:**
- ✅ Comprehensive OAuth 2.0 Authorization Code Flow implementation
- ✅ Automatic token refresh via spotipy
- ✅ Broad scope coverage (playback, playlists, library, user data)
- ✅ Device validation and fallback handling
- ✅ Rate limiting awareness through spotipy

**Current Limitations:**
- ❌ Not leveraging Spotify's real-time features (Web Playback SDK integration)
- ❌ Limited pagination handling for large result sets
- ❌ Missing advanced search filters and recommendation endpoints
- ❌ No webhook support for playback state changes
- ❌ Authentication entirely external to MCP protocol

## Working Plan: MCP & Spotify Integration Improvements

### Phase 1: Enhanced MCP Protocol Adoption

**1. Implement MCP Resources**
```python
# Add dynamic resources for current user context
@server.list_resources()
async def list_resources():
    return [
        types.Resource(
            uri="spotify://user/current",
            name="Current User Profile",
            description="User's Spotify profile and preferences",
            mimeType="application/json"
        ),
        types.Resource(
            uri="spotify://playback/current", 
            name="Current Playback State",
            description="Real-time playback information",
            mimeType="application/json"
        )
    ]
```

**2. Add MCP Prompts for Common Workflows**
```python
@server.list_prompts()
async def list_prompts():
    return [
        types.Prompt(
            name="create_mood_playlist",
            description="Create a playlist based on mood and preferences",
            arguments=[
                types.PromptArgument(name="mood", description="Target mood")
            ]
        )
    ]
```

**3. Implement Real-time Notifications**
- Add playback state change notifications
- Implement resource update subscriptions
- Use MCP's notification system for live updates

### Phase 2: Advanced Authentication & Security

**1. MCP-Native OAuth Flow**
```python
# Implement OAuth via MCP sampling for user authorization
@server.call_tool()
async def handle_oauth_init():
    # Use MCP sampling to get user consent
    auth_url = spotify_client.get_authorization_url()
    result = await server.request_sampling({
        "messages": [{"role": "user", "content": f"Please visit: {auth_url}"}]
    })
    # Handle callback and token exchange
```

**2. Enhanced Security Patterns**
- Implement PKCE flow for better security
- Add token encryption at rest
- Implement scope-based permission checking

### Phase 3: Spotify API Feature Completeness

**1. Advanced Search & Discovery**
```python
class AdvancedSearch(ToolModel):
    """Advanced search with filters, recommendations, and AI-powered discovery."""
    query: str
    filters: Optional[Dict[str, Any]] = None  # year, genre, popularity, etc.
    include_recommendations: bool = False
    mood_analysis: bool = False  # AI-powered mood detection
```

**2. Real-time Playback Integration**
- Implement Web Playback SDK bridge
- Add real-time playback state monitoring
- Support for multiple device management

**3. Enhanced Playlist Intelligence**
```python
class SmartPlaylistCreate(ToolModel):
    """AI-powered playlist creation with advanced features."""
    description: str  # Natural language description
    seed_tracks: Optional[List[str]] = None
    mood: Optional[str] = None
    genre_mix: Optional[List[str]] = None
    duration_target: Optional[int] = None  # minutes
    energy_curve: Optional[str] = None  # "building", "steady", "declining"
```

### Phase 4: Performance & Reliability

**1. Implement Caching Strategy**
- Cache frequently accessed user data
- Implement smart cache invalidation
- Add offline capability for cached content

**2. Enhanced Error Handling**
```python
class SpotifyMCPError(Exception):
    """Custom exception with MCP-compliant error reporting."""
    def to_mcp_error(self) -> types.Error:
        return types.Error(
            code=self.error_code,
            message=self.message,
            data=self.additional_context
        )
```

**3. Rate Limiting & Quota Management**
- Implement intelligent request batching
- Add predictive rate limit handling
- Optimize API call patterns

### Phase 5: Advanced Features

**1. Multi-User Support**
- Add user context switching
- Implement shared playlist collaboration
- Support for organizational accounts

**2. Analytics & Insights**
```python
class SpotifyAnalytics(ToolModel):
    """Provide listening analytics and insights."""
    time_range: str = "medium_term"  # short, medium, long
    analysis_type: str = "listening_patterns"
    include_recommendations: bool = True
```

**3. Content Generation**
- AI-powered playlist descriptions
- Smart playlist cover generation
- Automatic playlist categorization

### Comparison with TypeScript Implementation

**Their Advantages:**
- Better TypeScript/Zod integration for type safety
- More comprehensive tool parameter completion
- Cleaner async/await patterns

**Our Advantages:**
- More mature error handling with logging
- Better device management logic
- More comprehensive scope handling

**Action Items:**
1. Adopt Zod-like validation patterns using Pydantic v2 features
2. Implement context-aware parameter completion
3. Add comprehensive type hints throughout codebase
4. Enhance async error handling patterns

### Implementation Priority

**High Priority:**
- [ ] Add MCP Resources for user/playback state
- [ ] Implement real-time notifications
- [ ] Enhanced error handling with MCP compliance
- [ ] Advanced search with filters

**Medium Priority:**
- [ ] MCP Prompts for common workflows
- [ ] PKCE OAuth flow
- [ ] Smart playlist creation
- [ ] Caching strategy

**Low Priority:**
- [ ] Multi-user support
- [ ] Analytics features
- [ ] Web Playback SDK integration
- [ ] Advanced AI features

This plan transforms the current functional MCP server into a state-of-the-art implementation that fully leverages both MCP protocol capabilities and Spotify API features.

## Testing Infrastructure

The project now includes comprehensive testing and type checking:

### Test Structure
- `tests/` - All test files
- `tests/conftest.py` - Pytest configuration and shared fixtures
- `tests/test_utils.py` - Tests for utility functions (parsing, search query building)
- `tests/test_server.py` - Tests for MCP server tools and handlers

### Key Testing Features
- **Async Support**: Configured for testing async functions with `pytest-asyncio`
- **Mocking**: Uses `pytest-mock` for mocking Spotify API calls and authentication
- **Fixtures**: Provides sample data fixtures for tracks, playlists, artists
- **Environment Management**: Test env vars configured in `pyproject.toml` via `pytest-env`
- **Zero Setup Testing**: No `.env` file or credentials needed for tests

### Type Checking
- **MyPy Configuration**: Strict type checking with comprehensive rules
- **External Library Handling**: Ignores missing imports for `spotipy` and `dotenv`
- **Return Type Annotations**: All functions have proper return type hints

### Current Test Coverage
- ✅ Utils module: All parsing functions, search query building
- ✅ Server module: Tool schema generation, basic tool handlers
- ✅ Error handling: Invalid inputs, missing parameters
- ❌ Spotify API client: Needs integration tests
- ❌ Authentication flows: Needs mocked OAuth tests

### Running Tests Safely
All tests use mocked Spotify clients and environment variables, so they can run without:
- Real Spotify API credentials
- Network connectivity
- Spotify Premium account

This ensures safe development and CI/CD integration.