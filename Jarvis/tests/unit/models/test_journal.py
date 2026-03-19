"""Tests for JournalEntry model."""

from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from jarvis.models.journal import JournalEntry


class TestJournalEntry:
    """Test cases for JournalEntry model."""

    @pytest.fixture
    def sample_entry(self) -> JournalEntry:
        """Create a sample journal entry for testing."""
        return JournalEntry(
            id="entry-123",
            space_id="space-456",
            title="Daily Reflection",
            content="Today was a productive day. I completed the backend abstraction.",
            entry_date=date(2024, 3, 15),
            tags=["reflection", "work"],
            created_at=datetime(2024, 3, 15, 20, 0, 0, tzinfo=timezone.utc),
            path="Journal/2024/March",
        )

    def test_create_entry_with_all_fields(self, sample_entry: JournalEntry) -> None:
        """Test entry creation with all fields."""
        assert sample_entry.id == "entry-123"
        assert sample_entry.space_id == "space-456"
        assert sample_entry.title == "Daily Reflection"
        assert "productive" in sample_entry.content
        assert sample_entry.entry_date == date(2024, 3, 15)
        assert sample_entry.tags == ["reflection", "work"]
        assert sample_entry.path == "Journal/2024/March"

    def test_create_entry_minimal_fields(self) -> None:
        """Test entry creation with only required fields."""
        now = datetime.now(tz=timezone.utc)
        entry = JournalEntry(
            id="entry-123",
            space_id="space-456",
            title="Simple Entry",
            entry_date=date(2024, 3, 15),
            created_at=now,
        )
        assert entry.id == "entry-123"
        assert entry.content == ""
        assert entry.tags == []
        assert entry.path is None

    def test_computed_field_day_prefix(self, sample_entry: JournalEntry) -> None:
        """Test day_prefix computed field."""
        assert sample_entry.day_prefix == "15"

    def test_day_prefix_single_digit(self) -> None:
        """Test day_prefix for single digit days."""
        now = datetime.now(tz=timezone.utc)
        entry = JournalEntry(
            id="entry-123",
            space_id="space-456",
            title="Entry",
            entry_date=date(2024, 3, 5),
            created_at=now,
        )
        assert entry.day_prefix == "5"

    def test_title_validation_empty(self) -> None:
        """Test title cannot be empty."""
        now = datetime.now(tz=timezone.utc)
        with pytest.raises(ValidationError) as exc_info:
            JournalEntry(
                id="entry-123",
                space_id="space-456",
                title="",
                entry_date=date(2024, 3, 15),
                created_at=now,
            )
        assert "title" in str(exc_info.value)

    def test_title_validation_too_long(self) -> None:
        """Test title cannot exceed 500 characters."""
        now = datetime.now(tz=timezone.utc)
        with pytest.raises(ValidationError) as exc_info:
            JournalEntry(
                id="entry-123",
                space_id="space-456",
                title="x" * 501,
                entry_date=date(2024, 3, 15),
                created_at=now,
            )
        assert "title" in str(exc_info.value)

    def test_content_validation_too_long(self) -> None:
        """Test content cannot exceed 100000 characters."""
        now = datetime.now(tz=timezone.utc)
        with pytest.raises(ValidationError) as exc_info:
            JournalEntry(
                id="entry-123",
                space_id="space-456",
                title="Valid title",
                content="x" * 100001,
                entry_date=date(2024, 3, 15),
                created_at=now,
            )
        assert "content" in str(exc_info.value)

    def test_tags_validation_too_many(self) -> None:
        """Test cannot have more than 50 tags."""
        now = datetime.now(tz=timezone.utc)
        with pytest.raises(ValidationError) as exc_info:
            JournalEntry(
                id="entry-123",
                space_id="space-456",
                title="Valid title",
                entry_date=date(2024, 3, 15),
                tags=[f"tag{i}" for i in range(51)],
                created_at=now,
            )
        assert "50" in str(exc_info.value)

    def test_tags_validation_tag_too_long(self) -> None:
        """Test individual tag cannot exceed 100 characters."""
        now = datetime.now(tz=timezone.utc)
        with pytest.raises(ValidationError) as exc_info:
            JournalEntry(
                id="entry-123",
                space_id="space-456",
                title="Valid title",
                entry_date=date(2024, 3, 15),
                tags=["x" * 101],
                created_at=now,
            )
        assert "100 characters" in str(exc_info.value)

    def test_entry_serialization(self, sample_entry: JournalEntry) -> None:
        """Test JournalEntry can be serialized to dict."""
        data = sample_entry.model_dump()
        assert data["id"] == "entry-123"
        assert data["title"] == "Daily Reflection"
        assert data["entry_date"] == date(2024, 3, 15)
        # Computed field should be included
        assert data["day_prefix"] == "15"

    def test_entry_required_fields(self) -> None:
        """Test that required fields are enforced."""
        now = datetime.now(tz=timezone.utc)
        with pytest.raises(ValidationError):
            JournalEntry(
                space_id="space-456",
                title="No ID",
                entry_date=date(2024, 3, 15),
                created_at=now,
            )  # type: ignore[call-arg]

    def test_path_optional_for_flat_backends(self) -> None:
        """Test path is optional for backends without hierarchy."""
        now = datetime.now(tz=timezone.utc)
        entry = JournalEntry(
            id="entry-123",
            space_id="space-456",
            title="Notion Entry",
            entry_date=date(2024, 3, 15),
            created_at=now,
            path=None,  # Notion doesn't have hierarchy
        )
        assert entry.path is None

    def test_markdown_content(self) -> None:
        """Test entry can contain markdown content."""
        now = datetime.now(tz=timezone.utc)
        markdown_content = """
# Daily Notes

## Tasks Completed
- [x] Task 1
- [x] Task 2

## Learnings
**Important**: This is a key insight.

```python
def hello():
    print("Hello, World!")
```
"""
        entry = JournalEntry(
            id="entry-123",
            space_id="space-456",
            title="Markdown Entry",
            content=markdown_content,
            entry_date=date(2024, 3, 15),
            created_at=now,
        )
        assert "# Daily Notes" in entry.content
        assert "```python" in entry.content
