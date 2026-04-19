"""Tests for workload analyzer."""

from datetime import date, datetime, timedelta

from jarvis.analyzer import (
    analyze_workload,
    get_light_days,
    get_moveable_tasks_on_day,
    get_overloaded_days,
)
from jarvis.models import Task


def make_task(
    name: str,
    scheduled: date | None = None,
    tags: list[str] | None = None,
) -> Task:
    """Helper to create a task for testing."""
    now = datetime.now()
    return Task(
        id=f"task_{name}",
        space_id="space_1",
        title=name,
        due_date=scheduled,  # Use due_date (scheduled_date is an alias)
        tags=tags or [],
        created_at=now,
        updated_at=now,
    )


class TestAnalyzeWorkload:
    """Tests for analyze_workload function."""

    def test_empty_tasks(self) -> None:
        """Test analysis with no tasks."""
        start = date.today()
        end = start + timedelta(days=7)

        analysis = analyze_workload([], start, end)

        assert analysis.start_date == start
        assert analysis.end_date == end
        assert analysis.total_moveable == 0
        assert analysis.total_immovable == 0
        assert len(analysis.days) == 8  # 8 days inclusive

    def test_tasks_distributed(self) -> None:
        """Test analysis with tasks on different days."""
        start = date.today()
        end = start + timedelta(days=2)

        tasks = [
            make_task("task1", scheduled=start),
            make_task("task2", scheduled=start),
            make_task("task3", scheduled=start + timedelta(days=1)),
        ]

        analysis = analyze_workload(tasks, start, end)

        assert analysis.total_moveable == 3
        assert analysis.days[0].total_tasks == 2
        assert analysis.days[1].total_tasks == 1
        assert analysis.days[2].total_tasks == 0

    def test_immovable_tasks_counted(self) -> None:
        """Test that bar_movement tasks are counted separately."""
        start = date.today()
        end = start + timedelta(days=1)

        tasks = [
            make_task("moveable", scheduled=start),
            make_task("immovable", scheduled=start, tags=["bar_movement"]),
        ]

        analysis = analyze_workload(tasks, start, end)

        assert analysis.total_moveable == 1
        assert analysis.total_immovable == 1
        assert analysis.days[0].moveable_tasks == 1
        assert analysis.days[0].immovable_tasks == 1

    def test_tasks_outside_range_excluded(self) -> None:
        """Test that tasks outside date range are excluded."""
        start = date.today()
        end = start + timedelta(days=2)

        tasks = [
            make_task("inside", scheduled=start),
            make_task("before", scheduled=start - timedelta(days=1)),
            make_task("after", scheduled=end + timedelta(days=1)),
        ]

        analysis = analyze_workload(tasks, start, end)

        assert analysis.total_moveable == 1

    def test_unscheduled_tasks_excluded(self) -> None:
        """Test that tasks without scheduled_date are excluded."""
        start = date.today()
        end = start + timedelta(days=1)

        tasks = [
            make_task("scheduled", scheduled=start),
            make_task("unscheduled", scheduled=None),
        ]

        analysis = analyze_workload(tasks, start, end)

        assert analysis.total_moveable == 1


class TestGetOverloadedDays:
    """Tests for get_overloaded_days helper."""

    def test_finds_overloaded_days(self) -> None:
        """Test that days with >6 tasks are identified."""
        start = date.today()
        end = start + timedelta(days=1)

        tasks = [make_task(f"task{i}", scheduled=start) for i in range(8)]

        analysis = analyze_workload(tasks, start, end)
        overloaded = get_overloaded_days(analysis)

        assert len(overloaded) == 1
        assert overloaded[0].day_date == start
        assert overloaded[0].total_tasks == 8


class TestGetLightDays:
    """Tests for get_light_days helper."""

    def test_finds_light_days(self) -> None:
        """Test that days with <3 tasks are identified."""
        start = date.today()
        end = start + timedelta(days=2)

        tasks = [
            make_task("task1", scheduled=start + timedelta(days=1)),
            make_task("task2", scheduled=start + timedelta(days=1)),
        ]

        analysis = analyze_workload(tasks, start, end)
        light = get_light_days(analysis)

        # Day 0 and Day 2 have 0 tasks, Day 1 has 2 tasks
        assert len(light) == 3  # All days are light in this case


class TestGetMoveableTasksOnDay:
    """Tests for get_moveable_tasks_on_day helper."""

    def test_finds_moveable_tasks(self) -> None:
        """Test that only moveable tasks on target date are returned."""
        target = date.today()

        tasks = [
            make_task("moveable1", scheduled=target),
            make_task("moveable2", scheduled=target),
            make_task("immovable", scheduled=target, tags=["bar_movement"]),
            make_task("other_day", scheduled=target + timedelta(days=1)),
        ]

        moveable = get_moveable_tasks_on_day(tasks, target)

        assert len(moveable) == 2
        assert all(t.is_moveable for t in moveable)
        assert all(t.scheduled_date == target for t in moveable)
