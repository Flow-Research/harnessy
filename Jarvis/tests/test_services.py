"""Tests for service layer modules.

These tests verify the orchestration logic in service modules:
- Capability checking
- Default space resolution
- Connection management

The adapter is mocked since adapter functionality is tested
separately in integration tests.
"""

from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest

from jarvis.adapters.exceptions import NotSupportedError
from jarvis.models import Task, JournalEntry, Priority
from jarvis.services.adapter_service import (
    get_adapter,
    ensure_connected,
    connected_adapter,
    get_default_space,
    check_capability,
)
from jarvis.services.task_service import TaskService
from jarvis.services.journal_service import JournalService


# --- Fixtures ---


@pytest.fixture
def mock_adapter():
    """Create a mock adapter with standard capabilities."""
    adapter = MagicMock()
    adapter.backend_name = "mock"
    adapter.capabilities = {
        "tasks": True,
        "journal": True,
        "tags": True,
        "search": True,
        "priorities": True,
        "due_dates": True,
    }
    adapter.is_connected.return_value = True
    adapter.get_default_space.return_value = "default-space-id"
    return adapter


@pytest.fixture
def mock_adapter_no_journal():
    """Create a mock adapter without journal capability."""
    adapter = MagicMock()
    adapter.backend_name = "mock-no-journal"
    adapter.capabilities = {
        "tasks": True,
        "journal": False,
        "tags": True,
        "search": False,
        "priorities": True,
        "due_dates": True,
    }
    adapter.is_connected.return_value = True
    adapter.get_default_space.return_value = "default-space-id"
    return adapter


@pytest.fixture
def sample_task():
    """Create a sample task for testing."""
    now = datetime.now()
    return Task(
        id="task-123",
        title="Test Task",
        space_id="space-1",
        is_done=False,
        due_date=date(2026, 1, 30),
        priority=Priority.HIGH,
        tags=["test"],
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def sample_journal_entry():
    """Create a sample journal entry for testing."""
    return JournalEntry(
        id="entry-123",
        title="Test Entry",
        content="Test content",
        space_id="space-1",
        entry_date=date(2026, 1, 25),
        tags=["journal"],
        created_at=datetime.now(),
    )


# --- adapter_service tests ---


class TestAdapterService:
    """Tests for adapter_service module."""

    def test_check_capability_returns_true(self, mock_adapter):
        """Test check_capability returns True for supported capability."""
        assert check_capability(mock_adapter, "tasks") is True
        assert check_capability(mock_adapter, "journal") is True

    def test_check_capability_returns_false(self, mock_adapter):
        """Test check_capability returns False for unsupported capability."""
        assert check_capability(mock_adapter, "nonexistent") is False

    def test_ensure_connected_connects_if_needed(self, mock_adapter):
        """Test ensure_connected calls connect() when not connected."""
        mock_adapter.is_connected.return_value = False

        ensure_connected(mock_adapter)

        mock_adapter.connect.assert_called_once()

    def test_ensure_connected_skips_if_connected(self, mock_adapter):
        """Test ensure_connected doesn't call connect() if already connected."""
        mock_adapter.is_connected.return_value = True

        ensure_connected(mock_adapter)

        mock_adapter.connect.assert_not_called()

    @patch("jarvis.services.adapter_service.AdapterRegistry")
    @patch("jarvis.services.adapter_service.load_config")
    def test_get_adapter_uses_config_default(self, mock_load_config, mock_registry):
        """Test get_adapter uses active_backend from config when not specified."""
        mock_config = MagicMock()
        mock_config.active_backend = "anytype"
        mock_load_config.return_value = mock_config

        get_adapter()

        mock_registry.get_adapter.assert_called_once_with("anytype")

    @patch("jarvis.services.adapter_service.AdapterRegistry")
    @patch("jarvis.services.adapter_service.load_config")
    def test_get_adapter_uses_override(self, mock_load_config, mock_registry):
        """Test get_adapter uses specified backend over config."""
        mock_config = MagicMock()
        mock_config.active_backend = "anytype"
        mock_load_config.return_value = mock_config

        get_adapter("notion")

        mock_registry.get_adapter.assert_called_once_with("notion")

    @patch("jarvis.state.get_selected_space")
    def test_get_default_space_uses_saved(self, mock_get_selected, mock_adapter):
        """Test get_default_space uses saved selection if valid."""
        mock_get_selected.return_value = "saved-space-id"
        mock_adapter.list_spaces.return_value = [
            MagicMock(id="saved-space-id"),
            MagicMock(id="other-space"),
        ]

        result = get_default_space(mock_adapter)

        assert result == "saved-space-id"

    @patch("jarvis.state.get_selected_space")
    def test_get_default_space_falls_back_if_invalid(
        self, mock_get_selected, mock_adapter
    ):
        """Test get_default_space falls back to adapter default if saved is invalid."""
        mock_get_selected.return_value = "nonexistent-space"
        mock_adapter.list_spaces.return_value = [MagicMock(id="other-space")]

        result = get_default_space(mock_adapter)

        assert result == "default-space-id"
        mock_adapter.get_default_space.assert_called_once()

    @patch("jarvis.state.get_selected_space")
    def test_get_default_space_no_saved(self, mock_get_selected, mock_adapter):
        """Test get_default_space uses adapter default when no saved selection."""
        mock_get_selected.return_value = None

        result = get_default_space(mock_adapter)

        assert result == "default-space-id"


class TestConnectedAdapterContextManager:
    """Tests for connected_adapter context manager."""

    @patch("jarvis.services.adapter_service.get_adapter")
    def test_connects_and_disconnects(self, mock_get_adapter):
        """Test connected_adapter connects on enter and disconnects on exit."""
        mock_adapter = MagicMock()
        mock_adapter.is_connected.side_effect = [False, True, True]
        mock_get_adapter.return_value = mock_adapter

        with connected_adapter() as adapter:
            assert adapter is mock_adapter
            mock_adapter.connect.assert_called_once()

        mock_adapter.disconnect.assert_called_once()

    @patch("jarvis.services.adapter_service.get_adapter")
    def test_disconnects_on_exception(self, mock_get_adapter):
        """Test connected_adapter disconnects even if exception raised."""
        mock_adapter = MagicMock()
        mock_adapter.is_connected.side_effect = [False, True, True]
        mock_get_adapter.return_value = mock_adapter

        with pytest.raises(ValueError):
            with connected_adapter():
                raise ValueError("Test error")

        mock_adapter.disconnect.assert_called_once()


# --- TaskService tests ---


class TestTaskService:
    """Tests for TaskService class."""

    @patch("jarvis.services.task_service.get_adapter")
    def test_adapter_property_lazy_loads(self, mock_get_adapter, mock_adapter):
        """Test adapter property creates adapter on first access."""
        mock_get_adapter.return_value = mock_adapter
        service = TaskService()

        # Access adapter
        _ = service.adapter

        mock_get_adapter.assert_called_once_with(None)

    @patch("jarvis.services.task_service.get_adapter")
    def test_adapter_property_caches(self, mock_get_adapter, mock_adapter):
        """Test adapter property caches the adapter instance."""
        mock_get_adapter.return_value = mock_adapter
        service = TaskService()

        # Access adapter twice
        _ = service.adapter
        _ = service.adapter

        mock_get_adapter.assert_called_once()

    @patch("jarvis.services.task_service.get_adapter")
    def test_is_connected_false_when_no_adapter(self, mock_get_adapter):
        """Test is_connected returns False when adapter not created."""
        service = TaskService()

        assert service.is_connected is False
        mock_get_adapter.assert_not_called()

    @patch("jarvis.services.task_service.get_adapter")
    def test_is_connected_delegates_to_adapter(self, mock_get_adapter, mock_adapter):
        """Test is_connected delegates to adapter when created."""
        mock_get_adapter.return_value = mock_adapter
        mock_adapter.is_connected.return_value = True
        service = TaskService()

        # Initialize adapter
        _ = service.adapter

        assert service.is_connected is True

    @patch("jarvis.services.task_service.get_adapter")
    @patch("jarvis.services.task_service.ensure_connected")
    def test_connect(self, mock_ensure, mock_get_adapter, mock_adapter):
        """Test connect calls ensure_connected."""
        mock_get_adapter.return_value = mock_adapter
        service = TaskService()

        service.connect()

        mock_ensure.assert_called_once_with(mock_adapter)

    @patch("jarvis.services.task_service.get_adapter")
    def test_disconnect(self, mock_get_adapter, mock_adapter):
        """Test disconnect calls adapter disconnect."""
        mock_get_adapter.return_value = mock_adapter
        service = TaskService()
        service._adapter = mock_adapter

        service.disconnect()

        mock_adapter.disconnect.assert_called_once()

    @patch("jarvis.services.task_service.get_adapter")
    def test_create_task_uses_default_space(
        self, mock_get_adapter, mock_adapter, sample_task
    ):
        """Test create_task uses default space when not specified."""
        mock_get_adapter.return_value = mock_adapter
        mock_adapter.create_task.return_value = sample_task
        service = TaskService()
        service._adapter = mock_adapter

        result = service.create_task("Test Task")

        mock_adapter.get_default_space.assert_called_once()
        mock_adapter.create_task.assert_called_once()
        assert result == sample_task

    @patch("jarvis.services.task_service.get_adapter")
    def test_create_task_uses_provided_space(
        self, mock_get_adapter, mock_adapter, sample_task
    ):
        """Test create_task uses provided space_id."""
        mock_get_adapter.return_value = mock_adapter
        mock_adapter.create_task.return_value = sample_task
        service = TaskService()
        service._adapter = mock_adapter

        service.create_task("Test Task", space_id="custom-space")

        mock_adapter.get_default_space.assert_not_called()
        mock_adapter.create_task.assert_called_once()
        call_kwargs = mock_adapter.create_task.call_args[1]
        assert call_kwargs["space_id"] == "custom-space"

    @patch("jarvis.services.task_service.get_adapter")
    def test_create_task_passes_all_params(
        self, mock_get_adapter, mock_adapter, sample_task
    ):
        """Test create_task passes all parameters to adapter."""
        mock_get_adapter.return_value = mock_adapter
        mock_adapter.create_task.return_value = sample_task
        service = TaskService()
        service._adapter = mock_adapter
        due = date(2026, 2, 1)

        service.create_task(
            "Test Task",
            space_id="space-1",
            due_date=due,
            priority=Priority.HIGH,
            tags=["urgent"],
            description="Details",
        )

        mock_adapter.create_task.assert_called_once_with(
            space_id="space-1",
            title="Test Task",
            due_date=due,
            priority=Priority.HIGH,
            tags=["urgent"],
            description="Details",
        )

    @patch("jarvis.services.task_service.get_adapter")
    def test_get_task(self, mock_get_adapter, mock_adapter, sample_task):
        """Test get_task delegates to adapter."""
        mock_get_adapter.return_value = mock_adapter
        mock_adapter.get_task.return_value = sample_task
        service = TaskService()
        service._adapter = mock_adapter

        result = service.get_task("task-123", space_id="space-1")

        mock_adapter.get_task.assert_called_once_with("space-1", "task-123")
        assert result == sample_task

    @patch("jarvis.services.task_service.get_adapter")
    def test_get_tasks_with_filters(self, mock_get_adapter, mock_adapter, sample_task):
        """Test get_tasks passes all filter parameters."""
        mock_get_adapter.return_value = mock_adapter
        mock_adapter.get_tasks.return_value = [sample_task]
        service = TaskService()
        service._adapter = mock_adapter
        start = date(2026, 1, 1)
        end = date(2026, 1, 31)

        result = service.get_tasks(
            space_id="space-1",
            start_date=start,
            end_date=end,
            include_done=True,
            limit=10,
            offset=5,
        )

        mock_adapter.get_tasks.assert_called_once_with(
            space_id="space-1",
            start_date=start,
            end_date=end,
            include_done=True,
            limit=10,
            offset=5,
        )
        assert result == [sample_task]

    @patch("jarvis.services.task_service.get_adapter")
    def test_update_task(self, mock_get_adapter, mock_adapter, sample_task):
        """Test update_task delegates to adapter."""
        mock_get_adapter.return_value = mock_adapter
        mock_adapter.update_task.return_value = sample_task
        service = TaskService()
        service._adapter = mock_adapter

        result = service.update_task(
            "task-123",
            space_id="space-1",
            title="Updated Title",
            is_done=True,
        )

        mock_adapter.update_task.assert_called_once()
        assert result == sample_task

    @patch("jarvis.services.task_service.get_adapter")
    def test_delete_task(self, mock_get_adapter, mock_adapter):
        """Test delete_task delegates to adapter."""
        mock_get_adapter.return_value = mock_adapter
        mock_adapter.delete_task.return_value = True
        service = TaskService()
        service._adapter = mock_adapter

        result = service.delete_task("task-123", space_id="space-1")

        mock_adapter.delete_task.assert_called_once_with("space-1", "task-123")
        assert result is True

    @patch("jarvis.services.task_service.get_adapter")
    def test_complete_task(self, mock_get_adapter, mock_adapter, sample_task):
        """Test complete_task sets is_done=True."""
        mock_get_adapter.return_value = mock_adapter
        now = datetime.now()
        completed_task = Task(
            id="task-123",
            title="Test Task",
            space_id="space-1",
            is_done=True,
            created_at=now,
            updated_at=now,
        )
        mock_adapter.update_task.return_value = completed_task
        service = TaskService()
        service._adapter = mock_adapter

        result = service.complete_task("task-123", space_id="space-1")

        call_kwargs = mock_adapter.update_task.call_args[1]
        assert call_kwargs["is_done"] is True
        assert result.is_done is True

    @patch("jarvis.services.task_service.get_adapter")
    def test_check_tasks_capability_raises(self, mock_get_adapter, mock_adapter):
        """Test capability check raises NotSupportedError."""
        mock_adapter.capabilities = {"tasks": False}
        mock_get_adapter.return_value = mock_adapter
        service = TaskService()
        service._adapter = mock_adapter

        with pytest.raises(NotSupportedError) as exc_info:
            service.create_task("Test")

        assert "does not support tasks" in str(exc_info.value)


# --- JournalService tests ---


class TestJournalService:
    """Tests for JournalService class."""

    @patch("jarvis.services.journal_service.get_adapter")
    def test_adapter_property_lazy_loads(self, mock_get_adapter, mock_adapter):
        """Test adapter property creates adapter on first access."""
        mock_get_adapter.return_value = mock_adapter
        service = JournalService()

        _ = service.adapter

        mock_get_adapter.assert_called_once_with(None)

    @patch("jarvis.services.journal_service.get_adapter")
    def test_create_entry_uses_defaults(
        self, mock_get_adapter, mock_adapter, sample_journal_entry
    ):
        """Test create_entry uses default space and today's date."""
        mock_get_adapter.return_value = mock_adapter
        mock_adapter.create_journal_entry.return_value = sample_journal_entry
        service = JournalService()
        service._adapter = mock_adapter

        service.create_entry("Title", "Content")

        mock_adapter.get_default_space.assert_called_once()
        call_kwargs = mock_adapter.create_journal_entry.call_args[1]
        assert call_kwargs["entry_date"] == date.today()

    @patch("jarvis.services.journal_service.get_adapter")
    def test_create_entry_passes_all_params(
        self, mock_get_adapter, mock_adapter, sample_journal_entry
    ):
        """Test create_entry passes all parameters to adapter."""
        mock_get_adapter.return_value = mock_adapter
        mock_adapter.create_journal_entry.return_value = sample_journal_entry
        service = JournalService()
        service._adapter = mock_adapter
        entry_date = date(2026, 1, 20)

        service.create_entry(
            "Title",
            "Content",
            space_id="space-1",
            entry_date=entry_date,
            tags=["tag1"],
        )

        mock_adapter.create_journal_entry.assert_called_once_with(
            space_id="space-1",
            title="Title",
            content="Content",
            entry_date=entry_date,
            tags=["tag1"],
        )

    @patch("jarvis.services.journal_service.get_adapter")
    def test_get_entry(self, mock_get_adapter, mock_adapter, sample_journal_entry):
        """Test get_entry delegates to adapter."""
        mock_get_adapter.return_value = mock_adapter
        mock_adapter.get_journal_entry.return_value = sample_journal_entry
        service = JournalService()
        service._adapter = mock_adapter

        result = service.get_entry("entry-123", space_id="space-1")

        mock_adapter.get_journal_entry.assert_called_once_with("space-1", "entry-123")
        assert result == sample_journal_entry

    @patch("jarvis.services.journal_service.get_adapter")
    def test_get_entries_with_filters(
        self, mock_get_adapter, mock_adapter, sample_journal_entry
    ):
        """Test get_entries passes all filter parameters."""
        mock_get_adapter.return_value = mock_adapter
        mock_adapter.get_journal_entries.return_value = [sample_journal_entry]
        service = JournalService()
        service._adapter = mock_adapter
        start = date(2026, 1, 1)
        end = date(2026, 1, 31)

        result = service.get_entries(
            space_id="space-1",
            start_date=start,
            end_date=end,
            limit=10,
            offset=5,
        )

        mock_adapter.get_journal_entries.assert_called_once_with(
            space_id="space-1",
            start_date=start,
            end_date=end,
            limit=10,
            offset=5,
        )
        assert result == [sample_journal_entry]

    @patch("jarvis.services.journal_service.get_adapter")
    def test_search_entries(self, mock_get_adapter, mock_adapter, sample_journal_entry):
        """Test search_entries delegates to adapter."""
        mock_get_adapter.return_value = mock_adapter
        mock_adapter.search_journal_entries.return_value = [sample_journal_entry]
        service = JournalService()
        service._adapter = mock_adapter

        result = service.search_entries("query", space_id="space-1")

        mock_adapter.search_journal_entries.assert_called_once()
        assert result == [sample_journal_entry]

    @patch("jarvis.services.journal_service.get_adapter")
    def test_search_entries_checks_search_capability(
        self, mock_get_adapter, mock_adapter_no_journal
    ):
        """Test search_entries checks search capability."""
        mock_adapter_no_journal.capabilities["journal"] = True
        mock_get_adapter.return_value = mock_adapter_no_journal
        service = JournalService()
        service._adapter = mock_adapter_no_journal

        with pytest.raises(NotSupportedError) as exc_info:
            service.search_entries("query")

        assert "does not support search" in str(exc_info.value)

    @patch("jarvis.services.journal_service.get_adapter")
    def test_update_entry(self, mock_get_adapter, mock_adapter, sample_journal_entry):
        """Test update_entry delegates to adapter."""
        mock_get_adapter.return_value = mock_adapter
        mock_adapter.update_journal_entry.return_value = sample_journal_entry
        service = JournalService()
        service._adapter = mock_adapter

        result = service.update_entry(
            "entry-123",
            space_id="space-1",
            title="New Title",
            content="New Content",
        )

        mock_adapter.update_journal_entry.assert_called_once()
        assert result == sample_journal_entry

    @patch("jarvis.services.journal_service.get_adapter")
    def test_delete_entry(self, mock_get_adapter, mock_adapter):
        """Test delete_entry delegates to adapter."""
        mock_get_adapter.return_value = mock_adapter
        mock_adapter.delete_journal_entry.return_value = True
        service = JournalService()
        service._adapter = mock_adapter

        result = service.delete_entry("entry-123", space_id="space-1")

        mock_adapter.delete_journal_entry.assert_called_once_with("space-1", "entry-123")
        assert result is True

    @patch("jarvis.services.journal_service.get_adapter")
    def test_check_journal_capability_raises(
        self, mock_get_adapter, mock_adapter_no_journal
    ):
        """Test capability check raises NotSupportedError."""
        mock_get_adapter.return_value = mock_adapter_no_journal
        service = JournalService()
        service._adapter = mock_adapter_no_journal

        with pytest.raises(NotSupportedError) as exc_info:
            service.create_entry("Title", "Content")

        assert "does not support journal" in str(exc_info.value)

    @patch("jarvis.services.journal_service.get_adapter")
    def test_disconnect(self, mock_get_adapter, mock_adapter):
        """Test disconnect calls adapter disconnect."""
        mock_get_adapter.return_value = mock_adapter
        service = JournalService()
        service._adapter = mock_adapter

        service.disconnect()

        mock_adapter.disconnect.assert_called_once()

    @patch("jarvis.services.journal_service.get_adapter")
    def test_is_connected_false_when_no_adapter(self, mock_get_adapter):
        """Test is_connected returns False when adapter not created."""
        service = JournalService()

        assert service.is_connected is False
