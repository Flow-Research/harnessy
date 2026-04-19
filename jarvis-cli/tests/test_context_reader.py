"""Tests for context reader."""

import tempfile
from pathlib import Path

from jarvis.context_reader import get_context_summary, load_context


class TestLoadContext:
    """Tests for load_context function."""

    def test_load_from_nonexistent_path(self) -> None:
        """Test loading context from a path that doesn't exist."""
        context = load_context(Path("/nonexistent/path"))

        assert context.preferences_raw == ""
        assert context.patterns_raw == ""
        assert context.constraints_raw == ""
        assert context.priorities_raw == ""
        assert not context.has_context

    def test_load_from_empty_directory(self) -> None:
        """Test loading context from an empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            context = load_context(Path(tmpdir))

            assert context.preferences_raw == ""
            assert not context.has_context

    def test_load_partial_context(self) -> None:
        """Test loading context when only some files exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create only preferences.md
            (tmppath / "preferences.md").write_text("- Morning deep work")

            context = load_context(tmppath)

            assert "Morning deep work" in context.preferences_raw
            assert context.patterns_raw == ""
            assert context.has_context

    def test_load_full_context(self) -> None:
        """Test loading context when all files exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            (tmppath / "preferences.md").write_text("Preferences content")
            (tmppath / "patterns.md").write_text("Patterns content")
            (tmppath / "constraints.md").write_text("Constraints content")
            (tmppath / "priorities.md").write_text("Priorities content")

            context = load_context(tmppath)

            assert context.preferences_raw == "Preferences content"
            assert context.patterns_raw == "Patterns content"
            assert context.constraints_raw == "Constraints content"
            assert context.priorities_raw == "Priorities content"
            assert context.has_context

    def test_preserves_markdown_formatting(self) -> None:
        """Test that markdown content is preserved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            markdown_content = """# Preferences

## Time of Day
- Deep work: 9am-12pm
- Meetings: 2pm-5pm

## Notes
Some **bold** and *italic* text.
"""
            (tmppath / "preferences.md").write_text(markdown_content)

            context = load_context(tmppath)

            assert "# Preferences" in context.preferences_raw
            assert "**bold**" in context.preferences_raw


class TestGetContextSummary:
    """Tests for get_context_summary function."""

    def test_empty_summary(self) -> None:
        """Test summary for empty context."""
        context = load_context(Path("/nonexistent"))
        summary = get_context_summary(context)

        assert summary["preferences.md"] is False
        assert summary["patterns.md"] is False
        assert summary["constraints.md"] is False
        assert summary["priorities.md"] is False

    def test_partial_summary(self) -> None:
        """Test summary with partial content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "preferences.md").write_text("Content")
            (tmppath / "constraints.md").write_text("Content")

            context = load_context(tmppath)
            summary = get_context_summary(context)

            assert summary["preferences.md"] is True
            assert summary["patterns.md"] is False
            assert summary["constraints.md"] is True
            assert summary["priorities.md"] is False
