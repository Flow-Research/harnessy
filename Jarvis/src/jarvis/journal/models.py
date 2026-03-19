"""Domain models for Jarvis Journal."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, computed_field

# Constants
CONTENT_PREVIEW_LENGTH = 200


class JournalEntry(BaseModel):
    """Represents a journal entry stored in AnyType."""

    id: str = Field(description="AnyType object ID")
    space_id: str = Field(description="AnyType space ID")
    title: str = Field(description="AI-generated or manual title")
    content: str = Field(description="Full entry text")
    entry_date: date = Field(description="Date of the entry")
    path: str = Field(description="AnyType path: Journal/Year/Month")
    tags: list[str] = Field(default_factory=list, description="AI-extracted tags")
    created_at: datetime = Field(description="When entry was created")

    # Container references
    journal_id: str = Field(description="Journal collection ID")
    year_id: str = Field(description="Year container ID")
    month_id: str = Field(description="Month container ID")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def day_prefix(self) -> str:
        """Day number prefix for title (e.g., '24')."""
        return str(self.entry_date.day)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def full_title(self) -> str:
        """Complete title with day prefix."""
        return f"{self.day_prefix} - {self.title}"


class JournalEntryReference(BaseModel):
    """Lightweight reference to a journal entry for local storage."""

    id: str = Field(description="AnyType object ID")
    space_id: str = Field(description="AnyType space ID")
    path: str = Field(description="Journal/Year/Month path")
    title: str = Field(description="Entry title with day prefix")
    entry_date: date = Field(description="Entry date")
    created_at: datetime = Field(description="Creation timestamp")
    tags: list[str] = Field(default_factory=list)
    has_deep_dive: bool = Field(default=False)
    content_preview: str = Field(default="", description="First 100 chars")


class DeepDive(BaseModel):
    """AI-generated deep dive analysis of a journal entry."""

    id: str = Field(description="Unique deep dive ID")
    entry_id: str = Field(description="Associated journal entry ID")
    user_request: str = Field(description="What the user asked for")
    ai_response: str = Field(description="AI's deep dive content")
    format_type: str = Field(description="e.g., 'emotional', 'action_items', 'socratic'")
    created_at: datetime = Field(description="When generated")


MoodType = Literal["positive", "negative", "neutral", "mixed"]


class InsightsResult(BaseModel):
    """Result of cross-entry AI analysis."""

    analysis_window: str = Field(description="Time range analyzed")
    entry_count: int = Field(description="Number of entries analyzed")
    themes: list[str] = Field(default_factory=list, description="Recurring themes identified")
    patterns: list[str] = Field(default_factory=list, description="Behavioral patterns noticed")
    observations: str = Field(description="Free-form AI observations")
    generated_at: datetime = Field(description="When analysis was generated")


class ExtractedMetadata(BaseModel):
    """Metadata extracted from a journal entry by AI."""

    tags: list[str] = Field(default_factory=list, description="1-5 relevant tags")
    mood: MoodType = Field(default="neutral", description="Detected mood")
    topics: list[str] = Field(default_factory=list, description="Main topics discussed")
