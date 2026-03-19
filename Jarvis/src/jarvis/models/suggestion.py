"""Suggestion models for AI-generated task rescheduling.

These models are used by the AI client to store and manage suggestions.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


SuggestionStatus = Literal["pending", "accepted", "rejected", "applied", "failed"]


class Suggestion(BaseModel):
    """A proposed task rescheduling."""

    id: str = Field(description="Unique suggestion ID")
    task_id: str = Field(description="Task ID")
    task_name: str = Field(description="Task name for display")
    current_date: date = Field(description="Current scheduled date")
    proposed_date: date = Field(description="Suggested new date")
    reasoning: str = Field(description="AI-generated explanation")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score 0-1")
    status: SuggestionStatus = Field(default="pending", description="Suggestion status")
    created_at: datetime = Field(description="When suggestion was generated")

    def accept(self) -> None:
        """Mark suggestion as accepted."""
        self.status = "accepted"

    def reject(self) -> None:
        """Mark suggestion as rejected."""
        self.status = "rejected"

    def mark_applied(self) -> None:
        """Mark suggestion as successfully applied."""
        self.status = "applied"

    def mark_failed(self) -> None:
        """Mark suggestion as failed to apply."""
        self.status = "failed"
