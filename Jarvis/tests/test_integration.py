"""Integration tests for Jarvis with AnyType.

These tests require AnyType Desktop to be running with at least one space.
They are skipped if AnyType is not available.
"""

import os
from datetime import date, timedelta

import pytest

# Check if we can run integration tests
ANYTYPE_AVAILABLE = os.environ.get("JARVIS_INTEGRATION_TESTS", "").lower() == "true"
SKIP_REASON = (
    "Integration tests require AnyType Desktop running. "
    "Set JARVIS_INTEGRATION_TESTS=true to enable."
)


@pytest.mark.skipif(not ANYTYPE_AVAILABLE, reason=SKIP_REASON)
class TestAnyTypeIntegration:
    """Integration tests that require AnyType Desktop."""

    @pytest.fixture
    def client(self):
        """Create and connect an AnyType client."""
        from jarvis.anytype_client import AnyTypeClient

        client = AnyTypeClient()
        client.connect()
        yield client

    @pytest.fixture
    def space_id(self, client):
        """Get the default space ID."""
        return client.get_default_space()

    def test_connect_to_anytype(self, client):
        """Test that we can connect to AnyType."""
        # If we get here without error, connection succeeded
        assert client._client is not None

    def test_get_default_space(self, client, space_id):
        """Test that we can get the default space."""
        assert space_id is not None
        assert isinstance(space_id, str)
        assert len(space_id) > 0

    def test_get_tasks_in_range(self, client, space_id):
        """Test that we can fetch tasks from AnyType."""
        start = date.today()
        end = start + timedelta(days=14)

        tasks = client.get_tasks_in_range(space_id, start, end)

        # Tasks should be a list (possibly empty)
        assert isinstance(tasks, list)

        # If there are tasks, verify their structure
        for task in tasks:
            assert hasattr(task, "id")
            assert hasattr(task, "name")
            assert hasattr(task, "scheduled_date")
            assert hasattr(task, "is_moveable")


@pytest.mark.skipif(not ANYTYPE_AVAILABLE, reason=SKIP_REASON)
class TestEndToEndWorkflow:
    """End-to-end workflow tests."""

    def test_analyze_workflow(self):
        """Test the full analyze workflow."""
        from jarvis.analyzer import analyze_workload
        from jarvis.anytype_client import AnyTypeClient

        # Connect to AnyType
        client = AnyTypeClient()
        client.connect()
        space_id = client.get_default_space()

        # Get tasks
        start = date.today()
        end = start + timedelta(days=14)
        tasks = client.get_tasks_in_range(space_id, start, end)

        # Analyze workload
        analysis = analyze_workload(tasks, start, end)

        # Verify analysis structure
        assert analysis.start_date == start
        assert analysis.end_date == end
        assert len(analysis.days) == 15  # 15 days inclusive
        assert analysis.total_moveable >= 0
        assert analysis.total_immovable >= 0

    def test_bar_movement_respected(self):
        """Test that bar_movement tasks are never suggested for moving."""
        from jarvis.analyzer import get_moveable_tasks_on_day
        from jarvis.anytype_client import AnyTypeClient

        client = AnyTypeClient()
        client.connect()
        space_id = client.get_default_space()

        start = date.today()
        end = start + timedelta(days=14)
        tasks = client.get_tasks_in_range(space_id, start, end)

        # Get moveable tasks for each day
        for day_offset in range(15):
            target_date = start + timedelta(days=day_offset)
            moveable = get_moveable_tasks_on_day(tasks, target_date)

            # No moveable task should have bar_movement tag
            for task in moveable:
                assert "bar_movement" not in task.tags, (
                    f"Task '{task.name}' has bar_movement but was returned as moveable"
                )


@pytest.mark.skipif(not ANYTYPE_AVAILABLE, reason=SKIP_REASON)
class TestContextIntegration:
    """Test context loading with real files."""

    def test_load_real_context(self):
        """Test loading context from the actual context folder."""
        from pathlib import Path

        from jarvis.context_reader import get_context_summary, load_context

        # Load from actual context folder
        context_path = Path(__file__).parent.parent / "context"
        context = load_context(context_path)

        # Should have loaded something
        summary = get_context_summary(context)

        # At least the core files should exist
        assert "preferences.md" in summary
        assert "constraints.md" in summary

        # to_prompt_context should work
        prompt_context = context.to_prompt_context()
        assert isinstance(prompt_context, str)
