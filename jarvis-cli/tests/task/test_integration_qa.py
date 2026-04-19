"""QA Integration tests for task creation.

These tests require a running AnyType instance.
All created tasks are cleaned up after each test.
"""

from datetime import date, timedelta

import pytest

from jarvis.anytype_client import AnyTypeClient


@pytest.fixture
def client():
    """Create and connect an AnyType client."""
    client = AnyTypeClient()
    try:
        client.connect()
        return client
    except RuntimeError as e:
        pytest.skip(f"AnyType not available: {e}")


@pytest.fixture
def space_id(client):
    """Get the default space ID."""
    return client.get_default_space()


@pytest.fixture
def cleanup_tasks(client, space_id):
    """Fixture that tracks and cleans up created tasks."""
    created_task_ids = []

    yield created_task_ids

    # Cleanup: delete all created tasks
    for task_id in created_task_ids:
        try:
            client.delete_object(space_id, task_id)
        except Exception:
            pass  # Best effort cleanup


class TestTaskCreationQA:
    """QA tests for task creation feature."""

    def test_create_simple_task(self, client, space_id, cleanup_tasks):
        """QA-1: Create a simple task with just a title."""
        task_id = client.create_task(
            space_id=space_id,
            title="QA Test - Simple Task",
        )
        cleanup_tasks.append(task_id)

        assert task_id is not None
        assert len(task_id) > 0

    def test_create_task_with_due_date(self, client, space_id, cleanup_tasks):
        """QA-2: Create task with due date."""
        tomorrow = date.today() + timedelta(days=1)
        task_id = client.create_task(
            space_id=space_id,
            title="QA Test - Due Date Task",
            due_date=tomorrow,
        )
        cleanup_tasks.append(task_id)

        assert task_id is not None

    def test_create_task_with_priority(self, client, space_id, cleanup_tasks):
        """QA-3: Create task with priority."""
        task_id = client.create_task(
            space_id=space_id,
            title="QA Test - Priority Task",
            priority="high",
        )
        cleanup_tasks.append(task_id)

        assert task_id is not None

    def test_create_task_with_tags(self, client, space_id, cleanup_tasks):
        """QA-4: Create task with tags."""
        task_id = client.create_task(
            space_id=space_id,
            title="QA Test - Tagged Task",
            tags=["qa-test", "integration"],
        )
        cleanup_tasks.append(task_id)

        assert task_id is not None

    def test_create_task_with_description(self, client, space_id, cleanup_tasks):
        """QA-5: Create task with description."""
        task_id = client.create_task(
            space_id=space_id,
            title="QA Test - Description Task",
            description="This is a test description.\n\nWith multiple paragraphs.",
        )
        cleanup_tasks.append(task_id)

        assert task_id is not None

    def test_create_full_task(self, client, space_id, cleanup_tasks):
        """QA-6: Create task with all fields populated."""
        next_week = date.today() + timedelta(days=7)
        task_id = client.create_task(
            space_id=space_id,
            title="QA Test - Full Task",
            due_date=next_week,
            priority="medium",
            tags=["qa-test", "full-test"],
            description="Complete task with all fields set.",
        )
        cleanup_tasks.append(task_id)

        assert task_id is not None

    def test_created_task_appears_in_search(self, client, space_id, cleanup_tasks):
        """QA-7: Verify created task appears in task search."""
        unique_title = f"QA Unique Task {date.today().isoformat()}"
        today = date.today()

        task_id = client.create_task(
            space_id=space_id,
            title=unique_title,
            due_date=today,
        )
        cleanup_tasks.append(task_id)

        # Search for the task
        tasks = client.get_tasks_in_range(
            space_id=space_id,
            start=today,
            end=today,
        )

        task_names = [t.name for t in tasks]
        assert unique_title in task_names, f"Task not found in search. Found: {task_names}"

    def test_task_priority_values(self, client, space_id, cleanup_tasks):
        """QA-8: Test all priority values work."""
        for priority in ["high", "medium", "low"]:
            task_id = client.create_task(
                space_id=space_id,
                title=f"QA Test - Priority {priority}",
                priority=priority,
            )
            cleanup_tasks.append(task_id)
            assert task_id is not None

    def test_task_with_special_characters_in_title(self, client, space_id, cleanup_tasks):
        """QA-9: Test special characters in title."""
        task_id = client.create_task(
            space_id=space_id,
            title='QA Test - Special "chars" & symbols <> @ #',
        )
        cleanup_tasks.append(task_id)

        assert task_id is not None

    def test_task_with_long_title(self, client, space_id, cleanup_tasks):
        """QA-10: Test with a moderately long title."""
        long_title = "QA Test - " + "x" * 100  # 110 chars total
        task_id = client.create_task(
            space_id=space_id,
            title=long_title,
        )
        cleanup_tasks.append(task_id)

        assert task_id is not None
