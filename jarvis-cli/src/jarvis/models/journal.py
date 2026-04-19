"""JournalEntry model representing a journal entry in any backend."""

from datetime import date, datetime

from pydantic import BaseModel, Field, computed_field, field_validator


class JournalEntry(BaseModel):
    """Represents a journal entry in any backend.

    Provides a unified journal entry model that works across AnyType, Notion,
    and other backends with consistent fields and validation.
    """

    id: str = Field(description="Backend-specific entry identifier")
    space_id: str = Field(description="Space this entry belongs to")
    title: str = Field(min_length=1, max_length=500, description="Entry title")
    content: str = Field(default="", max_length=100000, description="Entry content (markdown)")
    entry_date: date = Field(description="Date of the journal entry")
    tags: list[str] = Field(default_factory=list, description="Associated tags")
    created_at: datetime = Field(description="Creation timestamp")

    # Optional: Path for hierarchical backends (AnyType)
    path: str | None = Field(
        default=None, description="Hierarchical path if applicable (e.g., Journal/2024/January)"
    )

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

    @computed_field
    @property
    def day_prefix(self) -> str:
        """Day number for title prefix."""
        return str(self.entry_date.day)
