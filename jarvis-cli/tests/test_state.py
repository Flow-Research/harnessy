"""Tests for state management."""

import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

from jarvis.models import Suggestion
from jarvis.state import (
    clear_suggestions,
    has_pending_suggestions,
    load_suggestions,
    save_suggestions,
)


def make_suggestion(
    id: str = "sug_001",
    task_name: str = "Test task",
    status: str = "pending",
) -> Suggestion:
    """Helper to create a suggestion for testing."""
    return Suggestion(
        id=id,
        task_id="task_1",
        task_name=task_name,
        current_date=date.today(),
        proposed_date=date.today() + timedelta(days=2),
        reasoning="Test reason",
        confidence=0.8,
        status=status,  # type: ignore[arg-type]
        created_at=datetime.now(),
    )


class TestSaveSuggestions:
    """Tests for save_suggestions function."""

    def test_saves_to_file(self) -> None:
        """Test that suggestions are saved to disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / ".jarvis"

            with mock.patch("jarvis.state.DATA_DIR", data_dir):
                with mock.patch("jarvis.state.PENDING_FILE", data_dir / "pending.json"):
                    suggestions = [make_suggestion()]
                    save_suggestions(suggestions, "space_123")

                    assert (data_dir / "pending.json").exists()

    def test_creates_directory(self) -> None:
        """Test that data directory is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "nested" / ".jarvis"

            with mock.patch("jarvis.state.DATA_DIR", data_dir):
                with mock.patch("jarvis.state.PENDING_FILE", data_dir / "pending.json"):
                    save_suggestions([make_suggestion()], "space_123")

                    assert data_dir.exists()


class TestLoadSuggestions:
    """Tests for load_suggestions function."""

    def test_load_nonexistent(self) -> None:
        """Test loading when no file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pending_file = Path(tmpdir) / "pending.json"

            with mock.patch("jarvis.state.PENDING_FILE", pending_file):
                suggestions, space_id = load_suggestions()

                assert suggestions == []
                assert space_id == ""

    def test_round_trip(self) -> None:
        """Test saving and loading suggestions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / ".jarvis"
            pending_file = data_dir / "pending.json"

            with mock.patch("jarvis.state.DATA_DIR", data_dir):
                with mock.patch("jarvis.state.PENDING_FILE", pending_file):
                    original = [
                        make_suggestion("sug_1", "Task 1"),
                        make_suggestion("sug_2", "Task 2"),
                    ]
                    save_suggestions(original, "space_abc")

                    loaded, space_id = load_suggestions()

                    assert len(loaded) == 2
                    assert space_id == "space_abc"
                    assert loaded[0].task_name == "Task 1"
                    assert loaded[1].task_name == "Task 2"


class TestClearSuggestions:
    """Tests for clear_suggestions function."""

    def test_clears_existing_file(self) -> None:
        """Test that pending.json is deleted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / ".jarvis"
            pending_file = data_dir / "pending.json"

            with mock.patch("jarvis.state.DATA_DIR", data_dir):
                with mock.patch("jarvis.state.PENDING_FILE", pending_file):
                    save_suggestions([make_suggestion()], "space_123")
                    assert pending_file.exists()

                    clear_suggestions()
                    assert not pending_file.exists()

    def test_no_error_if_not_exists(self) -> None:
        """Test that clearing nonexistent file doesn't error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pending_file = Path(tmpdir) / "pending.json"

            with mock.patch("jarvis.state.PENDING_FILE", pending_file):
                clear_suggestions()  # Should not raise


class TestHasPendingSuggestions:
    """Tests for has_pending_suggestions function."""

    def test_no_file(self) -> None:
        """Test returns False when no file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pending_file = Path(tmpdir) / "pending.json"

            with mock.patch("jarvis.state.PENDING_FILE", pending_file):
                assert has_pending_suggestions() is False

    def test_has_pending(self) -> None:
        """Test returns True when there are pending suggestions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / ".jarvis"
            pending_file = data_dir / "pending.json"

            with mock.patch("jarvis.state.DATA_DIR", data_dir):
                with mock.patch("jarvis.state.PENDING_FILE", pending_file):
                    save_suggestions([make_suggestion(status="pending")], "space_123")

                    assert has_pending_suggestions() is True

    def test_no_pending(self) -> None:
        """Test returns False when all suggestions are applied."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / ".jarvis"
            pending_file = data_dir / "pending.json"

            with mock.patch("jarvis.state.DATA_DIR", data_dir):
                with mock.patch("jarvis.state.PENDING_FILE", pending_file):
                    save_suggestions([make_suggestion(status="applied")], "space_123")

                    assert has_pending_suggestions() is False
