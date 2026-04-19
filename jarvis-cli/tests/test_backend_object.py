"""Tests for BackendObject model and object CLI ID parsing."""

from datetime import datetime

import pytest

from jarvis.models import BackendObject, ObjectProperty, PropertyFormat
from jarvis.object.cli import parse_object_id


class TestBackendObject:
    """Tests for the BackendObject model."""

    def test_basic_creation(self) -> None:
        """Test creating a BackendObject with minimal fields."""
        obj = BackendObject(id="obj_1", space_id="space_1")
        assert obj.id == "obj_1"
        assert obj.space_id == "space_1"
        assert obj.name == "Untitled"
        assert obj.object_type == "Unknown"
        assert obj.properties == []

    def test_full_creation(self) -> None:
        """Test creating a BackendObject with all fields."""
        now = datetime.now()
        obj = BackendObject(
            id="obj_1",
            space_id="space_1",
            name="My Task",
            object_type="Task",
            type_key="ot-task",
            icon="📋",
            description="A task description",
            content="Full markdown content",
            properties=[
                ObjectProperty(
                    key="due_date",
                    name="Due date",
                    format=PropertyFormat.DATE,
                    value="2026-03-20T00:00:00Z",
                ),
                ObjectProperty(
                    key="priority",
                    name="Priority",
                    format=PropertyFormat.NUMBER,
                    value=1,
                ),
                ObjectProperty(
                    key="created_date",
                    name="Created date",
                    format=PropertyFormat.DATE,
                    value="2026-01-01T00:00:00Z",
                    is_system=True,
                ),
            ],
            created_at=now,
            updated_at=now,
            backend="anytype",
        )
        assert obj.name == "My Task"
        assert obj.object_type == "Task"
        assert obj.icon == "📋"
        assert len(obj.properties) == 3

    def test_get_property(self) -> None:
        """Test looking up a property by key."""
        obj = BackendObject(
            id="obj_1",
            space_id="space_1",
            properties=[
                ObjectProperty(key="due_date", format=PropertyFormat.DATE, value="2026-03-20"),
                ObjectProperty(key="priority", format=PropertyFormat.NUMBER, value=1),
            ],
        )
        prop = obj.get_property("due_date")
        assert prop is not None
        assert prop.key == "due_date"
        assert prop.value == "2026-03-20"

        missing = obj.get_property("nonexistent")
        assert missing is None

    def test_get_editable_properties(self) -> None:
        """Test filtering editable vs system properties."""
        obj = BackendObject(
            id="obj_1",
            space_id="space_1",
            properties=[
                ObjectProperty(key="due_date", format=PropertyFormat.DATE, value="2026-03-20"),
                ObjectProperty(key="priority", format=PropertyFormat.NUMBER, value=1),
                ObjectProperty(
                    key="created_date",
                    format=PropertyFormat.DATE,
                    value="2026-01-01",
                    is_system=True,
                ),
                ObjectProperty(
                    key="last_modified_date",
                    format=PropertyFormat.DATE,
                    value="2026-03-15",
                    is_system=True,
                ),
            ],
        )
        editable = obj.get_editable_properties()
        assert len(editable) == 2
        assert all(not p.is_system for p in editable)
        assert {p.key for p in editable} == {"due_date", "priority"}

    def test_type_display(self) -> None:
        """Test type_display property for known types."""
        task = BackendObject(id="1", space_id="s", object_type="Task")
        assert "Task" in task.type_display
        assert "[ ]" in task.type_display

        page = BackendObject(id="1", space_id="s", object_type="Page")
        assert "Page" in page.type_display
        assert "#" in page.type_display

        collection = BackendObject(id="1", space_id="s", object_type="Collection")
        assert "Collection" in collection.type_display


class TestObjectProperty:
    """Tests for ObjectProperty model."""

    def test_display_value_text(self) -> None:
        """Test display_value for text properties."""
        prop = ObjectProperty(key="title", format=PropertyFormat.TEXT, value="Hello World")
        assert prop.display_value == "Hello World"

    def test_display_value_none(self) -> None:
        """Test display_value when value is None."""
        prop = ObjectProperty(key="title", format=PropertyFormat.TEXT, value=None)
        assert prop.display_value == ""

    def test_display_value_checkbox(self) -> None:
        """Test display_value for checkbox properties."""
        checked = ObjectProperty(key="done", format=PropertyFormat.CHECKBOX, value=True)
        assert checked.display_value == "Yes"

        unchecked = ObjectProperty(key="done", format=PropertyFormat.CHECKBOX, value=False)
        assert unchecked.display_value == "No"

    def test_display_value_multi_select(self) -> None:
        """Test display_value for multi-select properties."""
        prop = ObjectProperty(
            key="tags",
            format=PropertyFormat.MULTI_SELECT,
            value=["work", "urgent", "frontend"],
        )
        assert prop.display_value == "work, urgent, frontend"

    def test_display_value_date_trims_timezone(self) -> None:
        """Test display_value for dates trims T00:00:00Z suffix."""
        prop = ObjectProperty(
            key="due_date",
            format=PropertyFormat.DATE,
            value="2026-03-20T00:00:00Z",
        )
        assert prop.display_value == "2026-03-20"

    def test_display_value_date_preserves_time(self) -> None:
        """Test display_value preserves meaningful time info."""
        prop = ObjectProperty(
            key="due_date",
            format=PropertyFormat.DATE,
            value="2026-03-20T14:30:00Z",
        )
        assert prop.display_value == "2026-03-20T14:30:00Z"

    def test_display_value_number(self) -> None:
        """Test display_value for numbers."""
        prop = ObjectProperty(key="priority", format=PropertyFormat.NUMBER, value=42)
        assert prop.display_value == "42"


class TestParseObjectId:
    """Tests for the parse_object_id helper."""

    def test_raw_anytype_cid(self) -> None:
        """Test parsing a raw AnyType CID (bafyrei...)."""
        cid = "bafyreig5fk7tqzc5f5e5rqv5u5xyjz5f5e5rqv5u5xyjz5f5e5rqv5u5xyz"
        assert parse_object_id(cid) == cid

    def test_notion_uuid_with_dashes(self) -> None:
        """Test parsing a Notion UUID with dashes."""
        uuid = "12345678-abcd-ef01-2345-67890abcdef0"
        assert parse_object_id(uuid) == uuid

    def test_notion_uuid_without_dashes(self) -> None:
        """Test parsing a 32-char hex string."""
        hex_id = "12345678abcdef0123456789abcdef01"
        assert parse_object_id(hex_id) == hex_id

    def test_notion_url_with_title(self) -> None:
        """Test parsing a Notion URL with page title slug."""
        url = "https://www.notion.so/workspace/My-Page-Title-12345678abcdef0123456789abcdef01"
        assert parse_object_id(url) == "12345678abcdef0123456789abcdef01"

    def test_notion_url_without_title(self) -> None:
        """Test parsing a Notion URL without title slug."""
        url = "https://notion.so/12345678abcdef0123456789abcdef01"
        assert parse_object_id(url) == "12345678abcdef0123456789abcdef01"

    def test_notion_url_with_query_params(self) -> None:
        """Test parsing a Notion URL with query parameters."""
        url = "https://www.notion.so/workspace/Page-12345678abcdef0123456789abcdef01?v=abc"
        assert parse_object_id(url) == "12345678abcdef0123456789abcdef01"

    def test_anytype_deeplink(self) -> None:
        """Test parsing an AnyType deeplink."""
        link = "anytype://object/bafyreig5fk7tqzc5f5e5rqv5u5xyjz"
        assert parse_object_id(link) == "bafyreig5fk7tqzc5f5e5rqv5u5xyjz"

    def test_whitespace_stripped(self) -> None:
        """Test that whitespace is stripped from input."""
        assert parse_object_id("  some-id  ") == "some-id"

    def test_unknown_format_passthrough(self) -> None:
        """Test that unrecognized formats are passed through as-is."""
        weird_id = "custom-backend-id-12345"
        assert parse_object_id(weird_id) == weird_id

    def test_empty_string(self) -> None:
        """Test empty string returns empty."""
        assert parse_object_id("") == ""
