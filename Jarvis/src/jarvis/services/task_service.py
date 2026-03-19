"""Task service for task CRUD operations.

This module provides a high-level service for task operations that
handles capability checking, adapter selection, and error translation.
"""

from datetime import date

from ..adapters.base import KnowledgeBaseAdapter
from ..adapters.exceptions import NotSupportedError
from ..models import Task, Priority
from .adapter_service import get_adapter, ensure_connected, check_capability


class TaskService:
    """Service for task operations.

    Provides a high-level interface for task CRUD that works with
    any backend adapter and handles capability checking.

    Usage:
        service = TaskService()
        service.connect()
        task = service.create_task("Buy groceries", due_date=date.today())
    """

    def __init__(self, backend: str | None = None):
        """Initialize task service.

        Args:
            backend: Optional backend name override
        """
        self._adapter: KnowledgeBaseAdapter | None = None
        self._backend = backend

    @property
    def adapter(self) -> KnowledgeBaseAdapter:
        """Get the adapter instance, creating if needed."""
        if self._adapter is None:
            self._adapter = get_adapter(self._backend)
        return self._adapter

    @property
    def is_connected(self) -> bool:
        """Check if connected to backend."""
        return self._adapter is not None and self._adapter.is_connected()

    def connect(self) -> None:
        """Connect to the backend."""
        ensure_connected(self.adapter)

    def disconnect(self) -> None:
        """Disconnect from the backend."""
        if self._adapter is not None and self._adapter.is_connected():
            self._adapter.disconnect()

    def _check_tasks_capability(self) -> None:
        """Check if tasks capability is supported.

        Raises:
            NotSupportedError: If tasks are not supported
        """
        if not check_capability(self.adapter, "tasks"):
            raise NotSupportedError(
                f"Backend '{self.adapter.backend_name}' does not support tasks",
                backend=self.adapter.backend_name,
                capability="tasks",
            )

    def create_task(
        self,
        title: str,
        space_id: str | None = None,
        due_date: date | None = None,
        priority: Priority | None = None,
        tags: list[str] | None = None,
        description: str | None = None,
    ) -> Task:
        """Create a new task.

        Args:
            title: Task title
            space_id: Optional space ID (uses default if not provided)
            due_date: Optional due date
            priority: Optional priority level
            tags: Optional list of tag names
            description: Optional description

        Returns:
            Created Task object

        Raises:
            NotSupportedError: If tasks not supported
            ConnectionError: If not connected
        """
        self._check_tasks_capability()

        if space_id is None:
            space_id = self.adapter.get_default_space()

        return self.adapter.create_task(
            space_id=space_id,
            title=title,
            due_date=due_date,
            priority=priority,
            tags=tags,
            description=description,
        )

    def get_task(self, task_id: str, space_id: str | None = None) -> Task:
        """Get a single task by ID.

        Args:
            task_id: Task identifier
            space_id: Optional space ID (uses default if not provided)

        Returns:
            Task object

        Raises:
            NotFoundError: If task doesn't exist
            NotSupportedError: If tasks not supported
        """
        self._check_tasks_capability()

        if space_id is None:
            space_id = self.adapter.get_default_space()

        return self.adapter.get_task(space_id, task_id)

    def get_tasks(
        self,
        space_id: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        include_done: bool = False,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Task]:
        """Get tasks with optional filters.

        Args:
            space_id: Optional space ID (uses default if not provided)
            start_date: Filter tasks due on or after this date
            end_date: Filter tasks due on or before this date
            include_done: Include completed tasks
            limit: Maximum number of tasks to return
            offset: Number of tasks to skip

        Returns:
            List of Task objects

        Raises:
            NotSupportedError: If tasks not supported
        """
        self._check_tasks_capability()

        if space_id is None:
            space_id = self.adapter.get_default_space()

        return self.adapter.get_tasks(
            space_id=space_id,
            start_date=start_date,
            end_date=end_date,
            include_done=include_done,
            limit=limit,
            offset=offset,
        )

    def update_task(
        self,
        task_id: str,
        space_id: str | None = None,
        title: str | None = None,
        due_date: date | None = None,
        priority: Priority | None = None,
        tags: list[str] | None = None,
        description: str | None = None,
        is_done: bool | None = None,
    ) -> Task:
        """Update an existing task.

        Args:
            task_id: Task identifier
            space_id: Optional space ID (uses default if not provided)
            title: New title (None to keep existing)
            due_date: New due date (None to keep existing)
            priority: New priority (None to keep existing)
            tags: New tags (None to keep existing)
            description: New description (None to keep existing)
            is_done: New completion status (None to keep existing)

        Returns:
            Updated Task object

        Raises:
            NotFoundError: If task doesn't exist
            NotSupportedError: If tasks not supported
        """
        self._check_tasks_capability()

        if space_id is None:
            space_id = self.adapter.get_default_space()

        return self.adapter.update_task(
            space_id=space_id,
            task_id=task_id,
            title=title,
            due_date=due_date,
            priority=priority,
            tags=tags,
            description=description,
            is_done=is_done,
        )

    def delete_task(self, task_id: str, space_id: str | None = None) -> bool:
        """Delete a task.

        Args:
            task_id: Task identifier
            space_id: Optional space ID (uses default if not provided)

        Returns:
            True if deleted successfully

        Raises:
            NotFoundError: If task doesn't exist
            NotSupportedError: If tasks not supported
        """
        self._check_tasks_capability()

        if space_id is None:
            space_id = self.adapter.get_default_space()

        return self.adapter.delete_task(space_id, task_id)

    def complete_task(self, task_id: str, space_id: str | None = None) -> Task:
        """Mark a task as complete.

        Args:
            task_id: Task identifier
            space_id: Optional space ID (uses default if not provided)

        Returns:
            Updated Task object

        Raises:
            NotFoundError: If task doesn't exist
            NotSupportedError: If tasks not supported
        """
        return self.update_task(task_id, space_id=space_id, is_done=True)
