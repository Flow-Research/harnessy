"""Alignment scoring for weekly planning.

This module calculates how well scheduled tasks align with the user's
stated focus and goals using a multi-signal approach (FR-03.A).
"""

import re
from collections import defaultdict
from dataclasses import dataclass

from ..models import Task
from ..models.plan import (
    FocusMode,
    PlanContext,
    TaskCategory,
    TaskReality,
)
from datetime import date


# Category definitions with emojis
CATEGORY_CONFIG: dict[str, dict[str, str | list[str]]] = {
    "research": {"emoji": "🔬", "keywords": ["research", "experiment", "analysis", "study", "paper", "thesis"]},
    "business": {"emoji": "💼", "keywords": ["business", "meeting", "client", "sales", "revenue", "pitch"]},
    "development": {"emoji": "💻", "keywords": ["dev", "code", "implement", "build", "fix", "bug", "feature"]},
    "admin": {"emoji": "📝", "keywords": ["admin", "email", "invoice", "report", "form", "document"]},
    "maintenance": {"emoji": "🔧", "keywords": ["maintain", "update", "clean", "organize", "backup", "review"]},
    "learning": {"emoji": "📚", "keywords": ["learn", "course", "read", "tutorial", "practice", "skill"]},
    "personal": {"emoji": "🏠", "keywords": ["personal", "health", "family", "errand", "appointment"]},
    "other": {"emoji": "📦", "keywords": []},
}

# Focus mode to aligned categories mapping
FOCUS_ALIGNED_CATEGORIES: dict[FocusMode, set[str]] = {
    FocusMode.SHIPPING: {"development", "research"},
    FocusMode.LEARNING: {"learning", "research"},
    FocusMode.EXPLORING: {"research", "development", "learning"},
    FocusMode.RECOVERY: {"personal", "maintenance"},
    FocusMode.UNKNOWN: set(),  # No alignment preference
}


@dataclass
class AlignmentResult:
    """Result of alignment calculation."""

    score: float  # 0.0 - 1.0
    categories: list[TaskCategory]
    aligned_task_ids: list[str]
    unaligned_task_ids: list[str]


def calculate_alignment(
    tasks: list[Task],
    context: PlanContext,
) -> AlignmentResult:
    """Calculate alignment score and categorize tasks.

    Algorithm (FR-03.A):
    1. Tag match: task tags match focus/goal keywords
    2. Project match: task project in active projects
    3. Title match: task title contains goal keywords (fuzzy)
    4. Category match: task category aligns with focus mode

    Args:
        tasks: Tasks in planning window
        context: Parsed planning context

    Returns:
        AlignmentResult with score and categorized tasks
    """
    if not tasks:
        return AlignmentResult(
            score=0.0,
            categories=[],
            aligned_task_ids=[],
            unaligned_task_ids=[],
        )

    # Build keyword sets from context
    goal_keywords = _extract_keywords_from_goals(context.goals)
    focus_keywords = _get_focus_keywords(context.focus.mode)
    project_names = set(p.lower() for p in context.active_projects)

    # Aligned categories for this focus mode
    aligned_category_names = FOCUS_ALIGNED_CATEGORIES.get(context.focus.mode, set())

    # Categorize and score each task
    task_categories: dict[str, list[str]] = defaultdict(list)
    aligned_tasks: list[str] = []
    unaligned_tasks: list[str] = []

    for task in tasks:
        # Determine task category
        category = _categorize_task(task)
        task_categories[category].append(task.id)

        # Check alignment using multiple signals
        is_aligned = _check_task_alignment(
            task=task,
            goal_keywords=goal_keywords,
            focus_keywords=focus_keywords,
            project_names=project_names,
            aligned_categories=aligned_category_names,
            task_category=category,
        )

        if is_aligned:
            aligned_tasks.append(task.id)
        else:
            unaligned_tasks.append(task.id)

    # Calculate score
    total = len(tasks)
    aligned_count = len(aligned_tasks)
    score = aligned_count / total if total > 0 else 0.0

    # Build category objects
    categories = _build_categories(
        task_categories=task_categories,
        aligned_category_names=aligned_category_names,
    )

    return AlignmentResult(
        score=score,
        categories=categories,
        aligned_task_ids=aligned_tasks,
        unaligned_task_ids=unaligned_tasks,
    )


def build_task_reality(
    tasks: list[Task],
    alignment_result: AlignmentResult,
    start_date: date,
    end_date: date,
) -> TaskReality:
    """Build TaskReality from tasks and alignment result.

    Args:
        tasks: Tasks in planning window
        alignment_result: Result from calculate_alignment
        start_date: Start of planning window
        end_date: End of planning window

    Returns:
        TaskReality with full task analysis
    """
    # Group tasks by day
    tasks_by_day: dict[date, list[str]] = defaultdict(list)
    for task in tasks:
        if task.scheduled_date:
            tasks_by_day[task.scheduled_date].append(task.id)

    # Find overloaded and empty days
    overloaded_days: list[date] = []
    empty_days: list[date] = []

    current = start_date
    from datetime import timedelta

    while current <= end_date:
        day_task_count = len(tasks_by_day.get(current, []))
        if day_task_count > 6:
            overloaded_days.append(current)
        elif day_task_count == 0:
            empty_days.append(current)
        current += timedelta(days=1)

    return TaskReality(
        total_tasks=len(tasks),
        tasks_by_day=dict(tasks_by_day),
        tasks_by_category=alignment_result.categories,
        alignment_score=alignment_result.score,
        overloaded_days=overloaded_days,
        empty_days=empty_days,
    )


def _categorize_task(task: Task) -> str:
    """Determine the category of a task based on its content.

    Args:
        task: Task to categorize

    Returns:
        Category name (e.g., "research", "business", "admin")
    """
    # Build searchable text
    search_text = f"{task.name} {task.description or ''}".lower()

    # Check tags first (most explicit)
    task_tags = set(t.lower() for t in (task.tags or []))

    for category, config in CATEGORY_CONFIG.items():
        if category == "other":
            continue

        keywords = set(config["keywords"])

        # Check if any tag matches a keyword
        if task_tags & keywords:
            return category

        # Check if title/description contains keywords
        for keyword in keywords:
            if keyword in search_text:
                return category

    return "other"


def _check_task_alignment(
    task: Task,
    goal_keywords: set[str],
    focus_keywords: set[str],
    project_names: set[str],
    aligned_categories: set[str],
    task_category: str,
) -> bool:
    """Check if a task is aligned with user's focus and goals.

    Args:
        task: Task to check
        goal_keywords: Keywords from goals
        focus_keywords: Keywords from focus mode
        project_names: Active project names
        aligned_categories: Categories that align with focus
        task_category: The task's category

    Returns:
        True if task is aligned
    """
    # Build searchable text
    search_text = f"{task.name} {task.description or ''}".lower()
    task_tags = set(t.lower() for t in (task.tags or []))

    # Signal 1: Tag match with goal/focus keywords
    all_keywords = goal_keywords | focus_keywords
    if task_tags & all_keywords:
        return True

    # Signal 2: Project match
    for project in project_names:
        if project in search_text or project in task_tags:
            return True

    # Signal 3: Title contains goal keywords
    for keyword in goal_keywords:
        if len(keyword) > 3 and keyword in search_text:
            return True

    # Signal 4: Category aligns with focus mode
    if task_category in aligned_categories:
        return True

    return False


def _extract_keywords_from_goals(goals: list) -> set[str]:
    """Extract significant keywords from goals.

    Args:
        goals: List of ExtractedGoal objects

    Returns:
        Set of lowercase keywords
    """
    keywords: set[str] = set()

    # Common words to ignore
    stopwords = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "this", "that", "these", "those", "is",
        "are", "was", "were", "be", "been", "being", "have", "has", "had",
        "do", "does", "did", "will", "would", "could", "should", "may",
        "might", "must", "shall", "can", "need", "dare", "ought", "used",
        "my", "your", "his", "her", "its", "our", "their", "what", "which",
        "who", "whom", "when", "where", "why", "how", "all", "each", "every",
    }

    for goal in goals:
        # Extract words from goal text
        words = re.findall(r"\b[a-zA-Z]+\b", goal.text.lower())
        for word in words:
            if len(word) > 3 and word not in stopwords:
                keywords.add(word)

    return keywords


def _get_focus_keywords(mode: FocusMode) -> set[str]:
    """Get keywords associated with a focus mode.

    Args:
        mode: Focus mode

    Returns:
        Set of related keywords
    """
    focus_keywords: dict[FocusMode, set[str]] = {
        FocusMode.SHIPPING: {"ship", "release", "deploy", "launch", "submit", "deadline", "finish"},
        FocusMode.LEARNING: {"learn", "study", "course", "read", "practice", "understand"},
        FocusMode.EXPLORING: {"explore", "experiment", "prototype", "test", "try", "discover"},
        FocusMode.RECOVERY: {"rest", "recover", "break", "relax", "health", "personal"},
        FocusMode.UNKNOWN: set(),
    }
    return focus_keywords.get(mode, set())


def _build_categories(
    task_categories: dict[str, list[str]],
    aligned_category_names: set[str],
) -> list[TaskCategory]:
    """Build TaskCategory objects from categorized task IDs.

    Args:
        task_categories: Mapping of category name to task IDs
        aligned_category_names: Categories aligned with focus

    Returns:
        List of TaskCategory objects sorted by count
    """
    categories: list[TaskCategory] = []

    for category_name, task_ids in task_categories.items():
        config = CATEGORY_CONFIG.get(category_name, CATEGORY_CONFIG["other"])
        count = len(task_ids)

        # emoji is always a str in our config
        emoji_value = config.get("emoji", "📦")
        emoji = emoji_value if isinstance(emoji_value, str) else "📦"

        categories.append(
            TaskCategory(
                name=category_name.title(),
                emoji=emoji,
                task_ids=task_ids,
                task_count=count,
                is_aligned=category_name in aligned_category_names,
            )
        )

    # Sort by count descending
    categories.sort(key=lambda c: c.task_count, reverse=True)

    return categories
