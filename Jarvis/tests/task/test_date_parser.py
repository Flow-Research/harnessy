"""Tests for date parser module."""

from datetime import date, timedelta

import pytest

from jarvis.task.date_parser import is_past_date, parse_due_date


class TestParseDueDate:
    """Tests for parse_due_date function."""

    def test_parse_tomorrow(self) -> None:
        """Test parsing 'tomorrow'."""
        result = parse_due_date("tomorrow")
        assert result == date.today() + timedelta(days=1)

    def test_parse_today(self) -> None:
        """Test parsing 'today'."""
        result = parse_due_date("today")
        assert result == date.today()

    def test_parse_iso_date(self) -> None:
        """Test parsing ISO format date."""
        result = parse_due_date("2025-02-15")
        assert result == date(2025, 2, 15)

    def test_parse_natural_date(self) -> None:
        """Test parsing natural language date."""
        result = parse_due_date("feb 15")
        assert result is not None
        assert result.month == 2
        assert result.day == 15

    def test_parse_friday(self) -> None:
        """Test parsing 'friday'."""
        result = parse_due_date("friday")
        assert result is not None
        assert result.weekday() == 4  # Friday

    def test_parse_invalid_returns_none(self) -> None:
        """Test that invalid dates return None."""
        assert parse_due_date("not a date") is None
        assert parse_due_date("") is None
        assert parse_due_date("   ") is None

    def test_parse_in_3_days(self) -> None:
        """Test parsing 'in 3 days'."""
        result = parse_due_date("in 3 days")
        # Should be approximately 3 days from now
        assert result is not None
        assert result >= date.today()

    def test_parse_next_week(self) -> None:
        """Test parsing 'next week'."""
        result = parse_due_date("next week")
        assert result is not None
        assert result > date.today()


class TestIsPastDate:
    """Tests for is_past_date function."""

    def test_yesterday_is_past(self) -> None:
        """Test that yesterday is in the past."""
        yesterday = date.today() - timedelta(days=1)
        assert is_past_date(yesterday) is True

    def test_today_is_not_past(self) -> None:
        """Test that today is not in the past."""
        assert is_past_date(date.today()) is False

    def test_tomorrow_is_not_past(self) -> None:
        """Test that tomorrow is not in the past."""
        tomorrow = date.today() + timedelta(days=1)
        assert is_past_date(tomorrow) is False
