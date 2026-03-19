"""Task creation service."""

from datetime import date
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from jarvis.anytype_client import AnyTypeClient


class TaskService:
    """Service for task operations.

    Provides a business logic layer between CLI and AnyType client.
    """

    def __init__(self, client: "AnyTypeClient") -> None:
        """Initialize with AnyType client.

        Args:
            client: Connected AnyType client instance
        """
        self._client = client

    def create_task(
        self,
        space_id: str,
        title: str,
        due_date: Optional[date] = None,
        priority: Optional[str] = None,
        tags: Optional[list[str]] = None,
        description: Optional[str] = None,
    ) -> str:
        """Create a task in AnyType.

        Args:
            space_id: AnyType space ID
            title: Task title
            due_date: Optional due date
            priority: Optional priority (high/medium/low)
            tags: Optional list of tag names
            description: Optional task description (markdown)

        Returns:
            Task object ID
        """
        return self._client.create_task(
            space_id=space_id,
            title=title,
            due_date=due_date,
            priority=priority,
            tags=tags,
            description=description,
        )
