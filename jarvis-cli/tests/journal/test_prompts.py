"""Tests for journal AI prompts module."""

from jarvis.journal.prompts import (
    DEEP_DIVE_PROMPT,
    DEEP_DIVE_SYSTEM,
    INSIGHTS_PROMPT,
    INSIGHTS_SYSTEM,
    METADATA_EXTRACTION_PROMPT,
    METADATA_EXTRACTION_SYSTEM,
    TITLE_GENERATION_PROMPT,
    TITLE_GENERATION_SYSTEM,
    format_deep_dive_prompt,
    format_insights_prompt,
    format_metadata_prompt,
    format_title_prompt,
)


class TestPromptConstants:
    """Tests for prompt constant definitions."""

    def test_title_system_prompt_exists(self) -> None:
        """Test that title system prompt is defined."""
        assert TITLE_GENERATION_SYSTEM
        assert "concise" in TITLE_GENERATION_SYSTEM.lower()
        assert "3-7 words" in TITLE_GENERATION_SYSTEM

    def test_title_prompt_has_placeholder(self) -> None:
        """Test that title prompt has content placeholder."""
        assert "{content}" in TITLE_GENERATION_PROMPT

    def test_deep_dive_system_prompt_exists(self) -> None:
        """Test that deep dive system prompt is defined."""
        assert DEEP_DIVE_SYSTEM
        assert "thoughtful" in DEEP_DIVE_SYSTEM.lower()

    def test_deep_dive_prompt_has_placeholders(self) -> None:
        """Test that deep dive prompt has required placeholders."""
        assert "{content}" in DEEP_DIVE_PROMPT
        assert "{focus}" in DEEP_DIVE_PROMPT

    def test_insights_system_prompt_exists(self) -> None:
        """Test that insights system prompt is defined."""
        assert INSIGHTS_SYSTEM
        assert "pattern" in INSIGHTS_SYSTEM.lower()

    def test_insights_prompt_has_placeholders(self) -> None:
        """Test that insights prompt has required placeholders."""
        assert "{entries}" in INSIGHTS_PROMPT
        assert "{time_range}" in INSIGHTS_PROMPT
        assert "{count}" in INSIGHTS_PROMPT

    def test_metadata_system_prompt_exists(self) -> None:
        """Test that metadata system prompt is defined."""
        assert METADATA_EXTRACTION_SYSTEM
        assert "json" in METADATA_EXTRACTION_SYSTEM.lower()

    def test_metadata_prompt_has_placeholder(self) -> None:
        """Test that metadata prompt has content placeholder."""
        assert "{content}" in METADATA_EXTRACTION_PROMPT


class TestFormatTitlePrompt:
    """Tests for format_title_prompt function."""

    def test_formats_content(self) -> None:
        """Test that content is inserted into prompt."""
        result = format_title_prompt("Had a great day today")
        assert "Had a great day today" in result
        assert "{content}" not in result

    def test_preserves_structure(self) -> None:
        """Test that prompt structure is preserved."""
        result = format_title_prompt("Test content")
        assert "Title:" in result
        assert "---" in result

    def test_handles_multiline_content(self) -> None:
        """Test formatting with multiline content."""
        content = "Line 1\nLine 2\nLine 3"
        result = format_title_prompt(content)
        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 3" in result


class TestFormatDeepDivePrompt:
    """Tests for format_deep_dive_prompt function."""

    def test_formats_content_and_focus(self) -> None:
        """Test that both content and focus are inserted."""
        result = format_deep_dive_prompt("My journal entry", "explore feelings")
        assert "My journal entry" in result
        assert "explore feelings" in result
        assert "{content}" not in result
        assert "{focus}" not in result

    def test_preserves_structure(self) -> None:
        """Test that prompt structure is preserved."""
        result = format_deep_dive_prompt("Content", "Focus")
        assert "deep dive" in result.lower()
        assert "---" in result


class TestFormatInsightsPrompt:
    """Tests for format_insights_prompt function."""

    def test_formats_all_placeholders(self) -> None:
        """Test that all placeholders are replaced."""
        entries = "Entry 1\n---\nEntry 2"
        time_range = "Jan 10 - Jan 24"
        count = 5

        result = format_insights_prompt(entries, time_range, count)

        assert "Entry 1" in result
        assert "Entry 2" in result
        assert "Jan 10 - Jan 24" in result
        assert "5" in result
        assert "{entries}" not in result
        assert "{time_range}" not in result
        assert "{count}" not in result

    def test_preserves_structure(self) -> None:
        """Test that prompt structure is preserved."""
        result = format_insights_prompt("Entries", "Range", 1)
        assert "Analyze" in result
        assert "themes" in result.lower()
        assert "patterns" in result.lower()


class TestFormatMetadataPrompt:
    """Tests for format_metadata_prompt function."""

    def test_formats_content(self) -> None:
        """Test that content is inserted."""
        result = format_metadata_prompt("Today I worked on the project")
        assert "Today I worked on the project" in result
        assert "{content}" not in result

    def test_preserves_structure(self) -> None:
        """Test that prompt structure is preserved."""
        result = format_metadata_prompt("Content")
        assert "JSON:" in result
        assert "Extract" in result


class TestPromptGuidelines:
    """Tests ensuring prompts follow best practices."""

    def test_system_prompts_have_clear_role(self) -> None:
        """Test that system prompts define a clear role."""
        assert "You are" in TITLE_GENERATION_SYSTEM
        assert "You are" in DEEP_DIVE_SYSTEM
        assert "You are" in INSIGHTS_SYSTEM
        assert "You extract" in METADATA_EXTRACTION_SYSTEM

    def test_prompts_use_separators(self) -> None:
        """Test that user content is separated from instructions."""
        for prompt in [
            TITLE_GENERATION_PROMPT,
            DEEP_DIVE_PROMPT,
            INSIGHTS_PROMPT,
            METADATA_EXTRACTION_PROMPT,
        ]:
            assert "---" in prompt

    def test_title_prompt_asks_for_only_title(self) -> None:
        """Test that title generation asks for only the title."""
        assert "ONLY the title" in TITLE_GENERATION_SYSTEM

    def test_deep_dive_has_length_guidance(self) -> None:
        """Test that deep dive has paragraph length guidance."""
        assert "2-4 paragraphs" in DEEP_DIVE_PROMPT

    def test_insights_has_structured_output(self) -> None:
        """Test that insights prompt asks for structured output."""
        assert "1." in INSIGHTS_PROMPT
        assert "2." in INSIGHTS_PROMPT
        assert "3." in INSIGHTS_PROMPT

    def test_metadata_has_json_example(self) -> None:
        """Test that metadata extraction includes an example."""
        assert "Example:" in METADATA_EXTRACTION_SYSTEM
        assert "tags" in METADATA_EXTRACTION_SYSTEM
        assert "mood" in METADATA_EXTRACTION_SYSTEM
        assert "topics" in METADATA_EXTRACTION_SYSTEM
