"""Tests for task CLI commands."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from jarvis.cli import cli
from jarvis.models import Task


class TestTaskCreateCommand:
    """Tests for task create command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_create_requires_title(self, runner: CliRunner) -> None:
        """Test that title is required."""
        result = runner.invoke(cli, ["task", "create"])
        assert result.exit_code != 0
        assert "Missing argument" in result.output

    def test_title_too_long(self, runner: CliRunner) -> None:
        """Test that title is limited to 500 chars."""
        long_title = "x" * 501
        result = runner.invoke(cli, ["task", "create", long_title])
        assert "Title too long" in result.output
        assert result.exit_code == 1

    def test_invalid_priority_rejected(self, runner: CliRunner) -> None:
        """Test that invalid priority values are rejected."""
        result = runner.invoke(cli, ["task", "create", "Test", "-p", "invalid"])
        assert result.exit_code != 0

    def test_invalid_date_shows_error(self, runner: CliRunner) -> None:
        """Test that invalid date shows helpful error."""
        result = runner.invoke(cli, ["task", "create", "Test", "-d", "notadate"])
        assert "Could not parse date" in result.output
        assert result.exit_code == 1

    def test_t_alias_shows_help(self, runner: CliRunner) -> None:
        """Test that 't' alias works."""
        result = runner.invoke(cli, ["t", "--help"])
        assert result.exit_code == 0
        # Check for key elements in help output
        assert "TITLE" in result.output or "title" in result.output.lower()

    def test_task_create_help(self, runner: CliRunner) -> None:
        """Test task create help output."""
        result = runner.invoke(cli, ["task", "create", "--help"])
        assert result.exit_code == 0
        assert "--due" in result.output
        assert "--priority" in result.output
        assert "--tag" in result.output
        assert "--editor" in result.output

    @patch("jarvis.task.cli.get_adapter")
    @patch("jarvis.task.cli._get_space")
    def test_successful_task_creation(
        self,
        mock_get_space: MagicMock,
        mock_get_adapter: MagicMock,
        runner: CliRunner,
    ) -> None:
        """Test successful task creation."""
        # Setup mocks
        mock_adapter = MagicMock()
        mock_get_adapter.return_value = mock_adapter

        # Mock create_task to return a Task object
        now = datetime.now()
        mock_task = Task(
            id="task-id-123",
            space_id="space-id",
            title="Test Task",
            created_at=now,
            updated_at=now,
        )
        mock_adapter.create_task.return_value = mock_task

        mock_get_space.return_value = ("space-id", "Test Space")

        result = runner.invoke(cli, ["task", "create", "Test Task", "-d", "tomorrow"])

        assert result.exit_code == 0
        assert "Created" in result.output
        assert "Test Task" in result.output

    def test_too_many_tags(self, runner: CliRunner) -> None:
        """Test that too many tags are rejected."""
        # Create 21 tag arguments
        tags = [f"-t tag{i}" for i in range(21)]
        cmd = ["task", "create", "Test"] + " ".join(tags).split()
        result = runner.invoke(cli, cmd)
        assert "Too many tags" in result.output
        assert result.exit_code == 1
