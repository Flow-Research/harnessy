"""Context parsing for weekly planning.

This module extracts structured planning data from raw context files
using a hybrid approach: structured extraction for common patterns,
with AI fallback for unstructured content.
"""

import re
from datetime import date
from typing import Literal

from ..context_reader import load_context
from ..models import UserContext
from ..models.plan import (
    ExtractedGoal,
    FocusMode,
    FocusSummary,
    FOCUS_MODE_EMOJI,
    PlanContext,
)


def parse_context() -> PlanContext:
    """Load and parse context files into structured planning data.

    Returns:
        PlanContext with extracted structure and raw content
    """
    user_context = load_context()
    return parse_user_context(user_context)


def parse_user_context(user_context: UserContext) -> PlanContext:
    """Parse UserContext into structured PlanContext.

    Args:
        user_context: Raw context from context_reader

    Returns:
        PlanContext with extracted structure
    """
    # Track which files are missing
    missing_files: list[str] = []

    # Extract focus
    focus = FocusSummary.empty()
    if user_context.focus_raw.strip():
        focus = extract_focus(user_context.focus_raw)
    else:
        missing_files.append("focus.md")

    # Extract goals
    goals: list[ExtractedGoal] = []
    if user_context.goals_raw.strip():
        goals = extract_goals(user_context.goals_raw)
    else:
        missing_files.append("goals.md")

    # Extract priority rules
    priority_rules: list[str] = []
    if user_context.priorities_raw.strip():
        priority_rules = extract_bullet_points(user_context.priorities_raw)
    else:
        missing_files.append("priorities.md")

    # Extract constraints
    constraints: list[str] = []
    if user_context.constraints_raw.strip():
        constraints = extract_bullet_points(user_context.constraints_raw)
    else:
        missing_files.append("constraints.md")

    # Extract active projects
    active_projects: list[str] = []
    if user_context.projects_raw.strip():
        active_projects = extract_project_names(user_context.projects_raw)
    else:
        missing_files.append("projects.md")

    # Extract blockers
    blockers: list[str] = []
    if user_context.blockers_raw.strip():
        blockers = extract_bullet_points(user_context.blockers_raw)
    else:
        missing_files.append("blockers.md")

    # Determine context quality
    context_quality = _determine_quality(user_context, missing_files)

    return PlanContext(
        focus=focus,
        goals=goals,
        priority_rules=priority_rules,
        constraints=constraints,
        active_projects=active_projects,
        blockers=blockers,
        raw_context=user_context.to_prompt_context(),
        context_quality=context_quality,
        missing_files=missing_files,
    )


def extract_focus(focus_raw: str) -> FocusSummary:
    """Extract focus mode from focus.md content.

    Strategy:
    1. Look for mode keywords (Shipping, Learning, etc.)
    2. Parse "until" date if present
    3. Extract decision rules

    Args:
        focus_raw: Raw content of focus.md

    Returns:
        FocusSummary with extracted data
    """
    mode = FocusMode.UNKNOWN
    primary_goal: str | None = None
    decision_rule: str | None = None
    until_date: date | None = None

    # Normalize text for searching
    text_lower = focus_raw.lower()

    # Try to detect mode from keywords
    mode_patterns = [
        (r"shipping|deadline|crunch|submit", FocusMode.SHIPPING),
        (r"learning|study|research|reading", FocusMode.LEARNING),
        (r"explor|experiment|discover|prototype", FocusMode.EXPLORING),
        (r"recovery|rest|break|recharge", FocusMode.RECOVERY),
    ]

    for pattern, focus_mode in mode_patterns:
        if re.search(pattern, text_lower):
            mode = focus_mode
            break

    # Also check for explicit mode declarations (only override if valid)
    mode_match = re.search(
        r"(?:mode|current|status)[:\s]*[🚀📚🔍🌿]?\s*(\w+)",
        text_lower,
    )
    if mode_match:
        detected = FocusMode.from_string(mode_match.group(1))
        if detected != FocusMode.UNKNOWN:
            mode = detected

    # Extract "until" date
    until_patterns = [
        r"until[:\s]+([A-Za-z]+\s+\d{1,2}(?:,?\s*\d{4})?)",
        r"deadline[:\s]+([A-Za-z]+\s+\d{1,2}(?:,?\s*\d{4})?)",
        r"by[:\s]+([A-Za-z]+\s+\d{1,2}(?:,?\s*\d{4})?)",
    ]
    for pattern in until_patterns:
        match = re.search(pattern, focus_raw, re.IGNORECASE)
        if match:
            until_date = _parse_date_string(match.group(1))
            break

    # Extract primary goal (often the first bold or header item)
    goal_patterns = [
        r"\*\*(?:Goal|Primary|Focus)[:\s]*\*\*[:\s]*(.+?)(?:\n|$)",
        r"(?:^|\n)#+ .*?[:\s]+(.+?)(?:\n|$)",
        r"(?:Goal|Primary|Focus)[:\s]+(.+?)(?:\n|$)",
    ]
    for pattern in goal_patterns:
        match = re.search(pattern, focus_raw, re.IGNORECASE | re.MULTILINE)
        if match:
            primary_goal = match.group(1).strip()
            break

    # Extract decision rule
    rule_patterns = [
        r"(?:decision rule|rule|principle)[:\s]+(.+?)(?:\n|$)",
        r"if it (?:doesn't|does not|don't)(.+?)(?:\n|$)",
    ]
    for pattern in rule_patterns:
        match = re.search(pattern, focus_raw, re.IGNORECASE)
        if match:
            decision_rule = match.group(0).strip()
            break

    return FocusSummary(
        mode=mode,
        mode_emoji=FOCUS_MODE_EMOJI.get(mode, "❓"),
        primary_goal=primary_goal,
        decision_rule=decision_rule,
        until_date=until_date,
    )


def extract_goals(goals_raw: str) -> list[ExtractedGoal]:
    """Extract goals from goals.md content.

    Strategy:
    1. Look for ## This Week, ## This Month headers
    2. Extract bullet points under headers
    3. Parse frontmatter if present

    Args:
        goals_raw: Raw content of goals.md

    Returns:
        List of ExtractedGoal objects
    """
    goals: list[ExtractedGoal] = []

    # Check for YAML frontmatter
    frontmatter_match = re.match(r"^---\n(.+?)\n---", goals_raw, re.DOTALL)
    if frontmatter_match:
        goals.extend(_parse_goals_frontmatter(frontmatter_match.group(1)))

    # Extract goals by timeframe headers
    timeframe_patterns: list[tuple[str, Literal["this_week", "this_month", "this_quarter", "ongoing"]]] = [
        (r"##?\s*this\s*week", "this_week"),
        (r"##?\s*this\s*month", "this_month"),
        (r"##?\s*this\s*quarter", "this_quarter"),
        (r"##?\s*(?:ongoing|continuous|always)", "ongoing"),
    ]

    for pattern, timeframe in timeframe_patterns:
        section_match = re.search(
            f"{pattern}[^\n]*\n(.*?)(?=\n\\s*##|$)",
            goals_raw,
            re.IGNORECASE | re.DOTALL,
        )
        if section_match:
            section_content = section_match.group(1)
            bullets = _extract_bullets(section_content)
            for bullet in bullets:
                goals.append(
                    ExtractedGoal(
                        text=bullet,
                        timeframe=timeframe,
                        source_file="goals.md",
                    )
                )

    # If no structured headers found, treat all bullets as this_week
    if not goals:
        bullets = _extract_bullets(goals_raw)
        for bullet in bullets:
            goals.append(
                ExtractedGoal(
                    text=bullet,
                    timeframe="this_week",
                    source_file="goals.md",
                )
            )

    return goals


def extract_bullet_points(content: str) -> list[str]:
    """Extract bullet points from markdown content.

    Args:
        content: Raw markdown content

    Returns:
        List of bullet point strings
    """
    return _extract_bullets(content)


def extract_project_names(projects_raw: str) -> list[str]:
    """Extract project names from projects.md.

    Looks for:
    - Headers (## Project Name)
    - Bold items (**Project Name**)
    - List items with project keywords

    Args:
        projects_raw: Raw content of projects.md

    Returns:
        List of project names
    """
    projects: list[str] = []

    # Extract from headers (handle optional leading whitespace)
    header_matches = re.findall(r"^\s*##?\s+(.+?)(?:\s*[-–—]|$)", projects_raw, re.MULTILINE)
    projects.extend(header_matches)

    # Extract from bold items
    bold_matches = re.findall(r"\*\*([^*]+)\*\*", projects_raw)
    for match in bold_matches:
        if match not in projects and len(match) < 50:  # Avoid long descriptions
            projects.append(match)

    return projects


def _determine_quality(
    user_context: UserContext,
    missing_files: list[str],  # noqa: ARG001 - kept for potential future use
) -> Literal["full", "partial", "minimal", "none"]:
    """Determine context quality based on available files.

    Args:
        user_context: The loaded user context
        missing_files: List of missing file names (for future enhancement)

    Returns:
        Quality level string
    """
    _ = missing_files  # Acknowledge parameter for future use
    # Count files with content
    content_count = sum(
        1
        for field in [
            user_context.goals_raw,
            user_context.focus_raw,
            user_context.priorities_raw,
            user_context.constraints_raw,
            user_context.projects_raw,
            user_context.patterns_raw,
        ]
        if field.strip()
    )

    if content_count >= 4:
        return "full"
    elif content_count >= 2:
        return "partial"
    elif content_count >= 1:
        return "minimal"
    else:
        return "none"


def _extract_bullets(content: str) -> list[str]:
    """Extract bullet points from markdown.

    Args:
        content: Markdown text

    Returns:
        List of bullet text (without the bullet marker)
    """
    bullets: list[str] = []

    # Match various bullet styles: -, *, •, numbered
    bullet_pattern = r"^[\s]*(?:[-*•]|\d+\.)\s+(.+?)$"
    matches = re.findall(bullet_pattern, content, re.MULTILINE)

    for match in matches:
        text = match.strip()
        if text and len(text) > 2:  # Skip very short items
            bullets.append(text)

    return bullets


def _parse_date_string(date_str: str) -> date | None:
    """Parse a date string like 'January 28' or 'Jan 28, 2026'.

    Args:
        date_str: Date string to parse

    Returns:
        date object or None if parsing fails
    """
    import calendar

    # Clean up the string
    date_str = date_str.strip().replace(",", "")

    # Month name to number mapping
    month_names = {name.lower(): num for num, name in enumerate(calendar.month_name) if num}
    month_abbr = {name.lower(): num for num, name in enumerate(calendar.month_abbr) if num}

    try:
        # Try various formats
        parts = date_str.split()
        if len(parts) >= 2:
            month_str = parts[0].lower()
            day = int(parts[1])
            year = int(parts[2]) if len(parts) > 2 else date.today().year

            month = month_names.get(month_str) or month_abbr.get(month_str[:3])
            if month:
                return date(year, month, day)
    except (ValueError, IndexError):
        pass

    return None


def _parse_goals_frontmatter(frontmatter: str) -> list[ExtractedGoal]:
    """Parse goals from YAML frontmatter.

    Args:
        frontmatter: YAML content between --- markers

    Returns:
        List of ExtractedGoal objects
    """
    goals: list[ExtractedGoal] = []

    # Simple YAML parsing for common patterns
    timeframe_keys = {
        "this_week": "this_week",
        "thisweek": "this_week",
        "week": "this_week",
        "this_month": "this_month",
        "thismonth": "this_month",
        "month": "this_month",
    }

    current_timeframe: Literal["this_week", "this_month", "this_quarter", "ongoing"] = "this_week"

    for line in frontmatter.split("\n"):
        line = line.strip()

        # Check for timeframe key
        for key, timeframe in timeframe_keys.items():
            if line.lower().startswith(key):
                current_timeframe = timeframe  # type: ignore
                break

        # Check for list item
        if line.startswith("- "):
            goal_text = line[2:].strip().strip('"\'')
            if goal_text:
                goals.append(
                    ExtractedGoal(
                        text=goal_text,
                        timeframe=current_timeframe,
                        source_file="goals.md",
                    )
                )

    return goals
