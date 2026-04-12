"""Tests for jarvis.wiki.research private helpers.

Covers `_make_session_id`, `_extract_trailing_json`, and
`_validate_research_file` — the pure pieces of the research orchestrator
that don't need to spawn an agent.
"""

import re
from pathlib import Path

from jarvis.wiki.research import (
    TRACE_SKILL_NAME,
    _extract_trailing_json,
    _make_session_id,
    _validate_research_file,
)


class TestMakeSessionId:
    def test_format_is_timestamp_plus_short_id(self) -> None:
        sid = _make_session_id()
        # Pattern: YYYYMMDD-HHMMSS-<8-hex-chars>
        assert re.match(r"^\d{8}-\d{6}-[0-9a-f]{8}$", sid), sid

    def test_unique_across_calls(self) -> None:
        ids = {_make_session_id() for _ in range(20)}
        # 20 calls in microseconds — collisions are vanishingly unlikely
        assert len(ids) == 20


class TestTraceSkillName:
    def test_constant_is_set(self) -> None:
        assert TRACE_SKILL_NAME == "wiki-research"


class TestExtractTrailingJson:
    """_extract_trailing_json finds the LAST balanced {...} in agent output."""

    def test_simple_object(self) -> None:
        result = _extract_trailing_json('{"session_id": "abc", "x": 1}')
        assert result == {"session_id": "abc", "x": 1}

    def test_object_after_prose(self) -> None:
        text = "Here is the summary.\n\nMore text.\n\n" + '{"key": "value"}'
        assert _extract_trailing_json(text) == {"key": "value"}

    def test_object_inside_fenced_block(self) -> None:
        text = 'Some preamble.\n\n```json\n{"key": "value", "nested": {"inner": 42}}\n```\n'
        result = _extract_trailing_json(text)
        assert result == {"key": "value", "nested": {"inner": 42}}

    def test_picks_last_object_when_multiple_present(self) -> None:
        text = 'Earlier example: {"old": true}\n\nMore prose.\n\n{"final": "answer"}'
        # Walks from the end → finds the last balanced block
        assert _extract_trailing_json(text) == {"final": "answer"}

    def test_handles_nested_braces(self) -> None:
        text = '{"outer": {"middle": {"inner": "value"}}}'
        result = _extract_trailing_json(text)
        assert result == {"outer": {"middle": {"inner": "value"}}}

    def test_empty_input(self) -> None:
        assert _extract_trailing_json("") is None
        assert _extract_trailing_json("   \n  ") is None

    def test_no_json_returns_none(self) -> None:
        assert _extract_trailing_json("Just some text without JSON.") is None

    def test_unbalanced_braces_returns_none(self) -> None:
        # The walker will find a `}` and try to balance backward, but no
        # matching `{` exists, so it returns None.
        assert _extract_trailing_json("text }") is None

    def test_invalid_json_returns_none(self) -> None:
        # Looks like JSON but isn't parseable
        assert _extract_trailing_json('{"key": value-without-quotes}') is None

    def test_array_at_end_returns_none(self) -> None:
        """Top-level arrays aren't dicts; the helper requires a dict."""
        # Walker only matches braces, so an array won't be found
        assert _extract_trailing_json('["a", "b"]') is None


class TestValidateResearchFile:
    """_validate_research_file enforces the agent's file-write contract."""

    def _good_file(self, tmp_path: Path, name: str = "2026-04-12-test.md") -> Path:
        path = tmp_path / name
        path.write_text(
            "---\n"
            "source_url: https://example.com/foo\n"
            "source_title: Foo\n"
            "research_session: test-session-001\n"
            "fetched_at: 2026-04-12T05:00:00\n"
            "---\n"
            "\n"
            "# Foo\n\n" + "Body content. " * 30,  # > 200 bytes
            encoding="utf-8",
        )
        return path

    def test_valid_file_passes(self, tmp_path: Path) -> None:
        path = self._good_file(tmp_path)
        ok, reason = _validate_research_file(path)
        assert ok is True
        assert reason == "ok"

    def test_missing_file_fails(self, tmp_path: Path) -> None:
        ok, reason = _validate_research_file(tmp_path / "nonexistent.md")
        assert ok is False
        assert "unreadable" in reason

    def test_too_short_fails(self, tmp_path: Path) -> None:
        path = tmp_path / "tiny.md"
        path.write_text("---\nsource_url: x\n---\nshort\n", encoding="utf-8")
        ok, reason = _validate_research_file(path)
        assert ok is False
        assert "too short" in reason

    def test_missing_frontmatter_fails(self, tmp_path: Path) -> None:
        path = tmp_path / "no-fm.md"
        path.write_text("# No frontmatter\n\n" + ("body. " * 50), encoding="utf-8")
        ok, reason = _validate_research_file(path)
        assert ok is False
        assert "missing frontmatter" in reason

    def test_missing_source_url_fails(self, tmp_path: Path) -> None:
        path = tmp_path / "no-url.md"
        path.write_text(
            "---\ntitle: Foo\nresearch_session: test\n---\n\n" + "body. " * 50,
            encoding="utf-8",
        )
        ok, reason = _validate_research_file(path)
        assert ok is False
        assert "source_url" in reason

    def test_missing_research_session_fails(self, tmp_path: Path) -> None:
        path = tmp_path / "no-session.md"
        path.write_text(
            "---\nsource_url: https://example.com\ntitle: Foo\n---\n\n" + "body. " * 50,
            encoding="utf-8",
        )
        ok, reason = _validate_research_file(path)
        assert ok is False
        assert "research_session" in reason
