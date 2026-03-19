"""Tests for Space model."""

import pytest
from pydantic import ValidationError

from jarvis.models.space import Space


class TestSpace:
    """Test cases for Space model."""

    def test_create_space(self) -> None:
        """Test basic space creation."""
        space = Space(id="space-123", name="My Workspace", backend="anytype")
        assert space.id == "space-123"
        assert space.name == "My Workspace"
        assert space.backend == "anytype"

    def test_space_is_immutable(self) -> None:
        """Test that Space model is frozen (immutable)."""
        space = Space(id="space-123", name="My Workspace", backend="anytype")
        with pytest.raises(ValidationError):
            space.name = "Changed Name"  # type: ignore[misc]

    def test_space_with_different_backends(self) -> None:
        """Test Space works with various backend types."""
        anytype = Space(id="at-1", name="AnyType Space", backend="anytype")
        notion = Space(id="notion-ws-1", name="Notion Workspace", backend="notion")

        assert anytype.backend == "anytype"
        assert notion.backend == "notion"

    def test_space_required_fields(self) -> None:
        """Test that all fields are required."""
        with pytest.raises(ValidationError):
            Space(id="space-123", name="My Workspace")  # type: ignore[call-arg]

        with pytest.raises(ValidationError):
            Space(id="space-123", backend="anytype")  # type: ignore[call-arg]

        with pytest.raises(ValidationError):
            Space(name="My Workspace", backend="anytype")  # type: ignore[call-arg]

    def test_space_equality(self) -> None:
        """Test Space equality comparison."""
        space1 = Space(id="space-123", name="My Workspace", backend="anytype")
        space2 = Space(id="space-123", name="My Workspace", backend="anytype")
        space3 = Space(id="space-456", name="My Workspace", backend="anytype")

        assert space1 == space2
        assert space1 != space3

    def test_space_hashable(self) -> None:
        """Test Space can be used in sets and as dict keys."""
        space = Space(id="space-123", name="My Workspace", backend="anytype")
        space_set = {space}
        assert space in space_set

        space_dict = {space: "value"}
        assert space_dict[space] == "value"

    def test_space_serialization(self) -> None:
        """Test Space can be serialized to dict/JSON."""
        space = Space(id="space-123", name="My Workspace", backend="anytype")
        data = space.model_dump()

        assert data == {
            "id": "space-123",
            "name": "My Workspace",
            "backend": "anytype",
        }
