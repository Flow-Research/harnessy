"""Service layer for Jarvis.

This module provides a high-level service layer that abstracts adapter
operations and provides capability checking, error translation, and
business logic coordination.
"""

from .task_service import TaskService
from .journal_service import JournalService
from .adapter_service import get_adapter, ensure_connected
from .planning_service import (
    build_calendar_plan,
    build_reorganize_suggestions,
    parse_work_hours_from_context,
)

__all__ = [
    "TaskService",
    "JournalService",
    "build_reorganize_suggestions",
    "build_calendar_plan",
    "parse_work_hours_from_context",
    "get_adapter",
    "ensure_connected",
]
