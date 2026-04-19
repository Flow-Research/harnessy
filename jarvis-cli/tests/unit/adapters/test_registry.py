"""Tests for AdapterRegistry."""

from datetime import date, datetime
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from jarvis.adapters import (
    AdapterRegistry,
    KnowledgeBaseAdapter,
    get_adapter,
)
from jarvis.adapters.exceptions import AdapterNotFoundError
from jarvis.config.schema import JarvisConfig
from jarvis.models import BackendObject, JournalEntry, Priority, Space, Tag, Task


class MockAdapter:
    """Mock adapter for testing."""

    def __init__(self, config: JarvisConfig | None = None) -> None:
        self._config = config
        self._connected = False
        self._default_space = "space-1"

    @property
    def capabilities(self) -> dict[str, bool]:
        return {"tasks": True, "journal": True, "tags": True}

    @property
    def backend_name(self) -> str:
        return "mock"

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def list_spaces(self) -> list[Space]:
        return [Space(id="space-1", name="Test Space", backend="mock")]

    def get_default_space(self) -> str:
        return self._default_space

    def set_default_space(self, space_id: str) -> None:
        self._default_space = space_id

    def create_task(
        self,
        space_id: str,
        title: str,
        due_date: date | None = None,
        priority: Priority | None = None,
        tags: list[str] | None = None,
        description: str | None = None,
    ) -> Task:
        return Task(
            id="task-1",
            space_id=space_id,
            title=title,
            due_date=due_date,
            priority=priority,
            tags=tags or [],
            description=description,
            is_done=False,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    def get_task(self, space_id: str, task_id: str) -> Task:
        return Task(
            id=task_id,
            space_id=space_id,
            title="Test",
            is_done=False,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    def get_tasks(
        self,
        space_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
        include_done: bool = False,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Task]:
        return []

    def update_task(
        self,
        space_id: str,
        task_id: str,
        title: str | None = None,
        due_date: date | None = None,
        priority: Priority | None = None,
        tags: list[str] | None = None,
        description: str | None = None,
        is_done: bool | None = None,
    ) -> Task:
        return Task(
            id=task_id,
            space_id=space_id,
            title=title or "Test",
            is_done=is_done or False,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    def delete_task(self, space_id: str, task_id: str) -> bool:
        return True

    def create_journal_entry(
        self,
        space_id: str,
        content: str,
        title: str | None = None,
        entry_date: date | None = None,
    ) -> JournalEntry:
        return JournalEntry(
            id="entry-1",
            space_id=space_id,
            title=title or "Entry",
            content=content,
            entry_date=entry_date or date.today(),
            created_at=datetime.now(),
        )

    def get_journal_entry(self, space_id: str, entry_id: str) -> JournalEntry:
        return JournalEntry(
            id=entry_id,
            space_id=space_id,
            title="Test",
            content="Content",
            entry_date=date.today(),
            created_at=datetime.now(),
        )

    def get_journal_entries(
        self,
        space_id: str,
        limit: int = 10,
        offset: int = 0,
    ) -> list[JournalEntry]:
        return []

    def update_journal_entry(
        self,
        space_id: str,
        entry_id: str,
        content: str | None = None,
        title: str | None = None,
    ) -> JournalEntry:
        return JournalEntry(
            id=entry_id,
            space_id=space_id,
            title=title or "Test",
            content=content or "Test",
            entry_date=date.today(),
            created_at=datetime.now(),
        )

    def delete_journal_entry(self, space_id: str, entry_id: str) -> bool:
        return True

    def search_journal(
        self,
        space_id: str,
        query: str,
        limit: int = 10,
        offset: int = 0,
    ) -> list[JournalEntry]:
        return []

    def list_tags(self, space_id: str) -> list[Tag]:
        return []

    def create_tag(self, space_id: str, name: str, color: str | None = None) -> Tag:
        return Tag(id="tag-1", name=name, color=color)

    def get_object(self, space_id: str, object_id: str) -> BackendObject:
        return BackendObject(id=object_id, space_id=space_id, backend="mock")

    def update_object(
        self, space_id: str, object_id: str, updates: dict[str, object]
    ) -> BackendObject:
        return BackendObject(id=object_id, space_id=space_id, backend="mock")


class TestAdapterRegistry:
    """Test cases for AdapterRegistry."""

    @pytest.fixture(autouse=True)
    def clean_registry(self) -> Generator[None, None, None]:
        """Clean the registry before and after each test."""
        AdapterRegistry.clear_all()
        yield
        AdapterRegistry.clear_all()

    def test_register_adapter(self) -> None:
        """Test registering an adapter."""
        AdapterRegistry.register("mock", MockAdapter)
        assert AdapterRegistry.is_registered("mock")
        assert "mock" in AdapterRegistry.list_adapters()

    def test_unregister_adapter(self) -> None:
        """Test unregistering an adapter."""
        AdapterRegistry.register("mock", MockAdapter)
        assert AdapterRegistry.is_registered("mock")

        AdapterRegistry.unregister("mock")
        assert not AdapterRegistry.is_registered("mock")

    def test_unregister_nonexistent_adapter(self) -> None:
        """Test unregistering an adapter that doesn't exist doesn't raise."""
        # Should not raise
        AdapterRegistry.unregister("nonexistent")

    def test_list_adapters_empty(self) -> None:
        """Test list_adapters returns empty list when none registered."""
        assert AdapterRegistry.list_adapters() == []

    def test_list_adapters_multiple(self) -> None:
        """Test list_adapters returns all registered adapters."""
        AdapterRegistry.register("mock1", MockAdapter)
        AdapterRegistry.register("mock2", MockAdapter)

        adapters = AdapterRegistry.list_adapters()
        assert len(adapters) == 2
        assert "mock1" in adapters
        assert "mock2" in adapters

    def test_is_registered(self) -> None:
        """Test is_registered check."""
        assert not AdapterRegistry.is_registered("mock")

        AdapterRegistry.register("mock", MockAdapter)
        assert AdapterRegistry.is_registered("mock")

    def test_get_adapter_explicit_name(self) -> None:
        """Test getting adapter by explicit name."""
        AdapterRegistry.register("mock", MockAdapter)

        adapter = AdapterRegistry.get_adapter("mock")
        assert isinstance(adapter, MockAdapter)
        assert isinstance(adapter, KnowledgeBaseAdapter)

    def test_get_adapter_not_found(self) -> None:
        """Test getting unregistered adapter raises AdapterNotFoundError."""
        with pytest.raises(AdapterNotFoundError) as exc_info:
            AdapterRegistry.get_adapter("nonexistent")

        assert "nonexistent" in str(exc_info.value)
        assert "not found" in str(exc_info.value).lower()

    def test_get_adapter_returns_singleton(self) -> None:
        """Test that get_adapter returns the same instance on repeated calls."""
        AdapterRegistry.register("mock", MockAdapter)

        adapter1 = AdapterRegistry.get_adapter("mock")
        adapter2 = AdapterRegistry.get_adapter("mock")

        assert adapter1 is adapter2

    def test_get_adapter_from_config(self) -> None:
        """Test getting adapter uses active_backend from config when name is None."""
        AdapterRegistry.register("mock", MockAdapter)

        mock_config = MagicMock()
        mock_config.active_backend = "mock"

        with patch("jarvis.config.get_config", return_value=mock_config):
            adapter = AdapterRegistry.get_adapter()
            assert isinstance(adapter, MockAdapter)

    def test_get_adapter_with_factory(self) -> None:
        """Test get_adapter uses factory function when provided."""
        custom_instance = MockAdapter()
        custom_instance._default_space = "custom-space"

        def factory(config: JarvisConfig) -> MockAdapter:
            return custom_instance

        AdapterRegistry.register("mock", MockAdapter, factory=factory)

        adapter = AdapterRegistry.get_adapter("mock")
        assert adapter is custom_instance
        assert adapter._default_space == "custom-space"

    def test_clear_instances(self) -> None:
        """Test clear_instances removes cached instances."""
        AdapterRegistry.register("mock", MockAdapter)

        adapter1 = AdapterRegistry.get_adapter("mock")
        adapter1.connect()
        assert adapter1.is_connected()

        AdapterRegistry.clear_instances()

        # Should get a new instance
        adapter2 = AdapterRegistry.get_adapter("mock")
        assert adapter2 is not adapter1
        assert not adapter2.is_connected()

    def test_clear_instances_disconnects_adapters(self) -> None:
        """Test clear_instances disconnects connected adapters."""
        AdapterRegistry.register("mock", MockAdapter)

        adapter = AdapterRegistry.get_adapter("mock")
        adapter.connect()
        assert adapter.is_connected()

        AdapterRegistry.clear_instances()

        # Adapter should have been disconnected
        assert not adapter.is_connected()

    def test_clear_all(self) -> None:
        """Test clear_all removes all registrations and instances."""
        AdapterRegistry.register("mock1", MockAdapter)
        AdapterRegistry.register("mock2", MockAdapter)
        AdapterRegistry.get_adapter("mock1")  # Create instance

        AdapterRegistry.clear_all()

        assert AdapterRegistry.list_adapters() == []
        assert not AdapterRegistry.is_registered("mock1")
        assert not AdapterRegistry.is_registered("mock2")

    def test_unregister_disconnects_instance(self) -> None:
        """Test unregistering disconnects any cached instance."""
        AdapterRegistry.register("mock", MockAdapter)

        adapter = AdapterRegistry.get_adapter("mock")
        adapter.connect()
        assert adapter.is_connected()

        AdapterRegistry.unregister("mock")

        # Adapter should have been disconnected
        assert not adapter.is_connected()


class TestGetAdapterConvenienceFunction:
    """Test cases for get_adapter convenience function."""

    @pytest.fixture(autouse=True)
    def clean_registry(self) -> Generator[None, None, None]:
        """Clean the registry before and after each test."""
        AdapterRegistry.clear_all()
        yield
        AdapterRegistry.clear_all()

    def test_get_adapter_by_name(self) -> None:
        """Test get_adapter convenience function with explicit name."""
        AdapterRegistry.register("mock", MockAdapter)

        adapter = get_adapter("mock")
        assert isinstance(adapter, MockAdapter)

    def test_get_adapter_from_config(self) -> None:
        """Test get_adapter convenience function uses config."""
        AdapterRegistry.register("mock", MockAdapter)

        mock_config = MagicMock()
        mock_config.active_backend = "mock"

        with patch("jarvis.config.get_config", return_value=mock_config):
            adapter = get_adapter()
            assert isinstance(adapter, MockAdapter)

    def test_get_adapter_not_found(self) -> None:
        """Test get_adapter raises AdapterNotFoundError."""
        with pytest.raises(AdapterNotFoundError):
            get_adapter("nonexistent")


class TestAdapterRegistryErrorMessages:
    """Test error message quality."""

    @pytest.fixture(autouse=True)
    def clean_registry(self) -> Generator[None, None, None]:
        """Clean the registry before and after each test."""
        AdapterRegistry.clear_all()
        yield
        AdapterRegistry.clear_all()

    def test_error_message_shows_available_adapters(self) -> None:
        """Test error message includes available adapters."""
        AdapterRegistry.register("anytype", MockAdapter)
        AdapterRegistry.register("notion", MockAdapter)

        with pytest.raises(AdapterNotFoundError) as exc_info:
            AdapterRegistry.get_adapter("obsidian")

        error_msg = str(exc_info.value)
        assert "obsidian" in error_msg
        assert "anytype" in error_msg or "notion" in error_msg

    def test_error_message_when_no_adapters_registered(self) -> None:
        """Test error message when no adapters are registered."""
        with pytest.raises(AdapterNotFoundError) as exc_info:
            AdapterRegistry.get_adapter("mock")

        error_msg = str(exc_info.value)
        assert "mock" in error_msg
        assert "none" in error_msg.lower()
