"""Tests for KnowledgeBaseAdapter Protocol."""

from datetime import date, datetime

import pytest

from jarvis.adapters.base import KnowledgeBaseAdapter
from jarvis.models import BackendObject, JournalEntry, Priority, Space, Tag, Task


class TestKnowledgeBaseAdapterProtocol:
    """Test cases for the KnowledgeBaseAdapter Protocol."""

    def test_protocol_is_runtime_checkable(self) -> None:
        """Test that Protocol can be used with isinstance checks."""
        # Protocol should be runtime checkable (decorated with @runtime_checkable)
        # This allows isinstance() checks against the Protocol
        assert hasattr(KnowledgeBaseAdapter, "_is_runtime_protocol")
        assert KnowledgeBaseAdapter._is_runtime_protocol is True

    def test_minimal_adapter_satisfies_protocol(self) -> None:
        """Test that a class implementing all methods satisfies the Protocol."""

        class MinimalAdapter:
            """Minimal implementation of KnowledgeBaseAdapter."""

            @property
            def capabilities(self) -> dict[str, bool]:
                return {"tasks": True, "journal": True, "tags": True}

            @property
            def backend_name(self) -> str:
                return "minimal"

            def connect(self) -> None:
                pass

            def disconnect(self) -> None:
                pass

            def is_connected(self) -> bool:
                return True

            def list_spaces(self) -> list[Space]:
                return []

            def get_default_space(self) -> str:
                return "default"

            def set_default_space(self, space_id: str) -> None:
                pass

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
                    content="Test content",
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

            def create_tag(
                self, space_id: str, name: str, color: str | None = None
            ) -> Tag:
                return Tag(id="tag-1", name=name, color=color)

            def get_object(self, space_id: str, object_id: str) -> BackendObject:
                return BackendObject(id=object_id, space_id=space_id, backend="minimal")

            def update_object(
                self, space_id: str, object_id: str, updates: dict[str, object]
            ) -> BackendObject:
                return BackendObject(id=object_id, space_id=space_id, backend="minimal")

        adapter = MinimalAdapter()

        # Should satisfy isinstance check due to @runtime_checkable
        assert isinstance(adapter, KnowledgeBaseAdapter)

    def test_incomplete_adapter_fails_isinstance(self) -> None:
        """Test that a class missing methods fails isinstance check."""

        class IncompleteAdapter:
            """Adapter missing most methods."""

            @property
            def capabilities(self) -> dict[str, bool]:
                return {}

        adapter = IncompleteAdapter()

        # Should fail isinstance check
        assert not isinstance(adapter, KnowledgeBaseAdapter)


class TestMinimalAdapterBehavior:
    """Test that a minimal adapter implementation works correctly."""

    @pytest.fixture
    def adapter(self) -> KnowledgeBaseAdapter:
        """Create a minimal adapter for testing."""

        class TestAdapter:
            """Test adapter implementation."""

            def __init__(self) -> None:
                self._connected = False
                self._default_space = "space-1"

            @property
            def capabilities(self) -> dict[str, bool]:
                return {
                    "tasks": True,
                    "journal": True,
                    "tags": True,
                    "search": True,
                    "priorities": True,
                    "due_dates": True,
                    "daily_notes": False,
                    "relations": False,
                    "custom_properties": False,
                }

            @property
            def backend_name(self) -> str:
                return "test"

            def connect(self) -> None:
                self._connected = True

            def disconnect(self) -> None:
                self._connected = False

            def is_connected(self) -> bool:
                return self._connected

            def list_spaces(self) -> list[Space]:
                return [Space(id="space-1", name="Test Space", backend="test")]

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
                now = datetime.now()
                return Task(
                    id="task-new",
                    space_id=space_id,
                    title=title,
                    due_date=due_date,
                    priority=priority,
                    tags=tags or [],
                    description=description,
                    is_done=False,
                    created_at=now,
                    updated_at=now,
                )

            def get_task(self, space_id: str, task_id: str) -> Task:
                return Task(
                    id=task_id,
                    space_id=space_id,
                    title="Existing Task",
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
                    id="entry-new",
                    space_id=space_id,
                    title=title or "New Entry",
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
                return [Tag(id="tag-1", name="work", color="#ff0000")]

            def create_tag(
                self, space_id: str, name: str, color: str | None = None
            ) -> Tag:
                return Tag(id="tag-new", name=name, color=color)

            def get_object(self, space_id: str, object_id: str) -> BackendObject:
                return BackendObject(id=object_id, space_id=space_id, backend="test")

            def update_object(
                self, space_id: str, object_id: str, updates: dict[str, object]
            ) -> BackendObject:
                return BackendObject(id=object_id, space_id=space_id, backend="test")

        return TestAdapter()

    def test_capabilities_returns_dict(
        self, adapter: KnowledgeBaseAdapter
    ) -> None:
        """Test capabilities property returns expected dict."""
        caps = adapter.capabilities
        assert isinstance(caps, dict)
        assert caps["tasks"] is True
        assert caps["journal"] is True
        assert caps["daily_notes"] is False

    def test_backend_name_returns_string(
        self, adapter: KnowledgeBaseAdapter
    ) -> None:
        """Test backend_name property."""
        assert adapter.backend_name == "test"

    def test_connection_lifecycle(self, adapter: KnowledgeBaseAdapter) -> None:
        """Test connect/disconnect/is_connected cycle."""
        assert adapter.is_connected() is False

        adapter.connect()
        assert adapter.is_connected() is True

        adapter.disconnect()
        assert adapter.is_connected() is False

    def test_list_spaces(self, adapter: KnowledgeBaseAdapter) -> None:
        """Test list_spaces returns Space objects."""
        spaces = adapter.list_spaces()
        assert len(spaces) == 1
        assert spaces[0].id == "space-1"
        assert spaces[0].backend == "test"

    def test_default_space_operations(
        self, adapter: KnowledgeBaseAdapter
    ) -> None:
        """Test get/set default space."""
        assert adapter.get_default_space() == "space-1"

        adapter.set_default_space("space-2")
        assert adapter.get_default_space() == "space-2"

    def test_create_task(self, adapter: KnowledgeBaseAdapter) -> None:
        """Test create_task returns Task with correct fields."""
        task = adapter.create_task(
            space_id="space-1",
            title="Buy groceries",
            due_date=date(2025, 1, 30),
            priority=Priority.HIGH,
            tags=["shopping"],
        )

        assert task.id == "task-new"
        assert task.title == "Buy groceries"
        assert task.due_date == date(2025, 1, 30)
        assert task.priority == Priority.HIGH
        assert "shopping" in task.tags
        assert task.is_done is False

    def test_get_task(self, adapter: KnowledgeBaseAdapter) -> None:
        """Test get_task retrieves task by ID."""
        task = adapter.get_task("space-1", "task-123")
        assert task.id == "task-123"

    def test_create_journal_entry(self, adapter: KnowledgeBaseAdapter) -> None:
        """Test create_journal_entry returns JournalEntry."""
        entry = adapter.create_journal_entry(
            space_id="space-1",
            content="Today was productive.",
            title="Daily Reflection",
            entry_date=date(2025, 1, 25),
        )

        assert entry.id == "entry-new"
        assert entry.title == "Daily Reflection"
        assert entry.content == "Today was productive."
        assert entry.entry_date == date(2025, 1, 25)

    def test_list_tags(self, adapter: KnowledgeBaseAdapter) -> None:
        """Test list_tags returns Tag objects."""
        tags = adapter.list_tags("space-1")
        assert len(tags) == 1
        assert tags[0].name == "work"
        assert tags[0].color == "#ff0000"

    def test_create_tag(self, adapter: KnowledgeBaseAdapter) -> None:
        """Test create_tag creates new tag."""
        tag = adapter.create_tag("space-1", "personal", "#0000ff")
        assert tag.name == "personal"
        assert tag.color == "#0000ff"


class TestCapabilitiesContract:
    """Test the expected capabilities contract."""

    def test_required_capability_keys(self) -> None:
        """Document the required capability keys."""
        required_keys = {
            "tasks",
            "journal",
            "tags",
            "search",
            "priorities",
            "due_dates",
            "daily_notes",
            "relations",
            "custom_properties",
        }

        # This is a documentation test - ensures we know the contract
        assert len(required_keys) == 9

    def test_capability_values_are_booleans(self) -> None:
        """Test that capabilities should return boolean values."""

        class CapabilityTestAdapter:
            @property
            def capabilities(self) -> dict[str, bool]:
                return {
                    "tasks": True,
                    "journal": False,
                    "tags": True,
                    "search": False,
                    "priorities": True,
                    "due_dates": True,
                    "daily_notes": False,
                    "relations": False,
                    "custom_properties": False,
                }

            @property
            def backend_name(self) -> str:
                return "test"

        adapter = CapabilityTestAdapter()
        for key, value in adapter.capabilities.items():
            assert isinstance(value, bool), f"{key} should be bool, got {type(value)}"
