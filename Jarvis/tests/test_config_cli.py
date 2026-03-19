"""Tests for config CLI commands."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from jarvis.cli import cli
from jarvis.config import clear_config_cache, init_config


class TestConfigCommands:
    """Tests for jarvis config commands."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_config_help(self, runner: CliRunner) -> None:
        """Test config command shows help."""
        result = runner.invoke(cli, ["config", "--help"])
        assert result.exit_code == 0
        assert "backend" in result.output
        assert "capabilities" in result.output
        assert "show" in result.output
        assert "init" in result.output

    def test_config_path(self, runner: CliRunner) -> None:
        """Test config path command shows the path."""
        result = runner.invoke(cli, ["config", "path"])
        assert result.exit_code == 0
        assert ".jarvis/config.yaml" in result.output

    def test_config_backend_show(self, runner: CliRunner) -> None:
        """Test config backend shows current backend."""
        result = runner.invoke(cli, ["config", "backend"])
        assert result.exit_code == 0
        assert "Active backend" in result.output
        assert "anytype" in result.output.lower() or "notion" in result.output.lower()

    def test_config_backend_invalid(self, runner: CliRunner) -> None:
        """Test config backend with invalid backend name."""
        result = runner.invoke(cli, ["config", "backend", "invalid_backend"])
        assert "Invalid backend" in result.output

    def test_config_capabilities(self, runner: CliRunner) -> None:
        """Test config capabilities shows capabilities."""
        result = runner.invoke(cli, ["config", "capabilities"])
        # Should show capabilities or error (depending on backend availability)
        assert "Capabilities for" in result.output or "Error" in result.output

    def test_config_show(self, runner: CliRunner) -> None:
        """Test config show runs."""
        result = runner.invoke(cli, ["config", "show"])
        # Either shows config or says no config file
        assert "Configuration File" in result.output
        assert result.exit_code == 0


class TestConfigBackendCommand:
    """Detailed tests for config backend command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_backend_lists_options(self, runner: CliRunner) -> None:
        """Test backend command lists available backends."""
        result = runner.invoke(cli, ["config", "backend"])
        assert "anytype" in result.output
        assert "notion" in result.output
        assert "Available backends" in result.output


class TestConfigInitCommand:
    """Tests for config init command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_config_init_help(self, runner: CliRunner) -> None:
        """Test config init --help shows options."""
        result = runner.invoke(cli, ["config", "init", "--help"])
        assert result.exit_code == 0
        assert "--force" in result.output

    def test_config_init_creates_file(self, tmp_path: Path) -> None:
        """Test config init creates config file when using custom path."""
        config_file = tmp_path / "test_config.yaml"

        # Clear any cached config
        clear_config_cache()

        # Use init_config directly to test file creation
        path = init_config(config_path=config_file, force=True)
        assert path.exists()
        assert path == config_file

        # Check content
        content = config_file.read_text()
        assert "active_backend" in content
        assert "anytype" in content
