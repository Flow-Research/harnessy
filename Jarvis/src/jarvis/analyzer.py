"""Workload analysis for task scheduling."""

from collections import defaultdict
from datetime import date, timedelta

from jarvis.models import DayWorkload, Task, WorkloadAnalysis


def analyze_workload(
    tasks: list[Task],
    start_date: date,
    end_date: date,
) -> WorkloadAnalysis:
    """Analyze workload distribution across a date range.

    Args:
        tasks: List of tasks to analyze
        start_date: Start of the analysis period
        end_date: End of the analysis period

    Returns:
        WorkloadAnalysis with daily breakdown and totals
    """
    # Group tasks by date
    tasks_by_date: dict[date, list[Task]] = defaultdict(list)
    for task in tasks:
        if task.scheduled_date and start_date <= task.scheduled_date <= end_date:
            tasks_by_date[task.scheduled_date].append(task)

    # Build daily workload for each day in range
    days: list[DayWorkload] = []
    current = start_date
    total_moveable = 0
    total_immovable = 0

    while current <= end_date:
        day_tasks = tasks_by_date.get(current, [])
        moveable = sum(1 for t in day_tasks if t.is_moveable)
        immovable = len(day_tasks) - moveable

        total_moveable += moveable
        total_immovable += immovable

        days.append(
            DayWorkload(
                day_date=current,
                total_tasks=len(day_tasks),
                moveable_tasks=moveable,
                immovable_tasks=immovable,
                task_ids=[t.id for t in day_tasks],
            )
        )

        current += timedelta(days=1)

    return WorkloadAnalysis(
        start_date=start_date,
        end_date=end_date,
        days=days,
        total_moveable=total_moveable,
        total_immovable=total_immovable,
    )


def get_overloaded_days(analysis: WorkloadAnalysis) -> list[DayWorkload]:
    """Get all days that are overloaded (>6 tasks)."""
    return [d for d in analysis.days if d.status == "overloaded"]


def get_light_days(analysis: WorkloadAnalysis) -> list[DayWorkload]:
    """Get all days that are light (<3 tasks)."""
    return [d for d in analysis.days if d.status == "light"]


def get_moveable_tasks_on_day(tasks: list[Task], target_date: date) -> list[Task]:
    """Get moveable tasks scheduled for a specific date."""
    return [
        t for t in tasks
        if t.scheduled_date == target_date and t.is_moveable
    ]
