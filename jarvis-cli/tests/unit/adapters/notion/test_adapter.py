"""Tests for NotionAdapter."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from jarvis.adapters.notion.adapter import NotionAdapter
from jarvis.adapters.exceptions import (
    AuthError,
    ConfigError,
    ConnectionError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)
from jarvis.config.schema import BackendsConfig, JarvisConfig, NotionConfig
from jarvis.models import Priority


def create_notion_config() -> JarvisConfig:
    """Create a test config with Notion settings."""
    return JarvisConfig(
        active_backend="notion",
        backends=BackendsConfig(
            notion=NotionConfig(
                workspace_id="ws-123",
                task_database_id="db-tasks",
                journal_database_id="db-journal",
            )
        ),
    )


class TestNotionAdapterCapabilities:
    """Test capability declarations."""

    def test_capabilities(self) -> None:
        """Test capabilities property."""
        adapter = NotionAdapter()
        caps = adapter.capabilities

        assert caps["tasks"] is True
        assert caps["journal"] is True
        assert caps["tags"] is True
        assert caps["search"] is True
        assert caps["priorities"] is True
        assert caps["due_dates"] is True
        assert caps["daily_notes"] is False
        assert caps["relations"] is True
        assert caps["custom_properties"] is True

    def test_backend_name(self) -> None:
        """Test backend_name property."""
        adapter = NotionAdapter()
        assert adapter.backend_name == "notion"


class TestNotionAdapterConnection:
    """Test connection management."""

    def test_connect_without_notion_client(self) -> None:
        """Test connect raises when notion-client not installed."""
        adapter = NotionAdapter()

        # Mock the import to fail
        with patch.dict("sys.modules", {"notion_client": None}):
            with patch(
                "jarvis.adapters.notion.adapter.NotionAdapter.connect",
                side_effect=ConnectionError(
                    "notion-client package is not installed",
                    backend="notion",
                ),
            ):
                with pytest.raises(ConnectionError) as exc_info:
                    adapter.connect()
                assert "notion-client" in str(exc_info.value)

    def test_connect_without_token(self) -> None:
        """Test connect raises when token is missing."""
        adapter = NotionAdapter()

        with patch(
            "jarvis.adapters.notion.adapter.get_backend_token",
            side_effect=Exception("No API token found"),
        ):
            with pytest.raises(AuthError):
                adapter.connect()

    def test_connect_with_invalid_token(self) -> None:
        """Test connect raises AuthError for 401."""
        adapter = NotionAdapter()

        with patch("jarvis.adapters.notion.adapter.get_backend_token", return_value="invalid"):
            with patch("notion_client.Client") as mock_client_class:
                from notion_client.errors import APIErrorCode, APIResponseError

                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_response.status_code = 401
                mock_response.headers = {}

                mock_client.users.me.side_effect = APIResponseError(
                    mock_response, "Unauthorized", APIErrorCode.Unauthorized
                )
                mock_client_class.return_value = mock_client

                with pytest.raises(AuthError) as exc_info:
                    adapter.connect()
                assert "Invalid Notion token" in str(exc_info.value)

    def test_connect_success(self) -> None:
        """Test successful connection."""
        adapter = NotionAdapter()

        with patch("jarvis.adapters.notion.adapter.get_backend_token", return_value="valid-token"):
            with patch("notion_client.Client") as mock_client_class:
                mock_client = MagicMock()
                mock_client.users.me.return_value = {"id": "user-1"}
                mock_client_class.return_value = mock_client

                adapter.connect()

                assert adapter.is_connected() is True
                mock_client_class.assert_called_once_with(
                    auth="valid-token",
                    notion_version=NotionAdapter.NOTION_API_VERSION,
                )

    def test_is_connected_false_initially(self) -> None:
        """Test is_connected returns False initially."""
        adapter = NotionAdapter()
        assert adapter.is_connected() is False

    def test_disconnect(self) -> None:
        """Test disconnect clears connection state."""
        adapter = NotionAdapter()
        adapter._connected = True
        adapter._client = MagicMock()

        adapter.disconnect()

        assert adapter.is_connected() is False
        assert adapter._client is None


class TestNotionAdapterSpaces:
    """Test space operations."""

    @pytest.fixture
    def connected_adapter(self) -> NotionAdapter:
        """Create a connected adapter with config."""
        config = create_notion_config()
        adapter = NotionAdapter(config)
        adapter._connected = True
        adapter._client = MagicMock()
        return adapter

    def test_list_spaces_not_connected(self) -> None:
        """Test list_spaces raises when not connected."""
        config = create_notion_config()
        adapter = NotionAdapter(config)
        with pytest.raises(ConnectionError):
            adapter.list_spaces()

    def test_list_spaces_returns_workspace(self, connected_adapter: NotionAdapter) -> None:
        """Test list_spaces returns workspace as single space."""
        spaces = connected_adapter.list_spaces()

        assert len(spaces) == 1
        assert spaces[0].id == "ws-123"
        assert spaces[0].name == "Notion Workspace"
        assert spaces[0].backend == "notion"

    def test_get_default_space(self, connected_adapter: NotionAdapter) -> None:
        """Test get_default_space returns workspace ID."""
        result = connected_adapter.get_default_space()
        assert result == "ws-123"

    def test_get_default_space_no_config(self) -> None:
        """Test get_default_space raises when not configured."""
        adapter = NotionAdapter()
        with pytest.raises(ConfigError):
            adapter.get_default_space()

    def test_set_default_space_noop(self, connected_adapter: NotionAdapter) -> None:
        """Test set_default_space is a no-op."""
        # Should not raise
        connected_adapter.set_default_space("anything")


class TestNotionAdapterTasks:
    """Test task operations."""

    @pytest.fixture
    def connected_adapter(self) -> NotionAdapter:
        """Create a connected adapter with config."""
        config = create_notion_config()
        adapter = NotionAdapter(config)
        adapter._connected = True
        adapter._client = MagicMock()
        return adapter

    def test_create_task_not_connected(self) -> None:
        """Test create_task raises when not connected."""
        config = create_notion_config()
        adapter = NotionAdapter(config)
        with pytest.raises(ConnectionError):
            adapter.create_task("space-1", "Test task")

    def test_create_task_empty_title(self, connected_adapter: NotionAdapter) -> None:
        """Test create_task rejects empty title."""
        with pytest.raises(ValidationError) as exc_info:
            connected_adapter.create_task("space-1", "")
        assert "empty" in str(exc_info.value).lower()

    def test_create_task_title_too_long(self, connected_adapter: NotionAdapter) -> None:
        """Test create_task rejects too-long title."""
        with pytest.raises(ValidationError) as exc_info:
            connected_adapter.create_task("space-1", "x" * 501)
        assert "500" in str(exc_info.value)

    def test_create_task_success(self, connected_adapter: NotionAdapter) -> None:
        """Test create_task returns Task model."""
        mock_response = {
            "id": "page-123",
            "created_time": "2025-01-25T10:00:00.000Z",
            "last_edited_time": "2025-01-25T10:00:00.000Z",
            "properties": {
                "Name": {"title": [{"plain_text": "Buy groceries"}]},
                "Due Date": {"date": {"start": "2025-01-30"}},
                "Priority": {"select": {"name": "High"}},
                "Tags": {"multi_select": [{"name": "shopping"}]},
                "Done": {"checkbox": False},
            },
        }

        connected_adapter._client.pages.create.return_value = mock_response

        task = connected_adapter.create_task(
            space_id="space-1",
            title="Buy groceries",
            due_date=date(2025, 1, 30),
            priority=Priority.HIGH,
            tags=["shopping"],
        )

        assert task.id == "page-123"
        assert task.title == "Buy groceries"
        assert task.due_date == date(2025, 1, 30)
        assert task.priority == Priority.HIGH
        assert "shopping" in task.tags
        assert task.is_done is False

    def test_get_tasks_negative_offset(self, connected_adapter: NotionAdapter) -> None:
        """Test get_tasks rejects negative offset."""
        with pytest.raises(ValidationError) as exc_info:
            connected_adapter.get_tasks("space-1", offset=-1)
        assert "non-negative" in str(exc_info.value).lower()

    def test_get_tasks_success(self, connected_adapter: NotionAdapter) -> None:
        """Test get_tasks returns list of tasks."""
        mock_response = {
            "results": [
                {
                    "id": "page-1",
                    "created_time": "2025-01-25T10:00:00.000Z",
                    "last_edited_time": "2025-01-25T10:00:00.000Z",
                    "properties": {
                        "Name": {"title": [{"plain_text": "Task 1"}]},
                        "Done": {"checkbox": False},
                    },
                },
                {
                    "id": "page-2",
                    "created_time": "2025-01-25T11:00:00.000Z",
                    "last_edited_time": "2025-01-25T11:00:00.000Z",
                    "properties": {
                        "Name": {"title": [{"plain_text": "Task 2"}]},
                        "Done": {"checkbox": False},
                    },
                },
            ],
            "has_more": False,
        }

        connected_adapter._client.databases.query.return_value = mock_response

        tasks = connected_adapter.get_tasks("space-1")

        assert len(tasks) == 2
        assert tasks[0].id == "page-1"
        assert tasks[1].id == "page-2"

    def test_get_task_not_found(self, connected_adapter: NotionAdapter) -> None:
        """Test get_task raises NotFoundError."""
        from notion_client.errors import APIErrorCode, APIResponseError

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.headers = {}
        error = APIResponseError(mock_response, "Page not found", APIErrorCode.ObjectNotFound)

        connected_adapter._client.pages.retrieve.side_effect = error

        with pytest.raises(NotFoundError):
            connected_adapter.get_task("space-1", "nonexistent")

    def test_delete_task_success(self, connected_adapter: NotionAdapter) -> None:
        """Test delete_task archives the page."""
        connected_adapter._client.pages.update.return_value = {"archived": True}

        result = connected_adapter.delete_task("space-1", "page-123")

        assert result is True
        connected_adapter._client.pages.update.assert_called_once_with(
            page_id="page-123", archived=True
        )


class TestNotionAdapterJournal:
    """Test journal operations."""

    @pytest.fixture
    def connected_adapter(self) -> NotionAdapter:
        """Create a connected adapter with config."""
        config = create_notion_config()
        adapter = NotionAdapter(config)
        adapter._connected = True
        adapter._client = MagicMock()
        return adapter

    def test_create_journal_entry_not_connected(self) -> None:
        """Test create_journal_entry raises when not connected."""
        config = create_notion_config()
        adapter = NotionAdapter(config)
        with pytest.raises(ConnectionError):
            adapter.create_journal_entry("space-1", "Today was great")

    def test_create_journal_entry_success(self, connected_adapter: NotionAdapter) -> None:
        """Test create_journal_entry returns JournalEntry model."""
        mock_response = {
            "id": "page-journal-1",
            "created_time": "2025-01-25T10:00:00.000Z",
            "last_edited_time": "2025-01-25T10:00:00.000Z",
            "properties": {
                "Name": {"title": [{"plain_text": "Morning thoughts"}]},
                "Date": {"date": {"start": "2025-01-25"}},
            },
        }

        connected_adapter._client.pages.create.return_value = mock_response

        entry = connected_adapter.create_journal_entry(
            space_id="space-1",
            content="Today was productive.",
            title="Morning thoughts",
            entry_date=date(2025, 1, 25),
        )

        assert entry.id == "page-journal-1"
        assert entry.title == "Morning thoughts"
        assert entry.entry_date == date(2025, 1, 25)
        assert entry.content == "Today was productive."

    def test_get_journal_entries_negative_offset(
        self, connected_adapter: NotionAdapter
    ) -> None:
        """Test get_journal_entries rejects negative offset."""
        with pytest.raises(ValidationError):
            connected_adapter.get_journal_entries("space-1", offset=-1)

    def test_search_journal_negative_offset(self, connected_adapter: NotionAdapter) -> None:
        """Test search_journal rejects negative offset."""
        with pytest.raises(ValidationError):
            connected_adapter.search_journal("space-1", "query", offset=-1)


class TestNotionAdapterTags:
    """Test tag operations."""

    @pytest.fixture
    def connected_adapter(self) -> NotionAdapter:
        """Create a connected adapter with config."""
        config = create_notion_config()
        adapter = NotionAdapter(config)
        adapter._connected = True
        adapter._client = MagicMock()
        return adapter

    def test_list_tags_not_connected(self) -> None:
        """Test list_tags raises when not connected."""
        config = create_notion_config()
        adapter = NotionAdapter(config)
        with pytest.raises(ConnectionError):
            adapter.list_tags("space-1")

    def test_list_tags_success(self, connected_adapter: NotionAdapter) -> None:
        """Test list_tags returns tags from database schema."""
        mock_response = {
            "properties": {
                "Tags": {
                    "type": "multi_select",
                    "multi_select": {
                        "options": [
                            {"id": "tag-1", "name": "work", "color": "blue"},
                            {"id": "tag-2", "name": "personal", "color": "green"},
                        ]
                    },
                }
            }
        }

        connected_adapter._client.databases.retrieve.return_value = mock_response

        tags = connected_adapter.list_tags("space-1")

        assert len(tags) == 2
        assert tags[0].name == "work"
        assert tags[0].color == "blue"
        assert tags[1].name == "personal"

    def test_create_tag_returns_tag(self, connected_adapter: NotionAdapter) -> None:
        """Test create_tag returns Tag object."""
        # Notion creates tags automatically, so this just returns a Tag
        tag = connected_adapter.create_tag("space-1", "new-tag", "red")

        assert tag.name == "new-tag"
        assert tag.color == "red"
        assert tag.id == "new-tag"


class TestNotionAdapterErrorHandling:
    """Test API error handling."""

    @pytest.fixture
    def connected_adapter(self) -> NotionAdapter:
        """Create a connected adapter with config."""
        config = create_notion_config()
        adapter = NotionAdapter(config)
        adapter._connected = True
        adapter._client = MagicMock()
        return adapter

    def test_handle_api_error_401(self, connected_adapter: NotionAdapter) -> None:
        """Test 401 error raises AuthError."""
        from notion_client.errors import APIErrorCode, APIResponseError

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.headers = {}
        error = APIResponseError(mock_response, "Unauthorized", APIErrorCode.Unauthorized)

        with pytest.raises(AuthError):
            connected_adapter._handle_api_error(error)

    def test_handle_api_error_404(self, connected_adapter: NotionAdapter) -> None:
        """Test 404 error raises NotFoundError."""
        from notion_client.errors import APIErrorCode, APIResponseError

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.headers = {}
        error = APIResponseError(mock_response, "Not found", APIErrorCode.ObjectNotFound)

        with pytest.raises(NotFoundError):
            connected_adapter._handle_api_error(error)

    def test_handle_api_error_429(self, connected_adapter: NotionAdapter) -> None:
        """Test 429 error raises RateLimitError."""
        from notion_client.errors import APIErrorCode, APIResponseError

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "30"}
        error = APIResponseError(mock_response, "Rate limited", APIErrorCode.RateLimited)

        with pytest.raises(RateLimitError) as exc_info:
            connected_adapter._handle_api_error(error)
        assert exc_info.value.retry_after == 30.0

    def test_handle_api_error_500(self, connected_adapter: NotionAdapter) -> None:
        """Test 500 error raises ConnectionError."""
        from notion_client.errors import APIErrorCode, APIResponseError

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.headers = {}
        error = APIResponseError(
            mock_response, "Server error", APIErrorCode.InternalServerError
        )

        with pytest.raises(ConnectionError):
            connected_adapter._handle_api_error(error)


class TestNotionAdapterWithConfig:
    """Test adapter with configuration."""

    def test_init_with_config(self) -> None:
        """Test adapter uses config correctly."""
        config = create_notion_config()
        adapter = NotionAdapter(config)

        assert adapter._config == config
        assert adapter._config.backends.notion is not None
        assert adapter._config.backends.notion.workspace_id == "ws-123"

    def test_init_without_config(self) -> None:
        """Test adapter works without config."""
        adapter = NotionAdapter()
        assert adapter._config is None
        assert adapter.is_connected() is False
