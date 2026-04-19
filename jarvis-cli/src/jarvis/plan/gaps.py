"""Gap detection for weekly planning.

This module identifies gaps between the user's stated goals and their
scheduled tasks, detecting misalignments that need attention.
"""

import re
from datetime import date, timedelta

from ..models import Task
from ..models.plan import (
    ExtractedGoal,
    FocusMode,
    GapAnalysis,
    PlanContext,
    TaskCategory,
)


def detect_gaps(
    tasks: list[Task],
    context: PlanContext,
    categories: list[TaskCategory],
    start_date: date,
    end_date: date,
) -> GapAnalysis:
    """Detect gaps between goals and tasks.

    Checks:
    1. Goals without corresponding tasks
    2. Focus mode vs task category conflicts
    3. Schedule issues (overload, no buffer)

    Args:
        tasks: Tasks in planning window
        context: Parsed planning context
        categories: Task categories from alignment analysis
        start_date: Start of planning window
        end_date: End of planning window

    Returns:
        GapAnalysis with categorized gaps
    """
    # Find goals without supporting tasks
    goals_without_tasks = _find_unmatched_goals(context.goals, tasks)

    # Detect focus mode conflicts
    focus_conflicts = _detect_focus_conflicts(context, categories)

    # Detect schedule issues
    schedule_issues = _detect_schedule_issues(tasks, start_date, end_date)

    return GapAnalysis(
        goals_without_tasks=goals_without_tasks,
        focus_conflicts=focus_conflicts,
        schedule_issues=schedule_issues,
    )


def match_goals_to_tasks(
    goals: list[ExtractedGoal],
    tasks: list[Task],
) -> list[ExtractedGoal]:
    """Match each goal to its supporting tasks.

    Updates goals with has_tasks and matching_task_ids.

    Args:
        goals: List of extracted goals
        tasks: List of tasks to match against

    Returns:
        Updated goals with matching info populated
    """
    for goal in goals:
        matching_ids = _find_matching_tasks(goal, tasks)
        goal.has_tasks = len(matching_ids) > 0
        goal.matching_task_ids = matching_ids

    return goals


def _find_unmatched_goals(
    goals: list[ExtractedGoal],
    tasks: list[Task],
) -> list[ExtractedGoal]:
    """Find goals that have no corresponding tasks.

    Args:
        goals: List of extracted goals
        tasks: List of tasks to match against

    Returns:
        List of goals without any matching tasks
    """
    unmatched: list[ExtractedGoal] = []

    for goal in goals:
        matching_ids = _find_matching_tasks(goal, tasks)
        if not matching_ids:
            # Create a copy with has_tasks set to False
            unmatched_goal = ExtractedGoal(
                text=goal.text,
                timeframe=goal.timeframe,
                source_file=goal.source_file,
                has_tasks=False,
                matching_task_ids=[],
            )
            unmatched.append(unmatched_goal)

    return unmatched


def _find_matching_tasks(goal: ExtractedGoal, tasks: list[Task]) -> list[str]:
    """Find tasks that support a given goal.

    Matching criteria:
    1. Task title contains significant words from goal
    2. Task tags match goal keywords
    3. Task description references goal

    Args:
        goal: The goal to match
        tasks: Tasks to search

    Returns:
        List of matching task IDs
    """
    matching_ids: list[str] = []

    # Extract keywords from goal (words > 3 chars, not stopwords)
    goal_keywords = _extract_keywords(goal.text)

    if not goal_keywords:
        return []

    for task in tasks:
        # Build searchable text
        search_text = f"{task.name} {task.description or ''}".lower()
        task_tags = set(t.lower() for t in (task.tags or []))

        # Check for keyword matches
        matches = 0
        for keyword in goal_keywords:
            if keyword in search_text or keyword in task_tags:
                matches += 1

        # Require at least one significant keyword match
        # or multiple partial matches
        if matches >= 1:
            matching_ids.append(task.id)

    return matching_ids


def _detect_focus_conflicts(
    context: PlanContext,
    categories: list[TaskCategory],
) -> list[str]:
    """Detect conflicts between focus mode and task categories.

    Args:
        context: Planning context with focus mode
        categories: Task categories with alignment info

    Returns:
        List of human-readable conflict descriptions
    """
    conflicts: list[str] = []

    if context.focus.mode == FocusMode.UNKNOWN:
        return conflicts

    # Calculate percentage of unaligned tasks
    total_tasks = sum(c.task_count for c in categories)
    if total_tasks == 0:
        return conflicts

    unaligned_tasks = sum(c.task_count for c in categories if not c.is_aligned)
    unaligned_percent = (unaligned_tasks / total_tasks) * 100

    # Threshold for conflict: >30% unaligned
    if unaligned_percent > 30:
        # Find the largest unaligned category
        unaligned_categories = [c for c in categories if not c.is_aligned]
        if unaligned_categories:
            largest = max(unaligned_categories, key=lambda c: c.task_count)
            conflicts.append(
                f'Focus mode is "{context.focus.mode.value.title()}" but '
                f"{largest.task_count} {largest.name.lower()} tasks ({int(unaligned_percent)}%) scheduled')"
            )

    # Check for specific mode conflicts
    if context.focus.mode == FocusMode.SHIPPING:
        # In shipping mode, exploratory/learning tasks are conflicts
        exploratory_count = sum(
            c.task_count
            for c in categories
            if c.name.lower() in ("learning", "exploring", "research")
            and not c.is_aligned
        )
        if exploratory_count > 3:
            conflicts.append(
                f"Shipping mode but {exploratory_count} exploratory/learning tasks scheduled"
            )

    elif context.focus.mode == FocusMode.RECOVERY:
        # In recovery mode, high-intensity work is a conflict
        work_count = sum(
            c.task_count
            for c in categories
            if c.name.lower() in ("development", "business", "research")
        )
        if work_count > 5:
            conflicts.append(
                f"Recovery mode but {work_count} high-intensity work tasks scheduled"
            )

    return conflicts


def _detect_schedule_issues(
    tasks: list[Task],
    start_date: date,
    end_date: date,
) -> list[str]:
    """Detect schedule issues like overload or no buffer.

    Args:
        tasks: Tasks in planning window
        start_date: Start of planning window
        end_date: End of planning window

    Returns:
        List of human-readable issue descriptions
    """
    issues: list[str] = []

    # Count tasks per day
    tasks_by_day: dict[date, int] = {}
    current = start_date
    while current <= end_date:
        tasks_by_day[current] = 0
        current += timedelta(days=1)

    for task in tasks:
        if task.scheduled_date and start_date <= task.scheduled_date <= end_date:
            tasks_by_day[task.scheduled_date] = tasks_by_day.get(task.scheduled_date, 0) + 1

    # Check for overloaded days (>6 tasks)
    overloaded_days = [d for d, count in tasks_by_day.items() if count > 6]
    if overloaded_days:
        day_names = [d.strftime("%A") for d in sorted(overloaded_days)]
        if len(day_names) == 1:
            issues.append(f"{day_names[0]} is overloaded ({tasks_by_day[overloaded_days[0]]} tasks)")
        else:
            issues.append(f"{', '.join(day_names)} are overloaded (>6 tasks each)")

    # Check for buffer time (at least one light day)
    light_days = [d for d, count in tasks_by_day.items() if count <= 2]
    total_days = (end_date - start_date).days + 1
    if total_days >= 7 and len(light_days) == 0:
        issues.append("No buffer time scheduled (no light days in the week)")

    # Check for weekend overload (if planning includes weekends)
    weekend_dates = [d for d in tasks_by_day.keys() if d.weekday() >= 5]
    weekend_tasks = sum(tasks_by_day.get(d, 0) for d in weekend_dates)
    if weekend_tasks > 6:
        issues.append(f"Weekend is packed with {weekend_tasks} tasks")

    return issues


def _extract_keywords(text: str) -> set[str]:
    """Extract significant keywords from text.

    Args:
        text: Text to extract from

    Returns:
        Set of lowercase keywords
    """
    # Common words to ignore
    stopwords = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "this", "that", "these", "those", "is",
        "are", "was", "were", "be", "been", "being", "have", "has", "had",
        "do", "does", "did", "will", "would", "could", "should", "may",
        "might", "must", "shall", "can", "need", "dare", "ought", "used",
        "my", "your", "his", "her", "its", "our", "their", "what", "which",
        "who", "whom", "when", "where", "why", "how", "all", "each", "every",
        "week", "month", "day", "today", "tomorrow", "year", "time",
    }

    keywords: set[str] = set()
    words = re.findall(r"\b[a-zA-Z]+\b", text.lower())

    for word in words:
        if len(word) > 3 and word not in stopwords:
            keywords.add(word)

    return keywords
