"""Tag model representing a categorization label."""

from pydantic import BaseModel, Field


class Tag(BaseModel):
    """Represents a categorization tag.

    Tags are used to categorize tasks and journal entries
    across all backend types.
    """

    id: str = Field(description="Backend-specific tag identifier")
    name: str = Field(description="Tag display name")
    color: str | None = Field(default=None, description="Optional color code")

    model_config = {"frozen": True}  # Immutable
