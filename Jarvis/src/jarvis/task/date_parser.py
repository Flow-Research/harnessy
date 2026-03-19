"""Natural language date parsing for task creation."""

from datetime import date
from typing import Optional

import dateparser


def parse_due_date(input_str: str) -> Optional[date]:
    """Parse natural language date string to date object.

    Supports formats like:
    - Relative: today, tomorrow, next monday
    - Periods: next week, in 3 days, in 2 weeks
    - Absolute: 2025-02-15, feb 15, february 15

    Args:
        input_str: Date string like "tomorrow", "next friday", "2025-02-15"

    Returns:
        Parsed date or None if parsing fails

    Examples:
        >>> parse_due_date("tomorrow")
        date(2025, 1, 25)
        >>> parse_due_date("next friday")
        date(2025, 1, 31)
        >>> parse_due_date("invalid")
        None
    """
    if not input_str or not input_str.strip():
        return None

    # Configure dateparser settings
    settings = {
        "PREFER_DATES_FROM": "future",  # "next friday" = upcoming friday
        "RETURN_AS_TIMEZONE_AWARE": False,
    }

    try:
        result = dateparser.parse(input_str.strip(), settings=settings)
        if result:
            return result.date()
        return None
    except Exception:
        return None


def is_past_date(d: date) -> bool:
    """Check if date is in the past.

    Args:
        d: Date to check

    Returns:
        True if date is before today
    """
    return d < date.today()
