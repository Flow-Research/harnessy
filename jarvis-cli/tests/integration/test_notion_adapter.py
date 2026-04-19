"""Integration tests for NotionAdapter.

These tests require:
- JARVIS_NOTION_TOKEN environment variable
- Configured workspace with task and journal databases

Run with: pytest tests/integration/test_notion_adapter.py -v -m integration
Skip with: pytest -m "not integration"
"""

import os
from datetime import date, timedelta

import pytest

from jarvis.adapters.base import KnowledgeBaseAdapter
from jarvis.adapters.exceptions import AuthError, NotFoundError, ValidationError
from jarvis.adapters.notion import NotionAdapter
from jarvis.config import JarvisConfig
from jarvis.models import Priority


def notion_configured() -> bool:
    """Check if Notion is configured for testing."""
    token = os.environ.get("JARVIS_NOTION_TOKEN")
    if not token:
        return False

    # Try to load config
    try:
        config = JarvisConfig.load()
        if config.backends.notion is None:
            return False
        if not config.backends.notion.task_database_id:
            return False
        return True
    except Exception:
        return False


# Skip all tests in this module if Notion is not configured
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not notion_configured(),
        reason="Notion not configured (need JARVIS_NOTION_TOKEN and config)",
    ),
]


@pytest.fixture(scope="module")
def config() -> JarvisConfig:
    """Load Jarvis config for testing."""
    return JarvisConfig.load()


@pytest.fixture(scope="module")
def adapter(config: JarvisConfig) -> NotionAdapter:
    """Create and connect a Notion adapter for testing."""
    adapter = NotionAdapter(config)
    adapter.connect()
    return adapter


@pytest.fixture(scope="module")
def space_id(adapter: NotionAdapter) -> str:
    """Get the workspace ID for testing."""
    return adapter.get_default_space()


class TestNotionAdapterProtocol:
    """Test that NotionAdapter implements KnowledgeBaseAdapter protocol."""

    def test_implements_protocol(self, adapter: NotionAdapter) -> None:
        """Verify NotionAdapter implements the Protocol."""
        assert isinstance(adapter, KnowledgeBaseAdapter)

    def test_backend_name(self, adapter: NotionAdapter) -> None:
        """Test backend_name property."""
        assert adapter.backend_name == "notion"

    def test_capabilities(self, adapter: NotionAdapter) -> None:
        """Test capabilities property."""
        caps = adapter.capabilities
        assert isinstance(caps, dict)
        assert caps["tasks"] is True
        assert caps["journal"] is True
        assert caps["tags"] is True
        assert caps["search"] is True
        assert caps["priorities"] is True
        assert caps["due_dates"] is True
        assert caps["custom_properties"] is True


class TestNotionAdapterConnection:
    """Test connection management."""

    def test_is_connected(self, adapter: NotionAdapter) -> None:
        """Test is_connected returns True after connect."""
        assert adapter.is_connected() is True

    def test_disconnect_reconnect(self, config: JarvisConfig) -> None:
        """Test disconnect and reconnect flow."""
        adapter = NotionAdapter(config)
        adapter.connect()
        assert adapter.is_connected()

        adapter.disconnect()
        assert adapter.is_connected() is False

        adapter.connect()
        assert adapter.is_connected()

    def test_invalid_token_raises_auth_error(self) -> None:
        """Test that invalid token raises AuthError."""
        # Save original token
        original_token = os.environ.get("JARVIS_NOTION_TOKEN")

        try:
            # Set invalid token
            os.environ["JARVIS_NOTION_TOKEN"] = "invalid_token"

            adapter = NotionAdapter()
            with pytest.raises(AuthError):
                adapter.connect()
        finally:
            # Restore original token
            if original_token:
                os.environ["JARVIS_NOTION_TOKEN"] = original_token


class TestNotionAdapterSpaces:
    """Test space operations."""

    def test_list_spaces(self, adapter: NotionAdapter) -> None:
        """Test listing spaces (single workspace for Notion)."""
        spaces = adapter.list_spaces()
        assert len(spaces) == 1
        assert spaces[0].backend == "notion"

    def test_get_default_space(self, adapter: NotionAdapter) -> None:
        """Test getting default workspace."""
        space_id = adapter.get_default_space()
        assert space_id
        assert isinstance(space_id, str)

    def test_set_default_space_is_noop(self, adapter: NotionAdapter) -> None:
        """Test that set_default_space is a no-op for Notion."""
        # Should not raise
        adapter.set_default_space("any-id")


class TestNotionAdapterTasks:
    """Test task CRUD operations."""

    def test_create_task_minimal(
        self, adapter: NotionAdapter, space_id: str
    ) -> None:
        """Test creating a task with minimal fields."""
        task = adapter.create_task(
            space_id=space_id,
            title="Notion Integration Test Task",
        )
        assert task.id
        assert task.title == "Notion Integration Test Task"
        assert task.is_done is False

        # Cleanup
        adapter.delete_task(space_id, task.id)

    def test_create_task_full(
        self, adapter: NotionAdapter, space_id: str
    ) -> None:
        """Test creating a task with all fields."""
        due = date.today() + timedelta(days=7)
        task = adapter.create_task(
            space_id=space_id,
            title="Full Notion Integration Test Task",
            due_date=due,
            priority=Priority.HIGH,
            tags=["test", "notion"],
            description="This is a test task description for Notion.",
        )
        assert task.id
        assert task.title == "Full Notion Integration Test Task"
        assert task.due_date == due
        assert task.priority == Priority.HIGH

        # Cleanup
        adapter.delete_task(space_id, task.id)

    def test_get_task(self, adapter: NotionAdapter, space_id: str) -> None:
        """Test getting a single task."""
        # Create task first
        created = adapter.create_task(
            space_id=space_id,
            title="Notion Task to Get",
        )

        # Fetch it
        fetched = adapter.get_task(space_id, created.id)
        assert fetched.id == created.id
        assert fetched.title == created.title

        # Cleanup
        adapter.delete_task(space_id, created.id)

    def test_get_task_not_found(
        self, adapter: NotionAdapter, space_id: str
    ) -> None:
        """Test getting nonexistent task raises NotFoundError."""
        # Use a valid UUID format but nonexistent
        fake_id = "00000000-0000-0000-0000-000000000000"
        with pytest.raises(NotFoundError):
            adapter.get_task(space_id, fake_id)

    def test_get_tasks(self, adapter: NotionAdapter, space_id: str) -> None:
        """Test querying tasks."""
        # Create some tasks
        task1 = adapter.create_task(
            space_id=space_id, title="Notion Query Test 1"
        )
        task2 = adapter.create_task(
            space_id=space_id, title="Notion Query Test 2"
        )

        try:
            tasks = adapter.get_tasks(space_id, include_done=False)
            assert isinstance(tasks, list)
            task_ids = [t.id for t in tasks]
            assert task1.id in task_ids
            assert task2.id in task_ids
        finally:
            # Cleanup
            adapter.delete_task(space_id, task1.id)
            adapter.delete_task(space_id, task2.id)

    def test_get_tasks_with_date_filter(
        self, adapter: NotionAdapter, space_id: str
    ) -> None:
        """Test querying tasks with date filter."""
        today = date.today()
        tomorrow = today + timedelta(days=1)

        # Create task due tomorrow
        task = adapter.create_task(
            space_id=space_id,
            title="Notion Tomorrow Task",
            due_date=tomorrow,
        )

        try:
            # Query for tasks due from today to tomorrow
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
        self, adapter: NotionAdapter, space_id: str
    ) -> None:
        """Test task pagination."""
        # Create multiple tasks
        tasks_created = []
        for i in range(5):
            task = adapter.create_task(
                space_id=space_id,
                title=f"Notion Pagination Test {i}",
            )
            tasks_created.append(task)

        try:
            # Test limit
            tasks = adapter.get_tasks(space_id, limit=3)
            assert len(tasks) <= 3

            # Test offset
            all_tasks = adapter.get_tasks(space_id, limit=100)
            offset_tasks = adapter.get_tasks(space_id, offset=2, limit=100)
            assert len(offset_tasks) <= len(all_tasks) - 2
        finally:
            for task in tasks_created:
                adapter.delete_task(space_id, task.id)

    def test_update_task(self, adapter: NotionAdapter, space_id: str) -> None:
        """Test updating a task."""
        # Create task
        task = adapter.create_task(
            space_id=space_id,
            title="Notion Task to Update",
        )

        try:
            # Update title and due date
            new_date = date.today() + timedelta(days=14)
            updated = adapter.update_task(
                space_id=space_id,
                task_id=task.id,
                title="Updated Notion Task",
                due_date=new_date,
                priority=Priority.LOW,
            )
            assert updated.id == task.id
            assert updated.title == "Updated Notion Task"
            assert updated.due_date == new_date
            assert updated.priority == Priority.LOW
        finally:
            adapter.delete_task(space_id, task.id)

    def test_update_task_mark_done(
        self, adapter: NotionAdapter, space_id: str
    ) -> None:
        """Test marking a task as done."""
        task = adapter.create_task(
            space_id=space_id,
            title="Notion Task to Complete",
        )

        try:
            updated = adapter.update_task(
                space_id=space_id,
                task_id=task.id,
                is_done=True,
            )
            assert updated.is_done is True
        finally:
            adapter.delete_task(space_id, task.id)

    def test_delete_task(self, adapter: NotionAdapter, space_id: str) -> None:
        """Test deleting (archiving) a task."""
        # Create task
        task = adapter.create_task(
            space_id=space_id,
            title="Notion Task to Delete",
        )

        # Delete it (archives in Notion)
        result = adapter.delete_task(space_id, task.id)
        assert result is True

        # In Notion, archived pages can still be retrieved but won't appear in queries
        # The page still exists, just archived

    def test_create_task_validation(
        self, adapter: NotionAdapter, space_id: str
    ) -> None:
        """Test task creation validation."""
        # Empty title should fail
        with pytest.raises(ValidationError):
            adapter.create_task(space_id=space_id, title="")

        # Too long title should fail
        with pytest.raises(ValidationError):
            adapter.create_task(space_id=space_id, title="x" * 501)

    def test_negative_offset_validation(
        self, adapter: NotionAdapter, space_id: str
    ) -> None:
        """Test negative offset raises ValidationError."""
        with pytest.raises(ValidationError):
            adapter.get_tasks(space_id, offset=-1)


class TestNotionAdapterJournal:
    """Test journal CRUD operations."""

    def test_create_journal_entry(
        self, adapter: NotionAdapter, space_id: str
    ) -> None:
        """Test creating a journal entry."""
        entry = adapter.create_journal_entry(
            space_id=space_id,
            content="This is a test journal entry for Notion integration.",
            title="Notion Integration Test Entry",
        )
        assert entry.id
        assert entry.title == "Notion Integration Test Entry"
        assert "test journal entry" in entry.content

        # Cleanup
        adapter.delete_journal_entry(space_id, entry.id)

    def test_create_journal_entry_with_date(
        self, adapter: NotionAdapter, space_id: str
    ) -> None:
        """Test creating a journal entry with specific date."""
        yesterday = date.today() - timedelta(days=1)
        entry = adapter.create_journal_entry(
            space_id=space_id,
            content="Notion entry from yesterday",
            title="Notion Yesterday Entry",
            entry_date=yesterday,
        )
        assert entry.id
        assert entry.entry_date == yesterday

        # Cleanup
        adapter.delete_journal_entry(space_id, entry.id)

    def test_create_journal_auto_title(
        self, adapter: NotionAdapter, space_id: str
    ) -> None:
        """Test journal entry with auto-generated title."""
        entry = adapter.create_journal_entry(
            space_id=space_id,
            content="Entry without explicit title for Notion.",
        )
        assert entry.id
        # Title should be derived from content
        assert "Entry without explicit" in entry.title or entry.title

        # Cleanup
        adapter.delete_journal_entry(space_id, entry.id)

    def test_get_journal_entry(
        self, adapter: NotionAdapter, space_id: str
    ) -> None:
        """Test getting a journal entry with content."""
        # Create entry
        created = adapter.create_journal_entry(
            space_id=space_id,
            content="Entry content to retrieve from Notion.",
            title="Notion Get Test Entry",
        )

        try:
            fetched = adapter.get_journal_entry(space_id, created.id)
            assert fetched.id == created.id
            assert fetched.title == created.title
            assert "Entry content" in fetched.content
        finally:
            adapter.delete_journal_entry(space_id, created.id)

    def test_get_journal_entries(
        self, adapter: NotionAdapter, space_id: str
    ) -> None:
        """Test listing journal entries."""
        # Create entries
        entry1 = adapter.create_journal_entry(
            space_id=space_id,
            content="Notion list test 1",
            title="Notion List Entry 1",
        )
        entry2 = adapter.create_journal_entry(
            space_id=space_id,
            content="Notion list test 2",
            title="Notion List Entry 2",
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

    def test_update_journal_entry(
        self, adapter: NotionAdapter, space_id: str
    ) -> None:
        """Test updating a journal entry."""
        entry = adapter.create_journal_entry(
            space_id=space_id,
            content="Original Notion content",
            title="Notion Entry to Update",
        )

        try:
            updated = adapter.update_journal_entry(
                space_id=space_id,
                entry_id=entry.id,
                title="Updated Notion Entry",
                content="New Notion content after update.",
            )
            assert updated.title == "Updated Notion Entry"
            assert "New Notion content" in updated.content
        finally:
            adapter.delete_journal_entry(space_id, entry.id)

    def test_delete_journal_entry(
        self, adapter: NotionAdapter, space_id: str
    ) -> None:
        """Test deleting (archiving) a journal entry."""
        entry = adapter.create_journal_entry(
            space_id=space_id,
            content="Notion entry to delete",
            title="Notion Delete Test Entry",
        )

        result = adapter.delete_journal_entry(space_id, entry.id)
        assert result is True


class TestNotionAdapterTags:
    """Test tag operations."""

    def test_list_tags(self, adapter: NotionAdapter, space_id: str) -> None:
        """Test listing tags from database schema."""
        tags = adapter.list_tags(space_id)
        assert isinstance(tags, list)
        # Tags depend on database schema configuration

    def test_create_tag(self, adapter: NotionAdapter, space_id: str) -> None:
        """Test creating a tag (returns placeholder in Notion)."""
        tag = adapter.create_tag(space_id, name="notion-test-tag")
        assert tag.name == "notion-test-tag"
        # Notion creates tags implicitly when used


class TestNotionAdapterSearch:
    """Test search operations."""

    def test_search_journal(
        self, adapter: NotionAdapter, space_id: str
    ) -> None:
        """Test searching journal entries."""
        # Create entry with unique content
        unique_text = f"notion_unique_search_{date.today().isoformat()}"
        entry = adapter.create_journal_entry(
            space_id=space_id,
            content=f"This Notion entry contains {unique_text} for searching.",
            title="Notion Search Test Entry",
        )

        try:
            # Search for the unique text
            # Note: Notion search API may have delays in indexing
            results = adapter.search_journal(
                space_id=space_id,
                query=unique_text,
            )
            assert isinstance(results, list)
        finally:
            adapter.delete_journal_entry(space_id, entry.id)
