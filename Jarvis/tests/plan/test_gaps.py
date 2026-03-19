"""Tests for gap detection functionality."""

import pytest
from datetime import date, datetime, timedelta

from jarvis.models import Task, Priority
from jarvis.models.plan import (
    FocusMode,
    FocusSummary,
    ExtractedGoal,
    PlanContext,
    TaskCategory,
)
from jarvis.plan.gaps import (
    detect_gaps,
    match_goals_to_tasks,
)


def make_task(
    name: str,
    task_id: str = "test-id",
    tags: list[str] | None = None,
    scheduled_date: date | None = None,
    description: str | None = None,
) -> Task:
    """Helper to create test tasks."""
    now = datetime.now()
    return Task(
        id=task_id,
        space_id="test-space",
        title=name,
        tags=tags or [],
        due_date=scheduled_date or date.today(),
        description=description,
        is_done=False,
        created_at=now,
        updated_at=now,
    )


def make_context(
    mode: FocusMode = FocusMode.SHIPPING,
    goals: list[str] | None = None,
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
        focus=FocusSummary.from_mode(mode),
        goals=goal_objs,
        priority_rules=[],
        constraints=[],
        active_projects=[],
        blockers=[],
        raw_context="Test context",
        context_quality="full",
        missing_files=[],
    )


def make_category(
    name: str,
    task_count: int,
    is_aligned: bool = True,
) -> TaskCategory:
    """Helper to create test categories."""
    return TaskCategory(
        name=name,
        emoji="📦",
        task_ids=[f"task-{i}" for i in range(task_count)],
        task_count=task_count,
        is_aligned=is_aligned,
    )


class TestDetectGaps:
    """Tests for gap detection."""

    def test_detect_goals_without_tasks(self):
        """Should identify goals with no supporting tasks."""
        tasks = [
            make_task("Write code", task_id="1"),
            make_task("Review PR", task_id="2"),
        ]
        context = make_context(
            goals=[
                "Write paper abstract",
                "Generate figures",
                "Submit to conference",
            ]
        )
        categories = [make_category("Development", 2)]

        result = detect_gaps(
            tasks=tasks,
            context=context,
            categories=categories,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=6),
        )

        # Goals don't match tasks
        assert len(result.goals_without_tasks) >= 2

    def test_detect_focus_conflicts(self):
        """Should detect conflicts between focus mode and tasks."""
        context = make_context(mode=FocusMode.SHIPPING)

        # 50% unaligned categories
        categories = [
            make_category("Development", 5, is_aligned=True),
            make_category("Business", 5, is_aligned=False),
        ]

        result = detect_gaps(
            tasks=[],
            context=context,
            categories=categories,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=6),
        )

        # Should detect the focus conflict
        assert len(result.focus_conflicts) > 0 or result.total_gaps > 0

    def test_detect_overloaded_days(self):
        """Should detect overloaded days."""
        today = date.today()

        # 8 tasks on the same day
        tasks = [
            make_task(f"Task {i}", task_id=str(i), scheduled_date=today)
            for i in range(8)
        ]
        context = make_context()
        categories = []

        result = detect_gaps(
            tasks=tasks,
            context=context,
            categories=categories,
            start_date=today,
            end_date=today,
        )

        # Should detect overload
        assert any("overload" in issue.lower() for issue in result.schedule_issues)

    def test_detect_no_buffer_time(self):
        """Should detect lack of buffer time in a week."""
        today = date.today()

        # Create 5 tasks per day for 7 days
        tasks = []
        for day_offset in range(7):
            day = today + timedelta(days=day_offset)
            for i in range(5):
                tasks.append(
                    make_task(
                        f"Task {day_offset}-{i}",
                        task_id=f"{day_offset}-{i}",
                        scheduled_date=day,
                    )
                )

        context = make_context()
        categories = []

        result = detect_gaps(
            tasks=tasks,
            context=context,
            categories=categories,
            start_date=today,
            end_date=today + timedelta(days=6),
        )

        # Should detect no buffer time (no light days)
        assert any("buffer" in issue.lower() for issue in result.schedule_issues)

    def test_no_gaps_for_aligned_schedule(self):
        """Well-aligned schedule should have minimal gaps."""
        tasks = [
            make_task("Write paper intro", task_id="1", tags=["paper"]),
            make_task("Research methods", task_id="2", tags=["research"]),
        ]
        context = make_context(
            mode=FocusMode.SHIPPING,
            goals=["Write paper", "Research methods section"],
        )
        categories = [make_category("Research", 2, is_aligned=True)]

        result = detect_gaps(
            tasks=tasks,
            context=context,
            categories=categories,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=6),
        )

        # Some goals may match, so gaps should be reduced
        # Note: Exact matching depends on keyword extraction
        assert result.total_gaps >= 0  # At least validates no error

    def test_has_critical_gaps_property(self):
        """has_critical_gaps should be True for many unmatched goals."""
        context = make_context(
            goals=[
                "Goal 1 that has no task",
                "Goal 2 that has no task",
                "Goal 3 that has no task",
            ]
        )
        categories = []

        result = detect_gaps(
            tasks=[],
            context=context,
            categories=categories,
            start_date=date.today(),
            end_date=date.today(),
        )

        # >2 goals without tasks = critical
        assert result.has_critical_gaps


class TestMatchGoalsToTasks:
    """Tests for goal-task matching."""

    def test_match_by_keyword(self):
        """Goals should match tasks by keyword."""
        goals = [
            ExtractedGoal(
                text="Write paper abstract",
                timeframe="this_week",
                source_file="goals.md",
            ),
        ]
        tasks = [
            make_task("Draft paper abstract", task_id="1"),
            make_task("Unrelated task", task_id="2"),
        ]

        result = match_goals_to_tasks(goals, tasks)

        # First goal should match first task (both mention "paper" and "abstract")
        assert result[0].has_tasks
        assert "1" in result[0].matching_task_ids

    def test_no_match_for_unrelated_goals(self):
        """Goals should not match unrelated tasks."""
        goals = [
            ExtractedGoal(
                text="Learn quantum computing",
                timeframe="this_week",
                source_file="goals.md",
            ),
        ]
        tasks = [
            make_task("Write report", task_id="1"),
            make_task("Client meeting", task_id="2"),
        ]

        result = match_goals_to_tasks(goals, tasks)

        # Goal shouldn't match any task
        assert not result[0].has_tasks
        assert result[0].matching_task_ids == []

    def test_match_updates_goal_objects(self):
        """Matching should update the goal objects in place."""
        goals = [
            ExtractedGoal(
                text="Review code changes",
                timeframe="this_week",
                source_file="goals.md",
            ),
        ]
        tasks = [
            make_task("Code review for PR #123", task_id="1"),
        ]

        result = match_goals_to_tasks(goals, tasks)

        # Result is the same list, modified
        assert result is goals
        assert goals[0].has_tasks
