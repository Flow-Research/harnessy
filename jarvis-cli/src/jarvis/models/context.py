"""User context models for AI-powered task scheduling.

These models are used by the AI client to load and format user context.
"""

from pydantic import BaseModel, Field, computed_field


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
