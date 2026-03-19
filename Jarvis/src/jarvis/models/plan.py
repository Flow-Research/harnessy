"""Domain models for weekly planning.

These models represent the data structures used by the plan command
for context aggregation, alignment scoring, gap analysis, and plan generation.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Literal


class FocusMode(str, Enum):
    """User's current operational mode extracted from focus.md."""

    SHIPPING = "shipping"
    LEARNING = "learning"
    EXPLORING = "exploring"
    RECOVERY = "recovery"
    UNKNOWN = "unknown"

    @classmethod
    def from_string(cls, value: str) -> "FocusMode":
        """Parse focus mode from string, case-insensitive."""
        normalized = value.lower().strip()
        for mode in cls:
            if mode.value in normalized or normalized in mode.value:
                return mode
        return cls.UNKNOWN


# Emoji mapping for focus modes
FOCUS_MODE_EMOJI: dict[FocusMode, str] = {
    FocusMode.SHIPPING: "🚀",
    FocusMode.LEARNING: "📚",
    FocusMode.EXPLORING: "🔍",
    FocusMode.RECOVERY: "🌿",
    FocusMode.UNKNOWN: "❓",
}


@dataclass
class FocusSummary:
    """Synthesized focus from context files."""

    mode: FocusMode
    mode_emoji: str
    primary_goal: str | None
    decision_rule: str | None
    until_date: date | None

    @classmethod
    def empty(cls) -> "FocusSummary":
        """Create empty focus summary for graceful degradation."""
        return cls(
            mode=FocusMode.UNKNOWN,
            mode_emoji=FOCUS_MODE_EMOJI[FocusMode.UNKNOWN],
            primary_goal=None,
            decision_rule=None,
            until_date=None,
        )

    @classmethod
    def from_mode(
        cls,
        mode: FocusMode,
        primary_goal: str | None = None,
        decision_rule: str | None = None,
        until_date: date | None = None,
    ) -> "FocusSummary":
        """Create focus summary from mode with auto-emoji."""
        return cls(
            mode=mode,
            mode_emoji=FOCUS_MODE_EMOJI.get(mode, "❓"),
            primary_goal=primary_goal,
            decision_rule=decision_rule,
            until_date=until_date,
        )


@dataclass
class ExtractedGoal:
    """A goal extracted from context files."""

    text: str
    timeframe: Literal["this_week", "this_month", "this_quarter", "ongoing"]
    source_file: str  # e.g., "goals.md"
    has_tasks: bool = False  # Set during gap analysis
    matching_task_ids: list[str] = field(default_factory=list)


@dataclass
class TaskCategory:
    """A category of tasks with alignment info."""

    name: str
    emoji: str
    task_ids: list[str]
    task_count: int
    is_aligned: bool  # Aligned with current focus

    @property
    def percentage(self) -> float:
        """Placeholder for percentage calculation (set externally)."""
        return 0.0


@dataclass
class TaskReality:
    """Current state of scheduled tasks."""

    total_tasks: int
    tasks_by_day: dict[date, list[str]]  # date -> task_ids
    tasks_by_category: list[TaskCategory]
    alignment_score: float  # 0.0 - 1.0
    overloaded_days: list[date]  # days with >6 tasks
    empty_days: list[date]  # days with 0 tasks in window

    @property
    def alignment_percent(self) -> int:
        """Alignment score as percentage."""
        return int(self.alignment_score * 100)

    @classmethod
    def empty(cls) -> "TaskReality":
        """Create empty task reality for no-task scenarios."""
        return cls(
            total_tasks=0,
            tasks_by_day={},
            tasks_by_category=[],
            alignment_score=0.0,
            overloaded_days=[],
            empty_days=[],
        )


@dataclass
class GapAnalysis:
    """Gaps between goals and scheduled work."""

    goals_without_tasks: list[ExtractedGoal]
    focus_conflicts: list[str]  # Human-readable conflict descriptions
    schedule_issues: list[str]  # Overload, no buffer, etc.

    @property
    def has_critical_gaps(self) -> bool:
        """True if >2 goals without tasks or any focus conflicts."""
        return len(self.goals_without_tasks) > 2 or len(self.focus_conflicts) > 0

    @property
    def total_gaps(self) -> int:
        return (
            len(self.goals_without_tasks)
            + len(self.focus_conflicts)
            + len(self.schedule_issues)
        )

    @classmethod
    def empty(cls) -> "GapAnalysis":
        """Create empty gap analysis."""
        return cls(
            goals_without_tasks=[],
            focus_conflicts=[],
            schedule_issues=[],
        )


@dataclass
class DailyPlan:
    """Recommended plan for a single day."""

    plan_date: date
    day_name: str  # "Monday", "Tuesday", etc.
    theme: str  # "Deep work day", "Light day", etc.
    existing_tasks: list[str]  # Task titles
    suggestions: list[str]  # Suggested new tasks
    actions: list[str]  # Actions to take (e.g., "Defer X tasks")
    warnings: list[str]  # Issues to be aware of


@dataclass
class QuickAction:
    """Ready-to-run command suggestion."""

    label: str  # "[1]", "[2]", etc.
    command: str  # Full jarvis command
    description: str  # What it does


@dataclass
class WeeklyPlan:
    """Complete weekly plan output."""

    focus_summary: FocusSummary
    task_reality: TaskReality
    gap_analysis: GapAnalysis
    daily_plans: list[DailyPlan]
    quick_actions: list[QuickAction]
    generated_at: datetime
    planning_horizon: int  # days
    context_quality: Literal["full", "partial", "minimal", "none"]

    @property
    def has_gaps(self) -> bool:
        return self.gap_analysis.total_gaps > 0


@dataclass
class PlanContext:
    """Aggregated and parsed context for planning."""

    # Extracted structured data
    focus: FocusSummary
    goals: list[ExtractedGoal]
    priority_rules: list[str]
    constraints: list[str]
    active_projects: list[str]
    blockers: list[str]

    # Raw context for AI prompt
    raw_context: str  # From UserContext.to_prompt_context()

    # Metadata
    context_quality: Literal["full", "partial", "minimal", "none"]
    missing_files: list[str]

    @classmethod
    def empty(cls) -> "PlanContext":
        """Create empty context for graceful degradation."""
        return cls(
            focus=FocusSummary.empty(),
            goals=[],
            priority_rules=[],
            constraints=[],
            active_projects=[],
            blockers=[],
            raw_context="No user context provided.",
            context_quality="none",
            missing_files=[],
        )

    @property
    def has_goals(self) -> bool:
        """Check if any goals are defined."""
        return len(self.goals) > 0

    @property
    def has_focus(self) -> bool:
        """Check if focus mode is defined."""
        return self.focus.mode != FocusMode.UNKNOWN
