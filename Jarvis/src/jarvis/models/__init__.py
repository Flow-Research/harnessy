"""Domain models for Jarvis backend abstraction.

This package provides backend-agnostic data models that work
across all supported knowledge base systems.
"""

from .backend_object import BackendObject, ObjectProperty, PropertyFormat
from .context import UserContext
from .journal import JournalEntry
from .plan import (
    DailyPlan,
    ExtractedGoal,
    FocusMode,
    FocusSummary,
    GapAnalysis,
    PlanContext,
    QuickAction,
    TaskCategory,
    TaskReality,
    WeeklyPlan,
)
from .planning import (
    AppliedBlockResult,
    CalendarBusySlot,
    PlanApplyResult,
    PlannedBlock,
    SchedulePlan,
    TaskPlanningInput,
    UnplacedTask,
)
from .priority import Priority
from .space import Space
from .suggestion import Suggestion
from .tag import Tag
from .task import Task
from .workload import DayWorkload, WorkloadAnalysis

__all__ = [
    # Core domain models
    "BackendObject",
    "JournalEntry",
    "ObjectProperty",
    "Priority",
    "PropertyFormat",
    "Space",
    "Tag",
    "Task",
    # Schedule planning models (epic 07)
    "TaskPlanningInput",
    "CalendarBusySlot",
    "PlannedBlock",
    "UnplacedTask",
    "SchedulePlan",
    "AppliedBlockResult",
    "PlanApplyResult",
    # Weekly planning models (epic 05)
    "DailyPlan",
    "ExtractedGoal",
    "FocusMode",
    "FocusSummary",
    "GapAnalysis",
    "PlanContext",
    "QuickAction",
    "TaskCategory",
    "TaskReality",
    "WeeklyPlan",
    # Workload analysis models
    "DayWorkload",
    "WorkloadAnalysis",
    # AI/scheduling models
    "Suggestion",
    "UserContext",
]
