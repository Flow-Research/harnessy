"""Tests for status CLI command."""

import pytest
from click.testing import CliRunner

from jarvis.cli import cli


class TestStatusCommand:
    """Tests for jarvis status command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_status_help(self, runner: CliRunner) -> None:
        """Test status --help shows options."""
        result = runner.invoke(cli, ["status", "--help"])
        assert result.exit_code == 0
        assert "--diagnose" in result.output
        assert "connection" in result.output.lower()

    def test_status_shows_backend(self, runner: CliRunner) -> None:
        """Test status command shows backend info."""
        result = runner.invoke(cli, ["status"])
        # Should always show backend info (even if connection fails)
        assert "Backend:" in result.output

    def test_status_shows_jarvis_status_header(self, runner: CliRunner) -> None:
        """Test status command shows the Jarvis Status header."""
        result = runner.invoke(cli, ["status"])
        assert "Jarvis Status" in result.output

    def test_status_diagnose_flag(self, runner: CliRunner) -> None:
        """Test status --diagnose runs diagnostics."""
        result = runner.invoke(cli, ["status", "--diagnose"])
        # Diagnostics section should appear
        assert "Diagnostics" in result.output or "Cannot connect" in result.output


class TestStatusDiagnostics:
    """Tests for status diagnostics functionality."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_diagnose_checks_config_file(self, runner: CliRunner) -> None:
        """Test that diagnostics check for config file."""
        result = runner.invoke(cli, ["status", "--diagnose"])
        # Should mention config file in diagnostics
        output = result.output.lower()
        assert "config" in output or "configuration" in output
