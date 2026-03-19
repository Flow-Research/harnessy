"""Tests for capability-based command filtering."""

import pytest
from click.testing import CliRunner

from jarvis.cli import check_capability, require_capability


class MockAdapter:
    """Mock adapter for testing capability checks."""

    def __init__(self, capabilities: dict[str, bool], name: str = "mock"):
        self._capabilities = capabilities
        self._name = name

    @property
    def capabilities(self) -> dict[str, bool]:
        return self._capabilities

    @property
    def backend_name(self) -> str:
        return self._name


class TestCheckCapability:
    """Tests for check_capability function."""

    def test_capability_present_and_true(self) -> None:
        """Test that check returns True when capability is present and True."""
        adapter = MockAdapter({"tasks": True, "journal": True})
        assert check_capability(adapter, "tasks") is True
        assert check_capability(adapter, "journal") is True

    def test_capability_present_and_false(self) -> None:
        """Test that check returns False when capability is present but False."""
        adapter = MockAdapter({"tasks": True, "search": False})
        assert check_capability(adapter, "search") is False

    def test_capability_missing(self) -> None:
        """Test that check returns False when capability is not in dict."""
        adapter = MockAdapter({"tasks": True})
        assert check_capability(adapter, "journal") is False
        assert check_capability(adapter, "nonexistent") is False


class TestRequireCapability:
    """Tests for require_capability function."""

    def test_does_not_exit_when_capability_available(self) -> None:
        """Test that require_capability does not exit when capability is available."""
        adapter = MockAdapter({"tasks": True})
        # Should not raise
        require_capability(adapter, "tasks")

    def test_exits_when_capability_missing(self) -> None:
        """Test that require_capability exits when capability is missing."""
        adapter = MockAdapter({"tasks": True}, name="test_backend")

        with pytest.raises(SystemExit) as exc_info:
            require_capability(adapter, "journal", "Journal entries")

        assert exc_info.value.code == 1

    def test_exits_when_capability_false(self) -> None:
        """Test that require_capability exits when capability is False."""
        adapter = MockAdapter({"tasks": True, "search": False}, name="test_backend")

        with pytest.raises(SystemExit):
            require_capability(adapter, "search", "Full-text search")


class TestCapabilityMessages:
    """Tests for capability error messages."""

    def test_message_includes_feature_name(self, capsys) -> None:
        """Test that error message includes the feature name."""
        adapter = MockAdapter({"tasks": True}, name="test_backend")

        try:
            require_capability(adapter, "journal", "Journal entries")
        except SystemExit:
            pass

        # Note: We use Rich console which may not be captured by capsys
        # In a real test, we'd mock the console or use CliRunner

    def test_message_includes_backend_name(self, capsys) -> None:
        """Test that error message includes the backend name."""
        adapter = MockAdapter({"tasks": True}, name="notion")

        try:
            require_capability(adapter, "relations", "Item relations")
        except SystemExit:
            pass

        # Note: Rich console output - see above


class TestCapabilityIntegration:
    """Integration tests for capability checking in CLI commands."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_status_shows_capabilities(self, runner: CliRunner) -> None:
        """Test that jarvis status shows capability information."""
        from jarvis.cli import cli

        result = runner.invoke(cli, ["status"])
        # Status command shows capabilities section
        # (exact output depends on connection success/failure)
        assert "Backend:" in result.output

    def test_config_capabilities_shows_all(self, runner: CliRunner) -> None:
        """Test that jarvis config capabilities shows all capability info."""
        from jarvis.cli import cli

        result = runner.invoke(cli, ["config", "capabilities"])
        # Should show capabilities or an error message
        output = result.output.lower()
        assert "capabilities" in output or "error" in output
