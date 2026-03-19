"""Tests for configuration schema models."""

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from jarvis.config.schema import (
    AnalyticsConfig,
    AnyTypeConfig,
    BackendsConfig,
    JarvisConfig,
    NotionConfig,
    get_config_dir,
    get_config_path,
)


class TestNotionConfig:
    """Test cases for NotionConfig model."""

    def test_create_notion_config(self) -> None:
        """Test basic Notion config creation."""
        config = NotionConfig(
            workspace_id="ws-123",
            task_database_id="tasks-456",
            journal_database_id="journal-789",
        )
        assert config.workspace_id == "ws-123"
        assert config.task_database_id == "tasks-456"
        assert config.journal_database_id == "journal-789"

    def test_default_property_mappings(self) -> None:
        """Test default property mappings are set."""
        config = NotionConfig(
            workspace_id="ws-123",
            task_database_id="tasks-456",
            journal_database_id="journal-789",
        )
        assert config.property_mappings["priority"] == "Priority"
        assert config.property_mappings["due_date"] == "Due Date"
        assert config.property_mappings["tags"] == "Tags"
        assert config.property_mappings["done"] == "Done"

    def test_custom_property_mappings(self) -> None:
        """Test custom property mappings override defaults."""
        config = NotionConfig(
            workspace_id="ws-123",
            task_database_id="tasks-456",
            journal_database_id="journal-789",
            property_mappings={
                "priority": "Prioridade",
                "due_date": "Data",
                "tags": "Etiquetas",
                "done": "Concluído",
            },
        )
        assert config.property_mappings["priority"] == "Prioridade"

    def test_required_fields(self) -> None:
        """Test that required fields are enforced."""
        with pytest.raises(ValidationError):
            NotionConfig(workspace_id="ws-123")  # type: ignore[call-arg]


class TestAnyTypeConfig:
    """Test cases for AnyTypeConfig model."""

    def test_create_anytype_config_minimal(self) -> None:
        """Test AnyType config with no optional fields."""
        config = AnyTypeConfig()
        assert config.default_space_id is None

    def test_create_anytype_config_with_space_id(self) -> None:
        """Test AnyType config with pre-selected space."""
        config = AnyTypeConfig(default_space_id="space-123")
        assert config.default_space_id == "space-123"


class TestBackendsConfig:
    """Test cases for BackendsConfig model."""

    def test_create_backends_config_defaults(self) -> None:
        """Test backends config with defaults."""
        config = BackendsConfig()
        assert isinstance(config.anytype, AnyTypeConfig)
        assert config.notion is None

    def test_create_backends_config_with_notion(self) -> None:
        """Test backends config with Notion configured."""
        config = BackendsConfig(
            notion=NotionConfig(
                workspace_id="ws-123",
                task_database_id="tasks-456",
                journal_database_id="journal-789",
            )
        )
        assert config.notion is not None
        assert config.notion.workspace_id == "ws-123"


class TestAnalyticsConfig:
    """Test cases for AnalyticsConfig model."""

    def test_analytics_disabled_by_default(self) -> None:
        """Test analytics is opt-in (disabled by default)."""
        config = AnalyticsConfig()
        assert config.enabled is False
        assert config.metrics_file == "~/.jarvis/metrics.json"

    def test_analytics_enabled(self) -> None:
        """Test enabling analytics."""
        config = AnalyticsConfig(enabled=True, metrics_file="/custom/path.json")
        assert config.enabled is True
        assert config.metrics_file == "/custom/path.json"


class TestJarvisConfig:
    """Test cases for JarvisConfig root model."""

    def test_create_default_config(self) -> None:
        """Test creating config with all defaults."""
        config = JarvisConfig()
        assert config.version == 1
        assert config.active_backend == "anytype"
        assert config.analytics.enabled is False

    def test_create_config_with_notion_backend(self) -> None:
        """Test config with Notion as active backend."""
        config = JarvisConfig(
            active_backend="notion",
            backends=BackendsConfig(
                notion=NotionConfig(
                    workspace_id="ws-123",
                    task_database_id="tasks-456",
                    journal_database_id="journal-789",
                )
            ),
        )
        assert config.active_backend == "notion"
        assert config.backends.notion is not None

    def test_invalid_backend_raises_error(self) -> None:
        """Test invalid backend name raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            JarvisConfig(active_backend="invalid")
        assert "Invalid backend" in str(exc_info.value) or "Input should be" in str(exc_info.value)

    def test_get_backend_config_anytype(self) -> None:
        """Test get_backend_config for AnyType."""
        config = JarvisConfig()
        backend_config = config.get_backend_config("anytype")
        assert isinstance(backend_config, AnyTypeConfig)

    def test_get_backend_config_notion(self) -> None:
        """Test get_backend_config for Notion."""
        config = JarvisConfig(
            backends=BackendsConfig(
                notion=NotionConfig(
                    workspace_id="ws-123",
                    task_database_id="tasks-456",
                    journal_database_id="journal-789",
                )
            )
        )
        backend_config = config.get_backend_config("notion")
        assert isinstance(backend_config, NotionConfig)

    def test_get_backend_config_notion_not_configured(self) -> None:
        """Test get_backend_config raises error if Notion not configured."""
        config = JarvisConfig()
        with pytest.raises(ValueError) as exc_info:
            config.get_backend_config("notion")
        assert "not configured" in str(exc_info.value)

    def test_get_backend_config_uses_active_backend(self) -> None:
        """Test get_backend_config uses active_backend when None passed."""
        config = JarvisConfig(active_backend="anytype")
        backend_config = config.get_backend_config()
        assert isinstance(backend_config, AnyTypeConfig)

    def test_get_backend_config_unknown_backend(self) -> None:
        """Test get_backend_config raises error for unknown backend."""
        config = JarvisConfig()
        with pytest.raises(ValueError) as exc_info:
            config.get_backend_config("unknown")
        assert "Unknown backend" in str(exc_info.value)

    def test_config_from_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test config can be set via environment variables."""
        monkeypatch.setenv("JARVIS_ACTIVE_BACKEND", "anytype")
        config = JarvisConfig()
        assert config.active_backend == "anytype"


class TestConfigPaths:
    """Test cases for config path utilities."""

    def test_get_config_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test get_config_dir creates directory."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: fake_home)

        config_dir = get_config_dir()
        assert config_dir == fake_home / ".jarvis"
        assert config_dir.exists()

    def test_get_config_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test get_config_path returns correct path."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: fake_home)

        config_path = get_config_path()
        assert config_path == fake_home / ".jarvis" / "config.yaml"
