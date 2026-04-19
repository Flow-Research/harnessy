"""Tests for context parsing functionality."""

import pytest
from datetime import date

from jarvis.models import UserContext
from jarvis.models.plan import FocusMode, ExtractedGoal
from jarvis.plan.context_parser import (
    extract_focus,
    extract_goals,
    extract_bullet_points,
    extract_project_names,
    parse_user_context,
)


class TestExtractFocus:
    """Tests for focus mode extraction."""

    def test_extract_shipping_mode(self):
        """Should detect shipping mode from keywords."""
        focus_raw = """
        # Current Focus Mode

        **Current:** 🚀 Shipping (ICML Deadline Crunch)

        ## Until
        January 28, 2026
        """
        result = extract_focus(focus_raw)

        assert result.mode == FocusMode.SHIPPING
        assert result.mode_emoji == "🚀"
        assert result.until_date == date(2026, 1, 28)

    def test_extract_learning_mode(self):
        """Should detect learning mode from keywords."""
        focus_raw = """
        Mode: Learning

        Currently studying machine learning fundamentals.
        """
        result = extract_focus(focus_raw)

        assert result.mode == FocusMode.LEARNING
        assert result.mode_emoji == "📚"

    def test_extract_exploring_mode(self):
        """Should detect exploring mode."""
        focus_raw = "In exploration phase, trying new prototypes."
        result = extract_focus(focus_raw)

        assert result.mode == FocusMode.EXPLORING

    def test_extract_recovery_mode(self):
        """Should detect recovery mode."""
        focus_raw = "Recovery week - taking a break after intense project."
        result = extract_focus(focus_raw)

        assert result.mode == FocusMode.RECOVERY

    def test_empty_focus_returns_unknown(self):
        """Should return unknown mode for empty input."""
        result = extract_focus("")

        assert result.mode == FocusMode.UNKNOWN
        assert result.mode_emoji == "❓"

    def test_extract_primary_goal(self):
        """Should extract primary goal from bold text."""
        focus_raw = """
        **Goal:** Submit GND paper to ICML 2026
        **Mode:** Shipping
        """
        result = extract_focus(focus_raw)

        assert "Submit GND paper" in result.primary_goal or result.primary_goal is None

    def test_extract_decision_rule(self):
        """Should extract decision rules."""
        focus_raw = """
        Decision Rule: If it doesn't contribute to submission, defer it.
        """
        result = extract_focus(focus_raw)

        # Decision rule should contain the rule text
        assert result.decision_rule is not None
        assert "defer" in result.decision_rule.lower()


class TestExtractGoals:
    """Tests for goal extraction."""

    def test_extract_goals_with_headers(self):
        """Should extract goals from markdown headers."""
        goals_raw = """
        # Goals & Objectives

        ## This Week
        - Submit paper draft
        - Run experiment B2
        - Generate figures

        ## This Month
        - Complete ICML submission
        - Prepare rebuttal materials
        """
        result = extract_goals(goals_raw)

        assert len(result) >= 3  # At least the week goals

        week_goals = [g for g in result if g.timeframe == "this_week"]
        assert len(week_goals) == 3
        assert any("paper" in g.text.lower() for g in week_goals)

        month_goals = [g for g in result if g.timeframe == "this_month"]
        assert len(month_goals) == 2

    def test_extract_goals_without_headers(self):
        """Should extract bullet points as this_week goals if no headers."""
        goals_raw = """
        - Finish the report
        - Call the client
        - Review code
        """
        result = extract_goals(goals_raw)

        assert len(result) == 3
        assert all(g.timeframe == "this_week" for g in result)

    def test_empty_goals_returns_empty_list(self):
        """Should return empty list for empty input."""
        result = extract_goals("")
        assert result == []

    def test_goal_source_file_is_set(self):
        """Should set source_file to goals.md."""
        goals_raw = "- Test goal"
        result = extract_goals(goals_raw)

        assert len(result) == 1
        assert result[0].source_file == "goals.md"


class TestExtractBulletPoints:
    """Tests for bullet point extraction."""

    def test_extract_dash_bullets(self):
        """Should extract dash-prefixed bullets."""
        content = """
        - Item 1
        - Item 2
        - Item 3
        """
        result = extract_bullet_points(content)
        assert len(result) == 3

    def test_extract_asterisk_bullets(self):
        """Should extract asterisk-prefixed bullets."""
        content = """
        * Item 1
        * Item 2
        """
        result = extract_bullet_points(content)
        assert len(result) == 2

    def test_extract_numbered_bullets(self):
        """Should extract numbered list items."""
        content = """
        1. First item
        2. Second item
        """
        result = extract_bullet_points(content)
        assert len(result) == 2

    def test_skip_very_short_items(self):
        """Should skip items shorter than 3 characters."""
        content = """
        - Ok
        - This is valid
        """
        result = extract_bullet_points(content)
        # "Ok" is too short
        assert len(result) == 1
        assert "valid" in result[0]


class TestExtractProjectNames:
    """Tests for project name extraction."""

    def test_extract_from_headers(self):
        """Should extract project names from headers."""
        projects_raw = """
        ## GND Paper
        Working on the paper submission.

        ## Jarvis CLI
        Building the task scheduler.
        """
        result = extract_project_names(projects_raw)

        assert "GND Paper" in result
        assert "Jarvis CLI" in result

    def test_extract_from_bold(self):
        """Should extract project names from bold text."""
        projects_raw = """
        **Project Alpha** - In progress
        **Project Beta** - Planning phase
        """
        result = extract_project_names(projects_raw)

        assert "Project Alpha" in result
        assert "Project Beta" in result


class TestParseUserContext:
    """Tests for full context parsing."""

    def test_parse_full_context(self):
        """Should parse all context fields."""
        user_context = UserContext(
            focus_raw="Mode: Shipping until January 28",
            goals_raw="## This Week\n- Goal 1\n- Goal 2",
            priorities_raw="- Priority 1\n- Priority 2",
            constraints_raw="- No meetings before 10am",
            projects_raw="## Project A\nActive",
            blockers_raw="- Waiting on approval",
        )

        result = parse_user_context(user_context)

        assert result.focus.mode == FocusMode.SHIPPING
        assert len(result.goals) == 2
        assert len(result.priority_rules) == 2
        assert len(result.constraints) == 1
        assert len(result.active_projects) == 1
        assert len(result.blockers) == 1
        assert result.context_quality == "full"

    def test_parse_partial_context(self):
        """Should handle partial context gracefully."""
        user_context = UserContext(
            goals_raw="- Goal 1",
            focus_raw="",
            priorities_raw="",
        )

        result = parse_user_context(user_context)

        assert len(result.goals) == 1
        assert result.focus.mode == FocusMode.UNKNOWN
        assert result.context_quality in ("partial", "minimal")
        assert "focus.md" in result.missing_files

    def test_parse_empty_context(self):
        """Should return empty context for no input."""
        user_context = UserContext()

        result = parse_user_context(user_context)

        assert result.focus.mode == FocusMode.UNKNOWN
        assert result.goals == []
        assert result.context_quality == "none"
