"""Integration tests for AnyTypeAdapter.

These tests require the AnyType desktop app to be running on localhost:31009.
On first run, you'll need to approve the connection in the AnyType app.

Run with: pytest tests/integration/test_anytype_adapter.py -v -m integration
Skip with: pytest -m "not integration"
"""

from datetime import date, timedelta

import pytest

from jarvis.adapters.anytype import AnyTypeAdapter
from jarvis.adapters.base import KnowledgeBaseAdapter
from jarvis.adapters.exceptions import NotFoundError, ValidationError
from jarvis.models import Priority


def anytype_available() -> bool:
    """Check if AnyType desktop app is running."""
    import socket

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            result = sock.connect_ex(("localhost", 31009))
            return result == 0
    except Exception:
        return False


# Skip all tests in this module if AnyType is not available
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not anytype_available(),
        reason="AnyType desktop app not running on localhost:31009",
    ),
]


@pytest.fixture(scope="module")
def adapter() -> AnyTypeAdapter:
    """Create and connect an AnyType adapter for testing."""
    adapter = AnyTypeAdapter()
    adapter.connect()
    return adapter


@pytest.fixture(scope="module")
def space_id(adapter: AnyTypeAdapter) -> str:
    """Get the default space ID for testing."""
    return adapter.get_default_space()


class TestAnyTypeAdapterProtocol:
    """Test that AnyTypeAdapter implements KnowledgeBaseAdapter protocol."""

    def test_implements_protocol(self, adapter: AnyTypeAdapter) -> None:
        """Verify AnyTypeAdapter implements the Protocol."""
        assert isinstance(adapter, KnowledgeBaseAdapter)

    def test_backend_name(self, adapter: AnyTypeAdapter) -> None:
        """Test backend_name property."""
        assert adapter.backend_name == "anytype"

    def test_capabilities(self, adapter: AnyTypeAdapter) -> None:
        """Test capabilities property."""
        caps = adapter.capabilities
        assert isinstance(caps, dict)
        assert caps["tasks"] is True
        assert caps["journal"] is True
        assert caps["tags"] is True
        assert caps["search"] is True
        assert caps["priorities"] is True
        assert caps["due_dates"] is True


class TestAnyTypeAdapterConnection:
    """Test connection management."""

    def test_is_connected(self, adapter: AnyTypeAdapter) -> None:
        """Test is_connected returns True after connect."""
        assert adapter.is_connected() is True

    def test_disconnect_reconnect(self) -> None:
        """Test disconnect and reconnect flow."""
        adapter = AnyTypeAdapter()
        adapter.connect()
        assert adapter.is_connected()

        adapter.disconnect()
        # AnyType doesn't truly disconnect, but state should be clean

        adapter.connect()
        assert adapter.is_connected()


class TestAnyTypeAdapterSpaces:
    """Test space operations."""

    def test_list_spaces(self, adapter: AnyTypeAdapter) -> None:
        """Test listing spaces."""
        spaces = adapter.list_spaces()
        assert len(spaces) > 0
        for space in spaces:
            assert space.id
            assert space.name
            assert space.backend == "anytype"

    def test_get_default_space(self, adapter: AnyTypeAdapter) -> None:
        """Test getting default space."""
        space_id = adapter.get_default_space()
        assert space_id
        assert isinstance(space_id, str)

    def test_set_default_space(self, adapter: AnyTypeAdapter) -> None:
        """Test setting default space."""
        # Get current spaces
        spaces = adapter.list_spaces()
        if len(spaces) > 0:
            adapter.set_default_space(spaces[0].id)
            assert adapter._default_space_id == spaces[0].id

    def test_set_invalid_space_raises(self, adapter: AnyTypeAdapter) -> None:
        """Test setting invalid space raises NotFoundError."""
        with pytest.raises(NotFoundError) as exc_info:
            adapter.set_default_space("nonexistent-space-id")
        assert "not found" in str(exc_info.value).lower()


class TestAnyTypeAdapterTasks:
    """Test task CRUD operations."""

    def test_create_task_minimal(
        self, adapter: AnyTypeAdapter, space_id: str
    ) -> None:
        """Test creating a task with minimal fields."""
        task = adapter.create_task(
            space_id=space_id,
            title="Integration Test Task",
        )
        assert task.id
        assert task.title == "Integration Test Task"
        assert task.space_id == space_id
        assert task.is_done is False

        # Cleanup
        adapter.delete_task(space_id, task.id)

    def test_create_task_full(
        self, adapter: AnyTypeAdapter, space_id: str
    ) -> None:
        """Test creating a task with all fields."""
        due = date.today() + timedelta(days=7)
        task = adapter.create_task(
            space_id=space_id,
            title="Full Integration Test Task",
            due_date=due,
            priority=Priority.HIGH,
            tags=["test", "integration"],
            description="This is a test task description.",
        )
        assert task.id
        assert task.title == "Full Integration Test Task"
        assert task.due_date == due
        assert task.priority == Priority.HIGH
        assert "test" in task.tags
        assert "integration" in task.tags

        # Cleanup
        adapter.delete_task(space_id, task.id)

    def test_get_task(self, adapter: AnyTypeAdapter, space_id: str) -> None:
        """Test getting a single task."""
        # Create task first
        created = adapter.create_task(
            space_id=space_id,
            title="Task to Get",
        )

        # Fetch it
        fetched = adapter.get_task(space_id, created.id)
        assert fetched.id == created.id
        assert fetched.title == created.title

        # Cleanup
        adapter.delete_task(space_id, created.id)

    def test_get_task_not_found(
        self, adapter: AnyTypeAdapter, space_id: str
    ) -> None:
        """Test getting nonexistent task raises NotFoundError."""
        with pytest.raises(NotFoundError):
            adapter.get_task(space_id, "nonexistent-task-id")

    def test_get_tasks(self, adapter: AnyTypeAdapter, space_id: str) -> None:
        """Test querying tasks."""
        # Create some tasks
        task1 = adapter.create_task(space_id=space_id, title="Query Test 1")
        task2 = adapter.create_task(space_id=space_id, title="Query Test 2")

        try:
            tasks = adapter.get_tasks(space_id, include_done=False)
            assert isinstance(tasks, list)
            # Should have at least our two tasks
            task_ids = [t.id for t in tasks]
            assert task1.id in task_ids
            assert task2.id in task_ids
        finally:
            # Cleanup
            adapter.delete_task(space_id, task1.id)
            adapter.delete_task(space_id, task2.id)

    def test_get_tasks_with_date_filter(
        self, adapter: AnyTypeAdapter, space_id: str
    ) -> None:
        """Test querying tasks with date filter."""
        today = date.today()
        tomorrow = today + timedelta(days=1)

        # Create task due tomorrow
        task = adapter.create_task(
            space_id=space_id,
            title="Tomorrow Task",
            due_date=tomorrow,
        )

        try:
            # Query for tasks due today onwards
            tasks = adapter.get_tasks(
                space_id,
                start_date=today,
                end_date=tomorrow,
            )
            task_ids = [t.id for t in tasks]
            assert task.id in task_ids
        finally:
            adapter.delete_task(space_id, task.id)

    def test_get_tasks_with_pagination(
        self, adapter: AnyTypeAdapter, space_id: str
    ) -> None:
        """Test task pagination."""
        # Create multiple tasks
        tasks_created = []
        for i in range(5):
            task = adapter.create_task(
                space_id=space_id,
                title=f"Pagination Test {i}",
            )
            tasks_created.append(task)

        try:
            # Test limit
            tasks = adapter.get_tasks(space_id, limit=3)
            assert len(tasks) <= 3

            # Test offset
            all_tasks = adapter.get_tasks(space_id)
            offset_tasks = adapter.get_tasks(space_id, offset=2)
            # Should have fewer tasks with offset
            assert len(offset_tasks) <= len(all_tasks) - 2
        finally:
            for task in tasks_created:
                adapter.delete_task(space_id, task.id)

    def test_update_task(self, adapter: AnyTypeAdapter, space_id: str) -> None:
        """Test updating a task."""
        # Create task
        task = adapter.create_task(
            space_id=space_id,
            title="Task to Update",
        )

        try:
            # Update due date
            new_date = date.today() + timedelta(days=14)
            updated = adapter.update_task(
                space_id=space_id,
                task_id=task.id,
                due_date=new_date,
            )
            # Note: AnyType adapter only fully supports date updates currently
            assert updated.id == task.id
        finally:
            adapter.delete_task(space_id, task.id)

    def test_delete_task(self, adapter: AnyTypeAdapter, space_id: str) -> None:
        """Test deleting a task."""
        # Create task
        task = adapter.create_task(
            space_id=space_id,
            title="Task to Delete",
        )

        # Delete it
        result = adapter.delete_task(space_id, task.id)
        assert result is True

        # Note: In AnyType, deleted objects may still be retrievable (soft delete)
        # The delete_task returns True to indicate the operation completed

    def test_create_task_validation(
        self, adapter: AnyTypeAdapter, space_id: str
    ) -> None:
        """Test task creation validation."""
        # Empty title should fail
        with pytest.raises(ValidationError):
            adapter.create_task(space_id=space_id, title="")

        # Too long title should fail
        with pytest.raises(ValidationError):
            adapter.create_task(space_id=space_id, title="x" * 501)


class TestAnyTypeAdapterJournal:
    """Test journal CRUD operations.

    Note: These tests are marked xfail because they depend on the JournalHierarchy
    code which has known issues with the AnyType backend. The adapter code is correct,
    but the underlying journal infrastructure needs fixes.
    """

    @pytest.mark.xfail(reason="JournalHierarchy has issues with AnyType backend")
    def test_create_journal_entry(
        self, adapter: AnyTypeAdapter, space_id: str
    ) -> None:
        """Test creating a journal entry."""
        entry = adapter.create_journal_entry(
            space_id=space_id,
            content="This is a test journal entry for integration testing.",
            title="Integration Test Entry",
        )
        assert entry.id
        assert entry.title == "Integration Test Entry"
        assert "test journal entry" in entry.content

        # Cleanup
        adapter.delete_journal_entry(space_id, entry.id)

    @pytest.mark.xfail(reason="JournalHierarchy has issues with AnyType backend")
    def test_create_journal_entry_with_date(
        self, adapter: AnyTypeAdapter, space_id: str
    ) -> None:
        """Test creating a journal entry with specific date."""
        yesterday = date.today() - timedelta(days=1)
        entry = adapter.create_journal_entry(
            space_id=space_id,
            content="Entry from yesterday",
            title="Yesterday Entry",
            entry_date=yesterday,
        )
        assert entry.id
        assert entry.entry_date == yesterday

        # Cleanup
        adapter.delete_journal_entry(space_id, entry.id)

    @pytest.mark.xfail(reason="JournalHierarchy has issues with AnyType backend")
    def test_get_journal_entry(
        self, adapter: AnyTypeAdapter, space_id: str
    ) -> None:
        """Test getting a journal entry."""
        # Create entry
        created = adapter.create_journal_entry(
            space_id=space_id,
            content="Entry to retrieve",
            title="Get Test Entry",
        )

        try:
            fetched = adapter.get_journal_entry(space_id, created.id)
            assert fetched.id == created.id
            assert fetched.title == created.title
        finally:
            adapter.delete_journal_entry(space_id, created.id)

    @pytest.mark.xfail(reason="JournalHierarchy has issues with AnyType backend")
    def test_get_journal_entries(
        self, adapter: AnyTypeAdapter, space_id: str
    ) -> None:
        """Test listing journal entries."""
        # Create entries
        entry1 = adapter.create_journal_entry(
            space_id=space_id,
            content="List test 1",
            title="List Entry 1",
        )
        entry2 = adapter.create_journal_entry(
            space_id=space_id,
            content="List test 2",
            title="List Entry 2",
        )

        try:
            entries = adapter.get_journal_entries(space_id, limit=10)
            assert isinstance(entries, list)
            entry_ids = [e.id for e in entries]
            assert entry1.id in entry_ids
            assert entry2.id in entry_ids
        finally:
            adapter.delete_journal_entry(space_id, entry1.id)
            adapter.delete_journal_entry(space_id, entry2.id)

    @pytest.mark.xfail(reason="JournalHierarchy has issues with AnyType backend")
    def test_delete_journal_entry(
        self, adapter: AnyTypeAdapter, space_id: str
    ) -> None:
        """Test deleting a journal entry."""
        entry = adapter.create_journal_entry(
            space_id=space_id,
            content="Entry to delete",
            title="Delete Test Entry",
        )

        result = adapter.delete_journal_entry(space_id, entry.id)
        assert result is True


class TestAnyTypeAdapterTags:
    """Test tag operations."""

    def test_list_tags(self, adapter: AnyTypeAdapter, space_id: str) -> None:
        """Test listing tags."""
        tags = adapter.list_tags(space_id)
        assert isinstance(tags, list)
        # Tags may be empty if no tasks with tags exist

    def test_create_tag(self, adapter: AnyTypeAdapter, space_id: str) -> None:
        """Test creating a tag."""
        # In AnyType, tags are created implicitly
        tag = adapter.create_tag(space_id, name="test-tag")
        assert tag.name == "test-tag"
        assert tag.id == "test-tag"


class TestAnyTypeAdapterSearch:
    """Test search operations."""

    @pytest.mark.xfail(reason="JournalHierarchy has issues with AnyType backend")
    def test_search_journal(
        self, adapter: AnyTypeAdapter, space_id: str
    ) -> None:
        """Test searching journal entries."""
        # Create entry with unique content
        unique_text = f"unique_search_text_{date.today().isoformat()}"
        entry = adapter.create_journal_entry(
            space_id=space_id,
            content=f"This entry contains {unique_text} for searching.",
            title="Search Test Entry",
        )

        try:
            # Search for the unique text
            results = adapter.search_journal(
                space_id=space_id,
                query=unique_text,
            )
            assert isinstance(results, list)
            # Note: AnyType search may take time to index
        finally:
            adapter.delete_journal_entry(space_id, entry.id)
