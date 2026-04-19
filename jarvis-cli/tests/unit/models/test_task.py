"""Tests for Task model."""

from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from jarvis.models.priority import Priority
from jarvis.models.task import Task


class TestTask:
    """Test cases for Task model."""

    @pytest.fixture
    def sample_task(self) -> Task:
        """Create a sample task for testing."""
        return Task(
            id="task-123",
            space_id="space-456",
            title="Complete project",
            description="Finish the backend abstraction",
            due_date=date(2024, 3, 15),
            priority=Priority.HIGH,
            tags=["work", "urgent"],
            is_done=False,
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
        )

    def test_create_task_with_all_fields(self, sample_task: Task) -> None:
        """Test task creation with all fields."""
        assert sample_task.id == "task-123"
        assert sample_task.space_id == "space-456"
        assert sample_task.title == "Complete project"
        assert sample_task.description == "Finish the backend abstraction"
        assert sample_task.due_date == date(2024, 3, 15)
        assert sample_task.priority == Priority.HIGH
        assert sample_task.tags == ["work", "urgent"]
        assert sample_task.is_done is False

    def test_create_task_minimal_fields(self) -> None:
        """Test task creation with only required fields."""
        now = datetime.now(tz=timezone.utc)
        task = Task(
            id="task-123",
            space_id="space-456",
            title="Simple task",
            created_at=now,
            updated_at=now,
        )
        assert task.id == "task-123"
        assert task.description is None
        assert task.due_date is None
        assert task.priority is None
        assert task.tags == []
        assert task.is_done is False

    def test_computed_field_name(self, sample_task: Task) -> None:
        """Test name computed field (backward compatibility)."""
        assert sample_task.name == sample_task.title
        assert sample_task.name == "Complete project"

    def test_computed_field_scheduled_date(self, sample_task: Task) -> None:
        """Test scheduled_date computed field (backward compatibility)."""
        assert sample_task.scheduled_date == sample_task.due_date
        assert sample_task.scheduled_date == date(2024, 3, 15)

    def test_computed_field_is_moveable_true(self, sample_task: Task) -> None:
        """Test is_moveable returns True when bar_movement not in tags."""
        assert sample_task.is_moveable is True

    def test_computed_field_is_moveable_false(self) -> None:
        """Test is_moveable returns False when bar_movement in tags."""
        now = datetime.now(tz=timezone.utc)
        task = Task(
            id="task-123",
            space_id="space-456",
            title="Fixed task",
            tags=["bar_movement", "important"],
            created_at=now,
            updated_at=now,
        )
        assert task.is_moveable is False

    def test_title_validation_empty(self) -> None:
        """Test title cannot be empty."""
        now = datetime.now(tz=timezone.utc)
        with pytest.raises(ValidationError) as exc_info:
            Task(
                id="task-123",
                space_id="space-456",
                title="",
                created_at=now,
                updated_at=now,
            )
        assert "title" in str(exc_info.value)

    def test_title_validation_too_long(self) -> None:
        """Test title cannot exceed 500 characters."""
        now = datetime.now(tz=timezone.utc)
        with pytest.raises(ValidationError) as exc_info:
            Task(
                id="task-123",
                space_id="space-456",
                title="x" * 501,
                created_at=now,
                updated_at=now,
            )
        assert "title" in str(exc_info.value)

    def test_description_validation_too_long(self) -> None:
        """Test description cannot exceed 10000 characters."""
        now = datetime.now(tz=timezone.utc)
        with pytest.raises(ValidationError) as exc_info:
            Task(
                id="task-123",
                space_id="space-456",
                title="Valid title",
                description="x" * 10001,
                created_at=now,
                updated_at=now,
            )
        assert "description" in str(exc_info.value)

    def test_tags_validation_too_many(self) -> None:
        """Test cannot have more than 50 tags."""
        now = datetime.now(tz=timezone.utc)
        with pytest.raises(ValidationError) as exc_info:
            Task(
                id="task-123",
                space_id="space-456",
                title="Valid title",
                tags=[f"tag{i}" for i in range(51)],
                created_at=now,
                updated_at=now,
            )
        assert "50" in str(exc_info.value)

    def test_tags_validation_tag_too_long(self) -> None:
        """Test individual tag cannot exceed 100 characters."""
        now = datetime.now(tz=timezone.utc)
        with pytest.raises(ValidationError) as exc_info:
            Task(
                id="task-123",
                space_id="space-456",
                title="Valid title",
                tags=["x" * 101],
                created_at=now,
                updated_at=now,
            )
        assert "100 characters" in str(exc_info.value)

    def test_task_serialization(self, sample_task: Task) -> None:
        """Test Task can be serialized to dict."""
        data = sample_task.model_dump()
        assert data["id"] == "task-123"
        assert data["title"] == "Complete project"
        assert data["priority"] == "high"
        # Computed fields should also be included
        assert data["name"] == "Complete project"
        assert data["is_moveable"] is True

    def test_task_required_fields(self) -> None:
        """Test that required fields are enforced."""
        with pytest.raises(ValidationError):
            Task(space_id="space-456", title="No ID")  # type: ignore[call-arg]

    def test_task_with_priority_enum(self) -> None:
        """Test task works with Priority enum values."""
        now = datetime.now(tz=timezone.utc)
        for priority in Priority:
            task = Task(
                id="task-123",
                space_id="space-456",
                title="Test task",
                priority=priority,
                created_at=now,
                updated_at=now,
            )
            assert task.priority == priority
