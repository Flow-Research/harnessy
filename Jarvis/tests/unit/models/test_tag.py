"""Tests for Tag model."""

import pytest
from pydantic import ValidationError

from jarvis.models.tag import Tag


class TestTag:
    """Test cases for Tag model."""

    def test_create_tag_with_all_fields(self) -> None:
        """Test basic tag creation with all fields."""
        tag = Tag(id="tag-123", name="urgent", color="#ff0000")
        assert tag.id == "tag-123"
        assert tag.name == "urgent"
        assert tag.color == "#ff0000"

    def test_create_tag_without_color(self) -> None:
        """Test tag creation without optional color."""
        tag = Tag(id="tag-123", name="work")
        assert tag.id == "tag-123"
        assert tag.name == "work"
        assert tag.color is None

    def test_tag_is_immutable(self) -> None:
        """Test that Tag model is frozen (immutable)."""
        tag = Tag(id="tag-123", name="urgent")
        with pytest.raises(ValidationError):
            tag.name = "changed"  # type: ignore[misc]

    def test_tag_required_fields(self) -> None:
        """Test that id and name are required."""
        with pytest.raises(ValidationError):
            Tag(id="tag-123")  # type: ignore[call-arg]

        with pytest.raises(ValidationError):
            Tag(name="urgent")  # type: ignore[call-arg]

    def test_tag_equality(self) -> None:
        """Test Tag equality comparison."""
        tag1 = Tag(id="tag-123", name="urgent", color="#ff0000")
        tag2 = Tag(id="tag-123", name="urgent", color="#ff0000")
        tag3 = Tag(id="tag-456", name="urgent", color="#ff0000")

        assert tag1 == tag2
        assert tag1 != tag3

    def test_tag_hashable(self) -> None:
        """Test Tag can be used in sets and as dict keys."""
        tag = Tag(id="tag-123", name="urgent")
        tag_set = {tag}
        assert tag in tag_set

    def test_tag_serialization(self) -> None:
        """Test Tag can be serialized to dict/JSON."""
        tag = Tag(id="tag-123", name="urgent", color="#ff0000")
        data = tag.model_dump()

        assert data == {
            "id": "tag-123",
            "name": "urgent",
            "color": "#ff0000",
        }

    def test_tag_serialization_without_color(self) -> None:
        """Test Tag serialization when color is None."""
        tag = Tag(id="tag-123", name="work")
        data = tag.model_dump()

        assert data == {
            "id": "tag-123",
            "name": "work",
            "color": None,
        }
