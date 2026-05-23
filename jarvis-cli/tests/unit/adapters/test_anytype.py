"""Tests for AnyTypeAdapter."""

from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from jarvis.adapters.anytype import AnyTypeAdapter
from jarvis.adapters.exceptions import (
    AuthError,
    ConnectionError,
    NotFoundError,
    ValidationError,
)
from jarvis.config.schema import AnyTypeConfig, BackendsConfig, JarvisConfig
from jarvis.models import BackendObject, Priority


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

    def test_get_default_space_from_config(self, connected_adapter: AnyTypeAdapter) -> None:
        """Test get_default_space uses config value."""
        connected_adapter._default_space_id = "configured-space"

        result = connected_adapter.get_default_space()
        assert result == "configured-space"

    def test_get_default_space_first_space(self, connected_adapter: AnyTypeAdapter) -> None:
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

    def test_set_default_space_not_found(self, connected_adapter: AnyTypeAdapter) -> None:
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

    def test_create_task_title_too_long(self, connected_adapter: AnyTypeAdapter) -> None:
        """Test create_task rejects too-long title."""
        with pytest.raises(ValidationError) as exc_info:
            connected_adapter.create_task("space-1", "x" * 501)
        assert "500" in str(exc_info.value)

    def test_create_task_success(self, connected_adapter: AnyTypeAdapter) -> None:
        """Test create_task returns Task model."""
        with patch.object(connected_adapter._client, "create_task", return_value="task-123"):
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

    def test_get_tasks_negative_offset(self, connected_adapter: AnyTypeAdapter) -> None:
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

    def test_get_journal_entries_negative_offset(self, connected_adapter: AnyTypeAdapter) -> None:
        """Test get_journal_entries rejects negative offset."""
        with pytest.raises(ValidationError):
            connected_adapter.get_journal_entries("space-1", offset=-1)

    def test_search_journal_negative_offset(self, connected_adapter: AnyTypeAdapter) -> None:
        """Test search_journal rejects negative offset."""
        with pytest.raises(ValidationError):
            connected_adapter.search_journal("space-1", "query", offset=-1)


class TestAnyTypeAdapterSyncOperations:
    """Test Anytype operations used by jarvis sync."""

    @pytest.fixture
    def connected_adapter(self) -> AnyTypeAdapter:
        """Create a connected adapter."""
        adapter = AnyTypeAdapter()
        adapter._client._authenticated = True
        return adapter

    def _fake_space(self) -> SimpleNamespace:
        def get_type_byname(name: str) -> SimpleNamespace:
            return SimpleNamespace(name=name, key=f"ot-{name.lower()}")

        def create_object(obj: object) -> SimpleNamespace:
            assert getattr(obj, "name")
            return SimpleNamespace(id="created-1")

        return SimpleNamespace(
            get_type_byname=get_type_byname,
            create_object=create_object,
        )

    def test_create_page_in_attaches_with_shared_collection_helper(
        self, connected_adapter: AnyTypeAdapter
    ) -> None:
        """Sync page creation should use the resilient AnyType list-link helper."""
        connected_adapter._client._client = SimpleNamespace(
            get_space=lambda _space_id: self._fake_space()
        )
        with (
            patch.object(
                connected_adapter._client, "_add_to_collection", return_value=True
            ) as add_to_collection,
            patch("anytype.Object") as object_cls,
        ):
            object_cls.side_effect = lambda name, type: SimpleNamespace(
                name=name, type=type, body=""
            )

            object_id = connected_adapter.create_page_in("space-1", "parent-1", "Page", "Body")

        assert object_id == "created-1"
        add_to_collection.assert_called_once_with("space-1", "parent-1", "created-1")

    def test_create_collection_in_fails_when_attachment_fails(
        self, connected_adapter: AnyTypeAdapter
    ) -> None:
        """A child Collection is not synced successfully unless it appears under parent."""
        connected_adapter._client._client = SimpleNamespace(
            get_space=lambda _space_id: self._fake_space()
        )
        with (
            patch.object(connected_adapter._client, "_add_to_collection", return_value=False),
            patch("anytype.Object") as object_cls,
        ):
            object_cls.side_effect = lambda name, type: SimpleNamespace(name=name, type=type)

            with pytest.raises(ConnectionError):
                connected_adapter.create_collection_in("space-1", "parent-1", "Child")

    def test_create_collection_in_reattaches_existing_exact_name_collection(
        self, connected_adapter: AnyTypeAdapter
    ) -> None:
        """Interrupted sync retries should reuse one exact-name orphan Collection."""
        type_collection = SimpleNamespace(name="Collection", key="ot-collection")
        existing = SimpleNamespace(id="existing-1", name="Child")
        fake_space = SimpleNamespace(
            get_type_byname=lambda _name: type_collection,
            get_object=lambda _object_id: (_ for _ in ()).throw(RuntimeError("not linked")),
            search=lambda **_kwargs: [existing],
            create_object=MagicMock(side_effect=AssertionError("should not create duplicate")),
        )
        connected_adapter._client._client = SimpleNamespace(get_space=lambda _space_id: fake_space)

        with patch.object(
            connected_adapter._client, "_add_to_collection", return_value=True
        ) as add_to_collection:
            object_id = connected_adapter.create_collection_in("space-1", "parent-1", "Child")

        assert object_id == "existing-1"
        add_to_collection.assert_called_once_with("space-1", "parent-1", "existing-1")

    def test_delete_object_delegates_to_client(self, connected_adapter: AnyTypeAdapter) -> None:
        """Sync prune deletes through the shared Anytype client."""
        with patch.object(
            connected_adapter._client, "delete_object", return_value=True
        ) as delete_object:
            result = connected_adapter.delete_object("space-1", "obj-1")

        assert result is True
        delete_object.assert_called_once_with("space-1", "obj-1")

    def test_upload_file_in_uploads_and_attaches(
        self, connected_adapter: AnyTypeAdapter, tmp_path: Path
    ) -> None:
        """Native file sync should upload through Files API and link to Collection."""
        source = tmp_path / "image.png"
        source.write_bytes(b"\x89PNG\r\n")
        with (
            patch.object(
                connected_adapter._client, "upload_file", return_value="file-1"
            ) as upload_file,
            patch.object(
                connected_adapter._client, "_add_to_collection", return_value=True
            ) as add_to_collection,
        ):
            result = connected_adapter.upload_file_in("space-1", "parent-1", source)

        assert result == "file-1"
        upload_file.assert_called_once_with("space-1", source)
        add_to_collection.assert_called_once_with("space-1", "parent-1", "file-1")

    def test_update_page_content_uses_markdown_update_api(
        self, connected_adapter: AnyTypeAdapter
    ) -> None:
        """Folder sync page updates should use the markdown-capable object API."""
        api = SimpleNamespace(headers={"Anytype-Version": "old"}, updateObject=MagicMock())
        fake_space = SimpleNamespace(get_object=lambda _object_id: SimpleNamespace(name="Page"))
        connected_adapter._client._client = SimpleNamespace(
            get_space=lambda _space_id: fake_space,
            _apiEndpoints=api,
        )

        connected_adapter.update_page_content("space-1", "page-1", "# Body")

        api.updateObject.assert_called_once_with(
            "space-1",
            "page-1",
            {"name": "Page", "markdown": "# Body"},
        )
        assert api.headers["Anytype-Version"] == "old"

    def test_delete_file_delegates_to_client(self, connected_adapter: AnyTypeAdapter) -> None:
        """Sync prune deletes native file objects via the Files API."""
        with patch.object(
            connected_adapter._client, "delete_file", return_value=True
        ) as delete_file:
            result = connected_adapter.delete_file("space-1", "file-1")

        assert result is True
        delete_file.assert_called_once_with("space-1", "file-1")

    def test_delete_object_not_connected(self) -> None:
        """Sync prune delete raises when not connected."""
        adapter = AnyTypeAdapter()
        with pytest.raises(ConnectionError):
            adapter.delete_object("space-1", "obj-1")

    def test_validate_collection_accepts_collection(
        self, connected_adapter: AnyTypeAdapter
    ) -> None:
        """Collection destinations are valid sync roots."""
        obj = BackendObject(
            id="obj-1",
            space_id="space-1",
            name="Sync Root",
            object_type="Collection",
            type_key="ot-collection",
            backend="anytype",
        )
        with patch.object(connected_adapter, "get_object", return_value=obj):
            connected_adapter.validate_collection("space-1", "obj-1")

    def test_validate_collection_rejects_page(self, connected_adapter: AnyTypeAdapter) -> None:
        """Non-Collection destinations are rejected before sync writes."""
        obj = BackendObject(
            id="obj-1",
            space_id="space-1",
            name="Not a folder",
            object_type="Page",
            type_key="ot-page",
            backend="anytype",
        )
        with patch.object(connected_adapter, "get_object", return_value=obj):
            with pytest.raises(ValidationError):
                connected_adapter.validate_collection("space-1", "obj-1")


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
            backends=BackendsConfig(anytype=AnyTypeConfig(default_space_id="my-space"))
        )
        adapter = AnyTypeAdapter(config)

        assert adapter._default_space_id == "my-space"

    def test_init_without_config(self) -> None:
        """Test adapter works without config."""
        adapter = AnyTypeAdapter()
        assert adapter._default_space_id is None
