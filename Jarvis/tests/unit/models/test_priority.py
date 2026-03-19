"""Tests for Priority enum."""

import pytest

from jarvis.models.priority import Priority


class TestPriority:
    """Test cases for Priority enum."""

    def test_priority_values(self) -> None:
        """Test all priority values exist."""
        assert Priority.HIGH.value == "high"
        assert Priority.MEDIUM.value == "medium"
        assert Priority.LOW.value == "low"

    def test_priority_is_string_enum(self) -> None:
        """Test Priority extends str for JSON compatibility."""
        assert isinstance(Priority.HIGH, str)
        assert str(Priority.HIGH) == "high"

    def test_from_string_valid_lowercase(self) -> None:
        """Test from_string with lowercase input."""
        assert Priority.from_string("high") == Priority.HIGH
        assert Priority.from_string("medium") == Priority.MEDIUM
        assert Priority.from_string("low") == Priority.LOW

    def test_from_string_valid_uppercase(self) -> None:
        """Test from_string with uppercase input."""
        assert Priority.from_string("HIGH") == Priority.HIGH
        assert Priority.from_string("MEDIUM") == Priority.MEDIUM
        assert Priority.from_string("LOW") == Priority.LOW

    def test_from_string_valid_mixed_case(self) -> None:
        """Test from_string with mixed case input."""
        assert Priority.from_string("High") == Priority.HIGH
        assert Priority.from_string("MeDiUm") == Priority.MEDIUM
        assert Priority.from_string("LoW") == Priority.LOW

    def test_from_string_none_returns_none(self) -> None:
        """Test from_string returns None for None input."""
        assert Priority.from_string(None) is None

    def test_from_string_invalid_returns_none(self) -> None:
        """Test from_string returns None for invalid input."""
        assert Priority.from_string("invalid") is None
        assert Priority.from_string("") is None
        assert Priority.from_string("urgent") is None
        assert Priority.from_string("123") is None

    def test_priority_iteration(self) -> None:
        """Test all priorities can be iterated."""
        priorities = list(Priority)
        assert len(priorities) == 3
        assert Priority.HIGH in priorities
        assert Priority.MEDIUM in priorities
        assert Priority.LOW in priorities

    def test_priority_str_representation(self) -> None:
        """Test string representation."""
        assert str(Priority.HIGH) == "high"
        assert f"{Priority.MEDIUM}" == "medium"
