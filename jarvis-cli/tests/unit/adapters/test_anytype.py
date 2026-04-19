"""Tests for AnyTypeAdapter."""

from datetime import date
from unittest.mock import patch

import pytest

from jarvis.adapters.anytype import AnyTypeAdapter
from jarvis.adapters.exceptions import (
    AuthError,
    ConnectionError,
    NotFoundError,
    ValidationError,
)
from jarvis.config.schema import AnyTypeConfig, BackendsConfig, JarvisConfig
from jarvis.models import Priority


class TestAnyTypeAdapterCapabilities:
    """Test capability declarations."""

    def test_capabilities(self) -> None:
        """Test capabilities property."""
        adapter = AnyTypeAdapter()
        caps = adapter.capabilities

        assert caps["tasks"] is True
        assert caps["journal"] is True
        assert caps["tags"] is True
        assert caps["search"] is True
        assert caps["priorities"] is True
        assert caps["due_dates"] is True
        assert caps["daily_notes"] is False
        assert caps["relations"] is True
        assert caps["custom_properties"] is False

    def test_backend_name(self) -> None:
        """Test backend_name property."""
        adapter = AnyTypeAdapter()
        assert adapter.backend_name == "anytype"


class TestAnyTypeAdapterConnection:
    """Test connection management."""

    def test_connect_success(self) -> None:
        """Test successful connection."""
        adapter = AnyTypeAdapter()

        with patch.object(adapter._client, "connect"):
            adapter.connect()
            adapter._client.connect.assert_called_once()

    def test_connect_auth_error(self) -> None:
        """Test connection with auth failure."""
        adapter = AnyTypeAdapter()

        with patch.object(
            adapter._client, "connect", side_effect=RuntimeError("Authentication failed")
        ):
            with pytest.raises(AuthError) as exc_info:
                adapter.connect()
            assert "anytype" in str(exc_info.value).lower()

    def test_connect_connection_error(self) -> None:
        """Test connection with network failure."""
        adapter = AnyTypeAdapter()

        with patch.object(
            adapter._client, "connect", side_effect=RuntimeError("Connection refused")
        ):
            with pytest.raises(ConnectionError) as exc_info:
                adapter.connect()
            assert "anytype" in str(exc_info.value).lower()

    def test_is_connected_false_initially(self) -> None:
        """Test is_connected returns False initially."""
        adapter = AnyTypeAdapter()
        assert adapter.is_connected() is False

    def test_is_connected_true_after_connect(self) -> None:
        """Test is_connected returns True after connection."""
        adapter = AnyTypeAdapter()
        adapter._client._authenticated = True
        assert adapter.is_connected() is True

    def test_disconnect_is_noop(self) -> None:
        """Test disconnect doesn't raise."""
        adapter = AnyTypeAdapter()
        adapter._client._authenticated = True
        # Should not raise
        adapter.disconnect()


class TestAnyTypeAdapterSpaces:
    """Test space operations."""

    @pytest.fixture
    def connected_adapter(self) -> AnyTypeAdapter:
        """Create a connected adapter."""
        adapter = AnyTypeAdapter()
        adapter._client._authenticated = True
        return adapter

    def test_list_spaces_not_connected(self) -> None:
        """Test list_spaces raises when not connected."""
        adapter = AnyTypeAdapter()
        with pytest.raises(ConnectionError):
            adapter.list_spaces()

    def test_list_spaces_success(self, connected_adapter: AnyTypeAdapter) -> None:
        """Test list_spaces returns Space objects."""
        with patch.object(
            connected_adapter._client,
            "get_spaces",
            return_value=[("space-1", "My Space"), ("space-2", "Work")],
        ):
            spaces = connected_adapter.list_spaces()

            assert len(spaces) == 2
            assert spaces[0].id == "space-1"
            assert spaces[0].name == "My Space"
            assert spaces[0].backend == "anytype"

    def test_get_default_space_not_connected(self) -> None:
        """Test get_default_space raises when not connected."""
        adapter = AnyTypeAdapter()
        with pytest.raises(ConnectionError):
            adapter.get_default_space()

    def test_get_default_space_from_config(
        self, connected_adapter: AnyTypeAdapter
    ) -> None:
        """Test get_default_space uses config value."""
        connected_adapter._default_space_id = "configured-space"

        result = connected_adapter.get_default_space()
        assert result == "configured-space"

    def test_get_default_space_first_space(
        self, connected_adapter: AnyTypeAdapter
    ) -> None:
        """Test get_default_space returns first space when not configured."""
        with patch.object(
            connected_adapter._client,
            "get_default_space",
            return_value="first-space",
        ):
            result = connected_adapter.get_default_space()
            assert result == "first-space"

    def test_set_default_space_valid(self, connected_adapter: AnyTypeAdapter) -> None:
        """Test set_default_space with valid space."""
        with patch.object(
            connected_adapter._client,
            "get_spaces",
            return_value=[("space-1", "My Space")],
        ):
            connected_adapter.set_default_space("space-1")
            assert connected_adapter._default_space_id == "space-1"

    def test_set_default_space_not_found(
        self, connected_adapter: AnyTypeAdapter
    ) -> None:
        """Test set_default_space with invalid space."""
        with patch.object(
            connected_adapter._client,
            "get_spaces",
            return_value=[("space-1", "My Space")],
        ):
            with pytest.raises(NotFoundError) as exc_info:
                connected_adapter.set_default_space("nonexistent")
            assert "nonexistent" in str(exc_info.value)


class TestAnyTypeAdapterTasks:
    """Test task operations."""

    @pytest.fixture
    def connected_adapter(self) -> AnyTypeAdapter:
        """Create a connected adapter."""
        adapter = AnyTypeAdapter()
        adapter._client._authenticated = True
        return adapter

    def test_create_task_not_connected(self) -> None:
        """Test create_task raises when not connected."""
        adapter = AnyTypeAdapter()
        with pytest.raises(ConnectionError):
            adapter.create_task("space-1", "Test task")

    def test_create_task_empty_title(self, connected_adapter: AnyTypeAdapter) -> None:
        """Test create_task rejects empty title."""
        with pytest.raises(ValidationError) as exc_info:
            connected_adapter.create_task("space-1", "")
        assert "empty" in str(exc_info.value).lower()

    def test_create_task_title_too_long(
        self, connected_adapter: AnyTypeAdapter
    ) -> None:
        """Test create_task rejects too-long title."""
        with pytest.raises(ValidationError) as exc_info:
            connected_adapter.create_task("space-1", "x" * 501)
        assert "500" in str(exc_info.value)

    def test_create_task_success(self, connected_adapter: AnyTypeAdapter) -> None:
        """Test create_task returns Task model."""
        with patch.object(
            connected_adapter._client, "create_task", return_value="task-123"
        ):
            task = connected_adapter.create_task(
                space_id="space-1",
                title="Buy groceries",
                due_date=date(2025, 1, 30),
                priority=Priority.HIGH,
                tags=["shopping"],
            )

            assert task.id == "task-123"
            assert task.title == "Buy groceries"
            assert task.due_date == date(2025, 1, 30)
            assert task.priority == Priority.HIGH
            assert "shopping" in task.tags
            assert task.is_done is False

    def test_get_tasks_negative_offset(
        self, connected_adapter: AnyTypeAdapter
    ) -> None:
        """Test get_tasks rejects negative offset."""
        with pytest.raises(ValidationError) as exc_info:
            connected_adapter.get_tasks("space-1", offset=-1)
        assert "non-negative" in str(exc_info.value).lower()

    def test_delete_task_not_connected(self) -> None:
        """Test delete_task raises when not connected."""
        adapter = AnyTypeAdapter()
        with pytest.raises(ConnectionError):
            adapter.delete_task("space-1", "task-123")


class TestAnyTypeAdapterJournal:
    """Test journal operations."""

    @pytest.fixture
    def connected_adapter(self) -> AnyTypeAdapter:
        """Create a connected adapter."""
        adapter = AnyTypeAdapter()
        adapter._client._authenticated = True
        return adapter

    def test_create_journal_entry_not_connected(self) -> None:
        """Test create_journal_entry raises when not connected."""
        adapter = AnyTypeAdapter()
        with pytest.raises(ConnectionError):
            adapter.create_journal_entry("space-1", "Today was great")

    def test_get_journal_entries_negative_offset(
        self, connected_adapter: AnyTypeAdapter
    ) -> None:
        """Test get_journal_entries rejects negative offset."""
        with pytest.raises(ValidationError):
            connected_adapter.get_journal_entries("space-1", offset=-1)

    def test_search_journal_negative_offset(
        self, connected_adapter: AnyTypeAdapter
    ) -> None:
        """Test search_journal rejects negative offset."""
        with pytest.raises(ValidationError):
            connected_adapter.search_journal("space-1", "query", offset=-1)


class TestAnyTypeAdapterTags:
    """Test tag operations."""

    @pytest.fixture
    def connected_adapter(self) -> AnyTypeAdapter:
        """Create a connected adapter."""
        adapter = AnyTypeAdapter()
        adapter._client._authenticated = True
        return adapter

    def test_list_tags_not_connected(self) -> None:
        """Test list_tags raises when not connected."""
        adapter = AnyTypeAdapter()
        with pytest.raises(ConnectionError):
            adapter.list_tags("space-1")

    def test_create_tag_returns_tag(self, connected_adapter: AnyTypeAdapter) -> None:
        """Test create_tag returns Tag object."""
        tag = connected_adapter.create_tag("space-1", "work", "#ff0000")

        assert tag.name == "work"
        assert tag.color == "#ff0000"
        assert tag.id == "work"  # AnyType uses name as ID


class TestAnyTypeAdapterHelpers:
    """Test helper methods."""

    def test_validate_title_empty(self) -> None:
        """Test _validate_title rejects empty string."""
        adapter = AnyTypeAdapter()
        with pytest.raises(ValidationError):
            adapter._validate_title("")

    def test_validate_title_too_long(self) -> None:
        """Test _validate_title rejects too-long string."""
        adapter = AnyTypeAdapter()
        with pytest.raises(ValidationError):
            adapter._validate_title("x" * 501)

    def test_validate_title_valid(self) -> None:
        """Test _validate_title accepts valid title."""
        adapter = AnyTypeAdapter()
        # Should not raise
        adapter._validate_title("Valid title")


class TestAnyTypeAdapterWithConfig:
    """Test adapter with configuration."""

    def test_init_with_default_space(self) -> None:
        """Test adapter uses default_space_id from config."""
        config = JarvisConfig(
            backends=BackendsConfig(
                anytype=AnyTypeConfig(default_space_id="my-space")
            )
        )
        adapter = AnyTypeAdapter(config)

        assert adapter._default_space_id == "my-space"

    def test_init_without_config(self) -> None:
        """Test adapter works without config."""
        adapter = AnyTypeAdapter()
        assert adapter._default_space_id is None
