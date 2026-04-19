"""Tests for domain models."""

from datetime import date, datetime, timedelta

import pytest

from jarvis.models import (
    DayWorkload,
    Suggestion,
    Task,
    UserContext,
    WorkloadAnalysis,
)


class TestTask:
    """Tests for Task model."""

    def test_task_creation(self) -> None:
        """Test basic task creation."""
        now = datetime.now()
        task = Task(
            id="task_1",
            space_id="space_1",
            title="Write docs",
            due_date=date.today(),
            created_at=now,
            updated_at=now,
        )
        assert task.id == "task_1"
        assert task.title == "Write docs"
        assert task.name == "Write docs"  # Backward-compatible alias
        assert task.due_date == date.today()
        assert task.scheduled_date == date.today()  # Backward-compatible alias

    def test_task_is_moveable_default(self) -> None:
        """Test that tasks without bar_movement tag are moveable."""
        now = datetime.now()
        task = Task(
            id="task_1",
            space_id="space_1",
            title="Regular task",
            tags=["work", "important"],
            created_at=now,
            updated_at=now,
        )
        assert task.is_moveable is True

    def test_task_is_not_moveable_with_bar_movement(self) -> None:
        """Test that tasks with bar_movement tag are not moveable."""
        now = datetime.now()
        task = Task(
            id="task_1",
            space_id="space_1",
            title="Fixed meeting",
            tags=["bar_movement", "meeting"],
            created_at=now,
            updated_at=now,
        )
        assert task.is_moveable is False

    def test_task_has_deadline(self) -> None:
        """Test has_deadline property."""
        now = datetime.now()

        task_with_deadline = Task(
            id="task_1",
            space_id="space_1",
            title="Deadline task",
            due_date=date.today() + timedelta(days=7),
            created_at=now,
            updated_at=now,
        )
        assert task_with_deadline.has_deadline is True

        task_without_deadline = Task(
            id="task_2",
            space_id="space_1",
            title="No deadline",
            created_at=now,
            updated_at=now,
        )
        assert task_without_deadline.has_deadline is False


class TestDayWorkload:
    """Tests for DayWorkload model."""

    def test_status_overloaded(self) -> None:
        """Test overloaded status when >6 tasks."""
        day = DayWorkload(
            day_date=date.today(),
            total_tasks=8,
            moveable_tasks=5,
            immovable_tasks=3,
        )
        assert day.status == "overloaded"

    def test_status_light(self) -> None:
        """Test light status when <3 tasks."""
        day = DayWorkload(
            day_date=date.today(),
            total_tasks=2,
            moveable_tasks=2,
            immovable_tasks=0,
        )
        assert day.status == "light"

    def test_status_balanced(self) -> None:
        """Test balanced status when 3-6 tasks."""
        day = DayWorkload(
            day_date=date.today(),
            total_tasks=4,
            moveable_tasks=3,
            immovable_tasks=1,
        )
        assert day.status == "balanced"

    def test_status_boundary_three(self) -> None:
        """Test boundary: exactly 3 tasks is balanced."""
        day = DayWorkload(
            day_date=date.today(),
            total_tasks=3,
            moveable_tasks=3,
            immovable_tasks=0,
        )
        assert day.status == "balanced"

    def test_status_boundary_six(self) -> None:
        """Test boundary: exactly 6 tasks is balanced."""
        day = DayWorkload(
            day_date=date.today(),
            total_tasks=6,
            moveable_tasks=4,
            immovable_tasks=2,
        )
        assert day.status == "balanced"


class TestWorkloadAnalysis:
    """Tests for WorkloadAnalysis model."""

    def test_variance_calculation(self) -> None:
        """Test variance calculation for workload."""
        analysis = WorkloadAnalysis(
            start_date=date.today(),
            end_date=date.today() + timedelta(days=2),
            days=[
                DayWorkload(
                    day_date=date.today(),
                    total_tasks=2,
                    moveable_tasks=2,
                    immovable_tasks=0,
                ),
                DayWorkload(
                    day_date=date.today() + timedelta(days=1),
                    total_tasks=4,
                    moveable_tasks=4,
                    immovable_tasks=0,
                ),
                DayWorkload(
                    day_date=date.today() + timedelta(days=2),
                    total_tasks=6,
                    moveable_tasks=6,
                    immovable_tasks=0,
                ),
            ],
            total_moveable=12,
            total_immovable=0,
        )
        # Mean = 4, variance = ((2-4)^2 + (4-4)^2 + (6-4)^2) / 3 = 8/3
        # Std dev = sqrt(8/3) ≈ 1.633
        assert abs(analysis.variance - 1.633) < 0.01

    def test_variance_empty(self) -> None:
        """Test variance with no days."""
        analysis = WorkloadAnalysis(
            start_date=date.today(),
            end_date=date.today(),
            days=[],
            total_moveable=0,
            total_immovable=0,
        )
        assert analysis.variance == 0.0

    def test_variance_uniform(self) -> None:
        """Test variance with uniform distribution."""
        analysis = WorkloadAnalysis(
            start_date=date.today(),
            end_date=date.today() + timedelta(days=2),
            days=[
                DayWorkload(
                    day_date=date.today(),
                    total_tasks=4,
                    moveable_tasks=4,
                    immovable_tasks=0,
                ),
                DayWorkload(
                    day_date=date.today() + timedelta(days=1),
                    total_tasks=4,
                    moveable_tasks=4,
                    immovable_tasks=0,
                ),
                DayWorkload(
                    day_date=date.today() + timedelta(days=2),
                    total_tasks=4,
                    moveable_tasks=4,
                    immovable_tasks=0,
                ),
            ],
            total_moveable=12,
            total_immovable=0,
        )
        assert analysis.variance == 0.0


class TestSuggestion:
    """Tests for Suggestion model."""

    def test_suggestion_creation(self) -> None:
        """Test basic suggestion creation."""
        now = datetime.now()
        suggestion = Suggestion(
            id="sug_001",
            task_id="task_1",
            task_name="Write docs",
            current_date=date.today(),
            proposed_date=date.today() + timedelta(days=2),
            reasoning="Balance workload",
            confidence=0.85,
            created_at=now,
        )
        assert suggestion.status == "pending"
        assert suggestion.confidence == 0.85

    def test_suggestion_accept(self) -> None:
        """Test accepting a suggestion."""
        now = datetime.now()
        suggestion = Suggestion(
            id="sug_001",
            task_id="task_1",
            task_name="Test",
            current_date=date.today(),
            proposed_date=date.today() + timedelta(days=1),
            reasoning="Test",
            confidence=0.8,
            created_at=now,
        )
        suggestion.accept()
        assert suggestion.status == "accepted"

    def test_suggestion_reject(self) -> None:
        """Test rejecting a suggestion."""
        now = datetime.now()
        suggestion = Suggestion(
            id="sug_001",
            task_id="task_1",
            task_name="Test",
            current_date=date.today(),
            proposed_date=date.today() + timedelta(days=1),
            reasoning="Test",
            confidence=0.8,
            created_at=now,
        )
        suggestion.reject()
        assert suggestion.status == "rejected"

    def test_suggestion_confidence_bounds(self) -> None:
        """Test that confidence must be between 0 and 1."""
        now = datetime.now()

        # Valid confidence
        suggestion = Suggestion(
            id="sug_001",
            task_id="task_1",
            task_name="Test",
            current_date=date.today(),
            proposed_date=date.today() + timedelta(days=1),
            reasoning="Test",
            confidence=0.5,
            created_at=now,
        )
        assert suggestion.confidence == 0.5

        # Invalid confidence should raise
        with pytest.raises(ValueError):
            Suggestion(
                id="sug_002",
                task_id="task_1",
                task_name="Test",
                current_date=date.today(),
                proposed_date=date.today() + timedelta(days=1),
                reasoning="Test",
                confidence=1.5,  # Invalid
                created_at=now,
            )


class TestUserContext:
    """Tests for UserContext model."""

    def test_empty_context(self) -> None:
        """Test empty context."""
        context = UserContext()
        assert context.to_prompt_context() == "No user context provided."
        assert context.has_context is False

    def test_partial_context(self) -> None:
        """Test context with some fields populated."""
        context = UserContext(
            preferences_raw="- Deep work in mornings\n- Admin on Fridays",
        )
        prompt = context.to_prompt_context()
        assert "User Preferences" in prompt
        assert "Deep work in mornings" in prompt
        assert context.has_context is True

    def test_full_context(self) -> None:
        """Test context with all fields populated."""
        context = UserContext(
            preferences_raw="Prefer mornings",
            patterns_raw="High energy before lunch",
            constraints_raw="No meetings on Wednesdays",
            priorities_raw="Client work first",
        )
        prompt = context.to_prompt_context()
        assert "User Preferences" in prompt
        assert "Work Patterns" in prompt
        assert "Constraints" in prompt
        assert "Priorities" in prompt
        assert context.has_context is True

    def test_whitespace_only_not_counted(self) -> None:
        """Test that whitespace-only content is not counted as context."""
        context = UserContext(
            preferences_raw="   \n\t  ",
            patterns_raw="",
        )
        assert context.has_context is False
        assert context.to_prompt_context() == "No user context provided."
