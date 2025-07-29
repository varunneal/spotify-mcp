"""Tests for MCP prompts functionality."""
from typing import Dict, Any

import pytest
import mcp.types as types

from spotify_mcp.server import handle_list_prompts, handle_get_prompt


class TestListPrompts:
    """Tests for handle_list_prompts function."""
    
    @pytest.mark.asyncio
    async def test_handle_list_prompts(self) -> None:
        """Test that handle_list_prompts returns expected prompts."""
        prompts = await handle_list_prompts()
        
        assert len(prompts) == 5
        prompt_names = [prompt.name for prompt in prompts]
        
        expected_prompts = [
            "create_mood_playlist",
            "discover_similar_music",
            "party_playlist_generator", 
            "workout_playlist_builder",
            "focus_music_curator"
        ]
        
        for expected_prompt in expected_prompts:
            assert expected_prompt in prompt_names
        
        # Check that all prompts have proper structure
        for prompt in prompts:
            assert isinstance(prompt, types.Prompt)
            assert prompt.name
            assert prompt.description
            assert isinstance(prompt.arguments, list)


class TestGetPrompt:
    """Tests for handle_get_prompt function."""
    
    @pytest.mark.asyncio
    async def test_get_mood_playlist_prompt(self) -> None:
        """Test get_prompt for mood playlist creation."""
        result = await handle_get_prompt("create_mood_playlist", {
            "mood": "energetic",
            "genre": "rock", 
            "decade": "2000s"
        })
        
        assert isinstance(result, types.GetPromptResult)
        assert "energetic" in result.description
        assert len(result.messages) == 1
        
        message = result.messages[0]
        assert message.role == "user"
        assert isinstance(message.content, types.TextContent)
        assert "energetic" in message.content.text
        assert "rock" in message.content.text
        assert "2000s" in message.content.text
        assert "AdvancedSearch" in message.content.text
    
    @pytest.mark.asyncio
    async def test_get_mood_playlist_prompt_minimal(self) -> None:
        """Test get_prompt for mood playlist with minimal arguments."""
        result = await handle_get_prompt("create_mood_playlist", {"mood": "chill"})
        
        assert isinstance(result, types.GetPromptResult)
        assert "chill" in result.description
        
        message = result.messages[0]
        assert "chill" in message.content.text
        assert "Chill Vibes" in message.content.text
    
    @pytest.mark.asyncio
    async def test_get_discover_music_prompt(self) -> None:
        """Test get_prompt for music discovery."""
        result = await handle_get_prompt("discover_similar_music", {
            "reference": "Taylor Swift",
            "discovery_level": "deep_cuts"
        })
        
        assert isinstance(result, types.GetPromptResult)
        assert "Taylor Swift" in result.description
        
        message = result.messages[0]
        assert "Taylor Swift" in message.content.text
        assert "deep_cuts" in message.content.text
        assert "lesser-known tracks" in message.content.text
    
    @pytest.mark.asyncio
    async def test_get_party_playlist_prompt(self) -> None:
        """Test get_prompt for party playlist generation."""
        result = await handle_get_prompt("party_playlist_generator", {
            "party_type": "dance_party",
            "duration_hours": "4"
        })
        
        assert isinstance(result, types.GetPromptResult)
        assert "dance_party" in result.description
        
        message = result.messages[0]
        assert "dance_party" in message.content.text
        assert "4 hours" in message.content.text
        assert "60 tracks" in message.content.text  # ~15 tracks per hour * 4
        assert "Dance Party Mix" in message.content.text
    
    @pytest.mark.asyncio
    async def test_get_workout_playlist_prompt(self) -> None:
        """Test get_prompt for workout playlist building."""
        result = await handle_get_prompt("workout_playlist_builder", {
            "workout_type": "cardio",
            "intensity": "high"
        })
        
        assert isinstance(result, types.GetPromptResult)
        assert "cardio" in result.description
        
        message = result.messages[0]
        assert "cardio" in message.content.text
        assert "high" in message.content.text
        assert "120-140" in message.content.text  # BPM for cardio
        assert "Cardio Power - High" in message.content.text
    
    @pytest.mark.asyncio
    async def test_get_focus_music_prompt(self) -> None:
        """Test get_prompt for focus music curation."""
        result = await handle_get_prompt("focus_music_curator", {
            "focus_type": "coding",
            "noise_level": "minimal"
        })
        
        assert isinstance(result, types.GetPromptResult)
        assert "coding" in result.description
        
        message = result.messages[0]
        assert "coding" in message.content.text
        assert "minimal" in message.content.text
        assert "Deep Focus - Coding" in message.content.text
        assert "instrumental" in message.content.text
    
    @pytest.mark.asyncio
    async def test_get_prompt_with_defaults(self) -> None:
        """Test get_prompt with missing arguments uses defaults."""
        result = await handle_get_prompt("create_mood_playlist", None)
        
        assert isinstance(result, types.GetPromptResult)
        message = result.messages[0]
        assert "happy" in message.content.text  # Default mood
    
    @pytest.mark.asyncio
    async def test_get_prompt_unknown_name(self) -> None:
        """Test get_prompt with unknown prompt name."""
        with pytest.raises(Exception):  # Should raise SpotifyMCPError
            await handle_get_prompt("unknown_prompt", {})
    
    @pytest.mark.asyncio
    async def test_prompt_content_quality(self) -> None:
        """Test that prompt content includes all necessary elements."""
        result = await handle_get_prompt("create_mood_playlist", {
            "mood": "relaxing",
            "genre": "jazz"
        })
        
        message = result.messages[0]
        content = message.content.text
        
        # Check for structured workflow
        assert "1." in content and "2." in content and "3." in content
        
        # Check for specific tool mentions
        assert "AdvancedSearch" in content
        
        # Check for playlist creation steps
        assert "playlist" in content.lower()
        assert "tracks" in content.lower()
        
        # Check for goal/outcome
        assert "goal" in content.lower() or "experience" in content.lower()
    
    @pytest.mark.asyncio
    async def test_all_prompts_generate_valid_content(self) -> None:
        """Test that all prompts generate valid content."""
        prompt_tests = [
            ("create_mood_playlist", {"mood": "happy"}),
            ("discover_similar_music", {"reference": "Beatles"}),
            ("party_playlist_generator", {"party_type": "house_party"}),
            ("workout_playlist_builder", {"workout_type": "running"}),
            ("focus_music_curator", {"focus_type": "studying"})
        ]
        
        for prompt_name, args in prompt_tests:
            result = await handle_get_prompt(prompt_name, args)
            
            assert isinstance(result, types.GetPromptResult)
            assert result.description
            assert len(result.messages) == 1
            
            message = result.messages[0]
            assert message.role == "user"
            assert isinstance(message.content, types.TextContent)
            assert len(message.content.text) > 100  # Substantial content
            
            # Each prompt should mention the key argument
            key_arg = list(args.values())[0]
            assert key_arg in message.content.text