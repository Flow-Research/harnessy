"""Domain models for Jarvis task scheduler."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, computed_field


class Task(BaseModel):
    """Represents a task from AnyType."""

    id: str = Field(description="AnyType object ID")
    space_id: str = Field(description="AnyType space ID")
    name: str = Field(description="Task title")
    scheduled_date: date | None = Field(default=None, description="When task is scheduled")
    due_date: date | None = Field(default=None, description="Hard deadline")
    priority: str | None = Field(default=None, description="Priority level if set")
    tags: list[str] = Field(default_factory=list, description="Tags including bar_movement")
    is_done: bool = Field(default=False, description="Completion status")
    created_at: datetime = Field(description="When task was created")
    updated_at: datetime = Field(description="When task was last updated")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_moveable(self) -> bool:
        """Task can be rescheduled if not tagged bar_movement."""
        return "bar_movement" not in self.tags

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_deadline(self) -> bool:
        """Check if task has a due date."""
        return self.due_date is not None


class DayWorkload(BaseModel):
    """Workload for a single day."""

    day_date: date = Field(description="The date")
    total_tasks: int = Field(description="Total number of tasks")
    moveable_tasks: int = Field(description="Tasks that can be rescheduled")
    immovable_tasks: int = Field(description="Tasks with bar_movement tag")
    task_ids: list[str] = Field(default_factory=list, description="IDs of tasks on this day")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def status(self) -> Literal["overloaded", "balanced", "light"]:
        """Determine day status based on task count."""
        if self.total_tasks > 6:
            return "overloaded"
        elif self.total_tasks < 3:
            return "light"
        return "balanced"


class WorkloadAnalysis(BaseModel):
    """Complete workload analysis for a date range."""

    start_date: date = Field(description="Start of analysis period")
    end_date: date = Field(description="End of analysis period")
    days: list[DayWorkload] = Field(default_factory=list, description="Daily workload data")
    total_moveable: int = Field(description="Total moveable tasks in range")
    total_immovable: int = Field(description="Total immovable tasks in range")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def variance(self) -> float:
        """Standard deviation of daily task counts (lower is better)."""
        if not self.days:
            return 0.0
        counts = [d.total_tasks for d in self.days]
        mean = sum(counts) / len(counts)
        variance = sum((x - mean) ** 2 for x in counts) / len(counts)
        return float(variance**0.5)


SuggestionStatus = Literal["pending", "accepted", "rejected", "applied", "failed"]


class Suggestion(BaseModel):
    """A proposed task rescheduling."""

    id: str = Field(description="Unique suggestion ID")
    task_id: str = Field(description="AnyType task ID")
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


class UserContext(BaseModel):
    """User context loaded from markdown files.

    MVP simplification: Store raw markdown content and let AI interpret.
    """

    # Core scheduling context
    preferences_raw: str = Field(default="", description="Raw preferences.md content")
    patterns_raw: str = Field(default="", description="Raw patterns.md content")
    constraints_raw: str = Field(default="", description="Raw constraints.md content")
    priorities_raw: str = Field(default="", description="Raw priorities.md content")

    # Extended context
    goals_raw: str = Field(default="", description="Raw goals.md content")
    projects_raw: str = Field(default="", description="Raw projects.md content")
    recurring_raw: str = Field(default="", description="Raw recurring.md content")
    focus_raw: str = Field(default="", description="Raw focus.md content")
    blockers_raw: str = Field(default="", description="Raw blockers.md content")
    calendar_raw: str = Field(default="", description="Raw calendar.md content")
    delegation_raw: str = Field(default="", description="Raw delegation.md content")
    decisions_raw: str = Field(default="", description="Raw decisions.md content")

    def to_prompt_context(self) -> str:
        """Format all context for inclusion in AI prompt."""
        sections: list[str] = []

        # Core context
        if self.preferences_raw.strip():
            sections.append(f"## User Preferences\n{self.preferences_raw}")

        if self.patterns_raw.strip():
            sections.append(f"## Work Patterns\n{self.patterns_raw}")

        if self.constraints_raw.strip():
            sections.append(f"## Constraints\n{self.constraints_raw}")

        if self.priorities_raw.strip():
            sections.append(f"## Priorities\n{self.priorities_raw}")

        # Extended context
        if self.goals_raw.strip():
            sections.append(f"## Goals & Objectives\n{self.goals_raw}")

        if self.projects_raw.strip():
            sections.append(f"## Active Projects\n{self.projects_raw}")

        if self.recurring_raw.strip():
            sections.append(f"## Recurring Tasks\n{self.recurring_raw}")

        if self.focus_raw.strip():
            sections.append(f"## Current Focus\n{self.focus_raw}")

        if self.blockers_raw.strip():
            sections.append(f"## Blockers\n{self.blockers_raw}")

        if self.calendar_raw.strip():
            sections.append(f"## Calendar Context\n{self.calendar_raw}")

        if self.delegation_raw.strip():
            sections.append(f"## Delegation\n{self.delegation_raw}")

        if self.decisions_raw.strip():
            sections.append(f"## Decision Log\n{self.decisions_raw}")

        return "\n\n".join(sections) if sections else "No user context provided."

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_context(self) -> bool:
        """Check if any context is provided."""
        return any(
            getattr(self, field).strip()
            for field in UserContext.model_fields
            if field.endswith("_raw")
        )
