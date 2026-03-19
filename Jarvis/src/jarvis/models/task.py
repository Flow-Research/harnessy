"""Task model representing a task in any backend."""

from datetime import date, datetime

from pydantic import BaseModel, Field, computed_field, field_validator

from .priority import Priority


class Task(BaseModel):
    """Represents a task in any backend.

    Provides a unified task model that works across AnyType, Notion,
    and other backends with consistent fields and validation.
    """

    id: str = Field(description="Backend-specific task identifier")
    space_id: str = Field(description="Space this task belongs to")
    title: str = Field(min_length=1, max_length=500, description="Task title/name")
    description: str | None = Field(default=None, max_length=10000, description="Task description")
    due_date: date | None = Field(default=None, description="Due date")
    priority: Priority | None = Field(default=None, description="Priority level")
    tags: list[str] = Field(default_factory=list, description="Tag names")
    is_done: bool = Field(default=False, description="Completion status")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last modification timestamp")

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        """Validate tag list constraints."""
        if len(v) > 50:
            raise ValueError("Maximum 50 tags allowed")
        for tag in v:
            if len(tag) > 100:
                raise ValueError(f"Tag '{tag[:20]}...' exceeds 100 characters")
        return v

    # Computed properties for backward compatibility with existing code
    @computed_field
    @property
    def name(self) -> str:
        """Alias for title (backward compatibility)."""
        return self.title

    @computed_field
    @property
    def scheduled_date(self) -> date | None:
        """Alias for due_date (backward compatibility with existing code)."""
        return self.due_date

    @computed_field
    @property
    def is_moveable(self) -> bool:
        """Task can be rescheduled if not tagged bar_movement."""
        return "bar_movement" not in self.tags

    @computed_field
    @property
    def has_deadline(self) -> bool:
        """Check if task has a due date."""
        return self.due_date is not None
