"""Tests for alignment scoring functionality."""

import pytest
from datetime import date, datetime

from jarvis.models import Task, Priority
from jarvis.models.plan import (
    FocusMode,
    FocusSummary,
    ExtractedGoal,
    PlanContext,
)
from jarvis.plan.alignment import (
    calculate_alignment,
    build_task_reality,
)


def make_task(
    name: str,
    task_id: str = "test-id",
    tags: list[str] | None = None,
    scheduled_date: date | None = None,
    priority: Priority | None = None,
) -> Task:
    """Helper to create test tasks."""
    now = datetime.now()
    return Task(
        id=task_id,
        space_id="test-space",
        title=name,
        tags=tags or [],
        due_date=scheduled_date or date.today(),
        priority=priority,
        is_done=False,
        created_at=now,
        updated_at=now,
    )


def make_context(
    mode: FocusMode = FocusMode.SHIPPING,
    goals: list[str] | None = None,
    projects: list[str] | None = None,
) -> PlanContext:
    """Helper to create test context."""
    goal_objs = [
        ExtractedGoal(
            text=g,
            timeframe="this_week",
            source_file="goals.md",
        )
        for g in (goals or [])
    ]

    return PlanContext(
        focus=FocusSummary.from_mode(mode, primary_goal=goals[0] if goals else None),
        goals=goal_objs,
        priority_rules=[],
        constraints=[],
        active_projects=projects or [],
        blockers=[],
        raw_context="Test context",
        context_quality="full",
        missing_files=[],
    )


class TestCalculateAlignment:
    """Tests for alignment score calculation."""

    def test_all_aligned_tasks(self):
        """Tasks with matching tags should be aligned."""
        tasks = [
            make_task("Write paper", task_id="1", tags=["research", "paper"]),
            make_task("Run experiment", task_id="2", tags=["research"]),
            make_task("Submit draft", task_id="3", tags=["ship", "paper"]),
        ]
        context = make_context(
            mode=FocusMode.SHIPPING,
            goals=["Submit paper to ICML"],
            projects=["Paper"],
        )

        result = calculate_alignment(tasks, context)

        # All tasks should be aligned with shipping mode
        assert result.score > 0.5
        assert len(result.aligned_task_ids) >= 2

    def test_mixed_alignment(self):
        """Mix of aligned and unaligned tasks."""
        tasks = [
            make_task("Write paper", task_id="1", tags=["research"]),
            make_task("Client meeting", task_id="2", tags=["business"]),
            make_task("Buy groceries", task_id="3", tags=["personal"]),
            make_task("Code review", task_id="4", tags=["dev"]),
        ]
        context = make_context(
            mode=FocusMode.SHIPPING,
            goals=["Complete project"],
        )

        result = calculate_alignment(tasks, context)

        # Some tasks aligned, some not
        assert 0.0 <= result.score <= 1.0
        assert len(result.aligned_task_ids) + len(result.unaligned_task_ids) == 4

    def test_no_tasks_returns_zero_score(self):
        """Empty task list should return zero score."""
        context = make_context()

        result = calculate_alignment([], context)

        assert result.score == 0.0
        assert result.categories == []

    def test_category_assignment(self):
        """Tasks should be assigned to categories."""
        tasks = [
            make_task("Research topic", task_id="1", tags=["research"]),
            make_task("Client call", task_id="2", tags=["business"]),
            make_task("Fix bug", task_id="3", tags=["dev"]),
        ]
        context = make_context()

        result = calculate_alignment(tasks, context)

        # Should have categories
        assert len(result.categories) > 0

        # Each task should be in a category
        all_task_ids = set()
        for cat in result.categories:
            all_task_ids.update(cat.task_ids)
        assert len(all_task_ids) == 3

    def test_unknown_mode_no_alignment_preference(self):
        """Unknown focus mode should not favor any category."""
        tasks = [
            make_task("Task 1", task_id="1", tags=["personal"]),
            make_task("Task 2", task_id="2", tags=["business"]),
        ]
        context = make_context(mode=FocusMode.UNKNOWN)

        result = calculate_alignment(tasks, context)

        # With unknown mode, no inherent alignment from mode
        assert 0.0 <= result.score <= 1.0


class TestBuildTaskReality:
    """Tests for building task reality."""

    def test_tasks_grouped_by_day(self):
        """Tasks should be grouped by scheduled date."""
        today = date.today()
        tomorrow = date(today.year, today.month, today.day + 1) if today.day < 28 else today

        tasks = [
            make_task("Task 1", task_id="1", scheduled_date=today),
            make_task("Task 2", task_id="2", scheduled_date=today),
            make_task("Task 3", task_id="3", scheduled_date=tomorrow),
        ]
        context = make_context()
        alignment = calculate_alignment(tasks, context)

        result = build_task_reality(
            tasks=tasks,
            alignment_result=alignment,
            start_date=today,
            end_date=tomorrow,
        )

        assert result.total_tasks == 3
        assert today in result.tasks_by_day
        assert len(result.tasks_by_day[today]) == 2

    def test_detect_overloaded_days(self):
        """Days with >6 tasks should be marked overloaded."""
        today = date.today()

        # Create 8 tasks for today
        tasks = [
            make_task(f"Task {i}", task_id=str(i), scheduled_date=today)
            for i in range(8)
        ]
        context = make_context()
        alignment = calculate_alignment(tasks, context)

        result = build_task_reality(
            tasks=tasks,
            alignment_result=alignment,
            start_date=today,
            end_date=today,
        )

        assert today in result.overloaded_days

    def test_detect_empty_days(self):
        """Days with no tasks should be in empty_days."""
        from datetime import timedelta

        today = date.today()
        tomorrow = today + timedelta(days=1)
        day_after = today + timedelta(days=2)

        tasks = [
            make_task("Task 1", task_id="1", scheduled_date=today),
            # tomorrow has no tasks
            make_task("Task 2", task_id="2", scheduled_date=day_after),
        ]
        context = make_context()
        alignment = calculate_alignment(tasks, context)

        result = build_task_reality(
            tasks=tasks,
            alignment_result=alignment,
            start_date=today,
            end_date=day_after,
        )

        assert tomorrow in result.empty_days

    def test_alignment_percent_conversion(self):
        """Alignment score should convert to percentage correctly."""
        tasks = [make_task("Task 1", task_id="1")]
        context = make_context()
        alignment = calculate_alignment(tasks, context)

        result = build_task_reality(
            tasks=tasks,
            alignment_result=alignment,
            start_date=date.today(),
            end_date=date.today(),
        )

        # alignment_percent should be 0-100 integer
        assert 0 <= result.alignment_percent <= 100
        assert isinstance(result.alignment_percent, int)
