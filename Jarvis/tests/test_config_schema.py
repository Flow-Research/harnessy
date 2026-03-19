"""Tests for configuration schema models."""

import pytest

from jarvis.config.schema import (
    AnyTypeConfig,
    AnalyticsConfig,
    BackendsConfig,
    JarvisConfig,
    NotionConfig,
    get_config_dir,
    get_config_path,
)


class TestNotionConfig:
    """Tests for NotionConfig model."""

    def test_minimal_config(self):
        """Test creating NotionConfig with required fields."""
        config = NotionConfig(
            workspace_id="ws-123",
            task_database_id="db-tasks",
            journal_database_id="db-journal",
        )
        assert config.workspace_id == "ws-123"
        assert config.task_database_id == "db-tasks"
        assert config.journal_database_id == "db-journal"

    def test_default_property_mappings(self):
        """Test default property mappings are set."""
        config = NotionConfig(
            workspace_id="ws-123",
            task_database_id="db-tasks",
            journal_database_id="db-journal",
        )
        assert "priority" in config.property_mappings
        assert "due_date" in config.property_mappings
        assert config.property_mappings["title"] == "Name"

    def test_custom_property_mappings(self):
        """Test custom property mappings override defaults."""
        config = NotionConfig(
            workspace_id="ws-123",
            task_database_id="db-tasks",
            journal_database_id="db-journal",
            property_mappings={"title": "Task Name", "priority": "Urgency"},
        )
        assert config.property_mappings["title"] == "Task Name"
        assert config.property_mappings["priority"] == "Urgency"


class TestAnyTypeConfig:
    """Tests for AnyTypeConfig model."""

    def test_default_config(self):
        """Test AnyTypeConfig with default values."""
        config = AnyTypeConfig()
        assert config.default_space_id is None

    def test_with_default_space(self):
        """Test AnyTypeConfig with pre-selected space."""
        config = AnyTypeConfig(default_space_id="space-123")
        assert config.default_space_id == "space-123"


class TestBackendsConfig:
    """Tests for BackendsConfig model."""

    def test_default_has_anytype(self):
        """Test default BackendsConfig includes AnyType."""
        config = BackendsConfig()
        assert config.anytype is not None
        assert config.notion is None

    def test_with_notion(self):
        """Test BackendsConfig with Notion configured."""
        config = BackendsConfig(
            notion=NotionConfig(
                workspace_id="ws-123",
                task_database_id="db-tasks",
                journal_database_id="db-journal",
            )
        )
        assert config.notion is not None
        assert config.notion.workspace_id == "ws-123"


class TestAnalyticsConfig:
    """Tests for AnalyticsConfig model."""

    def test_default_disabled(self):
        """Test analytics is disabled by default."""
        config = AnalyticsConfig()
        assert config.enabled is False

    def test_default_metrics_file(self):
        """Test default metrics file path."""
        config = AnalyticsConfig()
        assert config.metrics_file == "~/.jarvis/metrics.json"


class TestJarvisConfig:
    """Tests for root JarvisConfig model."""

    def test_default_config(self):
        """Test JarvisConfig with all defaults."""
        config = JarvisConfig()
        assert config.version == 1
        assert config.active_backend == "anytype"
        assert config.backends is not None
        assert config.analytics.enabled is False

    def test_set_notion_backend(self):
        """Test setting Notion as active backend."""
        config = JarvisConfig(
            active_backend="notion",
            backends=BackendsConfig(
                notion=NotionConfig(
                    workspace_id="ws-123",
                    task_database_id="db-tasks",
                    journal_database_id="db-journal",
                )
            ),
        )
        assert config.active_backend == "notion"

    def test_invalid_backend_raises(self):
        """Test that invalid backend raises validation error."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            JarvisConfig(active_backend="invalid")  # type: ignore
        # Pydantic's Literal type validates before custom validator
        assert "active_backend" in str(exc_info.value)

    def test_get_backend_config_anytype(self):
        """Test get_backend_config returns AnyType config."""
        config = JarvisConfig()
        backend_config = config.get_backend_config("anytype")
        assert isinstance(backend_config, AnyTypeConfig)

    def test_get_backend_config_notion(self):
        """Test get_backend_config returns Notion config when configured."""
        config = JarvisConfig(
            backends=BackendsConfig(
                notion=NotionConfig(
                    workspace_id="ws-123",
                    task_database_id="db-tasks",
                    journal_database_id="db-journal",
                )
            )
        )
        backend_config = config.get_backend_config("notion")
        assert isinstance(backend_config, NotionConfig)
        assert backend_config.workspace_id == "ws-123"

    def test_get_backend_config_notion_not_configured(self):
        """Test get_backend_config raises when Notion not configured."""
        config = JarvisConfig()
        with pytest.raises(ValueError) as exc_info:
            config.get_backend_config("notion")
        assert "not configured" in str(exc_info.value)

    def test_get_backend_config_unknown(self):
        """Test get_backend_config raises for unknown backend."""
        config = JarvisConfig()
        with pytest.raises(ValueError) as exc_info:
            config.get_backend_config("unknown")
        assert "Unknown backend" in str(exc_info.value)

    def test_get_backend_config_uses_active(self):
        """Test get_backend_config uses active_backend when none specified."""
        config = JarvisConfig(active_backend="anytype")
        backend_config = config.get_backend_config()
        assert isinstance(backend_config, AnyTypeConfig)


class TestConfigPaths:
    """Tests for config path utilities."""

    def test_get_config_dir_returns_path(self):
        """Test get_config_dir returns a Path."""
        config_dir = get_config_dir()
        assert config_dir.name == ".jarvis"
        assert config_dir.is_dir()

    def test_get_config_path_returns_yaml(self):
        """Test get_config_path returns config.yaml path."""
        config_path = get_config_path()
        assert config_path.name == "config.yaml"
        assert config_path.parent.name == ".jarvis"
