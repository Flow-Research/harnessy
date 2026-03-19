"""Protocol defining the interface all backend adapters must implement.

This module uses Python's Protocol (PEP 544) for structural subtyping,
allowing adapters to implement the interface without explicit inheritance.
"""

from datetime import date
from typing import Protocol, runtime_checkable

from ..models import BackendObject, JournalEntry, Priority, Space, Tag, Task


@runtime_checkable
class KnowledgeBaseAdapter(Protocol):
    """Protocol that all backend adapters must implement.

    Adapters provide a consistent interface for CRUD operations
    on tasks, journal entries, and tags across different backends.

    This Protocol uses structural subtyping - any class that implements
    all these methods is considered a valid adapter, without needing
    to explicitly inherit from this class.

    Usage:
        adapter = registry.get_adapter()
        adapter.connect()
        tasks = adapter.get_tasks(space_id)

    Example implementation:
        class MyAdapter:
            @property
            def capabilities(self) -> dict[str, bool]:
                return {"tasks": True, "journal": True, ...}

            @property
            def backend_name(self) -> str:
                return "my_backend"

            def connect(self) -> None:
                # Establish connection
                ...
    """

    # =========================================================================
    # Capability Declaration
    # =========================================================================

    @property
    def capabilities(self) -> dict[str, bool]:
        """Declare supported capabilities.

        Returns:
            Dict mapping capability names to support status.

        Required capability keys:
            - tasks: Task CRUD operations
            - journal: Journal entry CRUD operations
            - tags: Tag management
            - search: Full-text search
            - priorities: Task priority levels
            - due_dates: Task due dates
            - daily_notes: Automatic daily note creation
            - relations: Links between items
            - custom_properties: User-defined fields
        """
        ...

    @property
    def backend_name(self) -> str:
        """Return the backend identifier (e.g., 'anytype', 'notion')."""
        ...

    # =========================================================================
    # Connection Management
    # =========================================================================

    def connect(self) -> None:
        """Establish connection to the backend.

        Raises:
            ConnectionError: If connection cannot be established
            AuthError: If authentication fails
        """
        ...

    def disconnect(self) -> None:
        """Close connection to the backend gracefully."""
        ...

    def is_connected(self) -> bool:
        """Check if currently connected to the backend.

        Returns:
            True if connected and authenticated, False otherwise.
        """
        ...

    # =========================================================================
    # Space Operations
    # =========================================================================

    def list_spaces(self) -> list[Space]:
        """List all available spaces/workspaces.

        Returns:
            List of Space objects.

        Raises:
            ConnectionError: If not connected
        """
        ...

    def get_default_space(self) -> str:
        """Get the default/current space ID.

        Returns:
            Space ID string.

        Raises:
            ConnectionError: If not connected
            NotFoundError: If no spaces exist
        """
        ...

    def set_default_space(self, space_id: str) -> None:
        """Set the default space for operations.

        Args:
            space_id: ID of space to make default

        Raises:
            NotFoundError: If space doesn't exist
        """
        ...

    # =========================================================================
    # Task Operations
    # =========================================================================

    def create_task(
        self,
        space_id: str,
        title: str,
        due_date: date | None = None,
        priority: Priority | None = None,
        tags: list[str] | None = None,
        description: str | None = None,
    ) -> Task:
        """Create a new task.

        Args:
            space_id: Space to create task in
            title: Task title (1-500 characters)
            due_date: Optional due date
            priority: Optional priority level
            tags: Optional list of tag names
            description: Optional description/notes (max 10000 characters)

        Returns:
            Created Task object with ID populated.

        Raises:
            NotSupportedError: If tasks capability is False
            ConnectionError: If not connected
            ValidationError: If title or description exceeds limits
        """
        ...

    def get_task(self, space_id: str, task_id: str) -> Task:
        """Get a single task by ID.

        Args:
            space_id: Space containing the task
            task_id: Task identifier

        Returns:
            Task object.

        Raises:
            NotFoundError: If task doesn't exist
            ConnectionError: If not connected
        """
        ...

    def get_tasks(
        self,
        space_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
        include_done: bool = False,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Task]:
        """Query tasks with optional filters.

        Args:
            space_id: Space to query
            start_date: Filter tasks due on or after this date
            end_date: Filter tasks due on or before this date
            include_done: Include completed tasks
            limit: Maximum number of tasks to return
            offset: Number of tasks to skip (for pagination, must be >= 0)

        Returns:
            List of Task objects matching filters.

        Raises:
            ConnectionError: If not connected
            ValidationError: If offset is negative
        """
        ...

    def update_task(
        self,
        space_id: str,
        task_id: str,
        title: str | None = None,
        due_date: date | None = None,
        priority: Priority | None = None,
        tags: list[str] | None = None,
        description: str | None = None,
        is_done: bool | None = None,
    ) -> Task:
        """Update an existing task.

        Only provided (non-None) fields are updated.

        Args:
            space_id: Space containing the task
            task_id: Task to update
            title: New title (optional)
            due_date: New due date (optional)
            priority: New priority (optional)
            tags: New tags list (optional, replaces existing)
            description: New description (optional)
            is_done: New completion status (optional)

        Returns:
            Updated Task object.

        Raises:
            NotFoundError: If task doesn't exist
            ConnectionError: If not connected
            ValidationError: If title or description exceeds limits
        """
        ...

    def delete_task(self, space_id: str, task_id: str) -> bool:
        """Delete a task.

        Args:
            space_id: Space containing the task
            task_id: Task to delete

        Returns:
            True if deleted successfully.

        Raises:
            NotFoundError: If task doesn't exist
            ConnectionError: If not connected
        """
        ...

    # =========================================================================
    # Journal Operations
    # =========================================================================

    def create_journal_entry(
        self,
        space_id: str,
        content: str,
        title: str | None = None,
        entry_date: date | None = None,
    ) -> JournalEntry:
        """Create a new journal entry.

        Args:
            space_id: Space to create entry in
            content: Entry content (markdown)
            title: Optional title (may be auto-generated)
            entry_date: Date for entry (defaults to today)

        Returns:
            Created JournalEntry object.

        Raises:
            NotSupportedError: If journal capability is False
            ConnectionError: If not connected
        """
        ...

    def get_journal_entry(self, space_id: str, entry_id: str) -> JournalEntry:
        """Get a single journal entry by ID.

        Args:
            space_id: Space containing the entry
            entry_id: Entry identifier

        Returns:
            JournalEntry object.

        Raises:
            NotFoundError: If entry doesn't exist
            ConnectionError: If not connected
        """
        ...

    def get_journal_entries(
        self,
        space_id: str,
        limit: int = 10,
        offset: int = 0,
    ) -> list[JournalEntry]:
        """List journal entries with pagination.

        Args:
            space_id: Space to query
            limit: Maximum entries to return
            offset: Number of entries to skip (must be >= 0)

        Returns:
            List of JournalEntry objects, newest first.

        Raises:
            ConnectionError: If not connected
            ValidationError: If offset is negative
        """
        ...

    def update_journal_entry(
        self,
        space_id: str,
        entry_id: str,
        content: str | None = None,
        title: str | None = None,
    ) -> JournalEntry:
        """Update an existing journal entry.

        Args:
            space_id: Space containing the entry
            entry_id: Entry to update
            content: New content (optional)
            title: New title (optional)

        Returns:
            Updated JournalEntry object.

        Raises:
            NotFoundError: If entry doesn't exist
            ConnectionError: If not connected
        """
        ...

    def delete_journal_entry(self, space_id: str, entry_id: str) -> bool:
        """Delete a journal entry.

        Args:
            space_id: Space containing the entry
            entry_id: Entry to delete

        Returns:
            True if deleted successfully.

        Raises:
            NotFoundError: If entry doesn't exist
            ConnectionError: If not connected
        """
        ...

    def search_journal(
        self,
        space_id: str,
        query: str,
        limit: int = 10,
        offset: int = 0,
    ) -> list[JournalEntry]:
        """Search journal entries by content.

        Args:
            space_id: Space to search
            query: Search query string
            limit: Maximum results to return
            offset: Number of results to skip (for pagination)

        Returns:
            List of matching JournalEntry objects.

        Raises:
            NotSupportedError: If search capability is False
            ConnectionError: If not connected
        """
        ...

    # =========================================================================
    # Tag Operations
    # =========================================================================

    def list_tags(self, space_id: str) -> list[Tag]:
        """List all tags in a space.

        Args:
            space_id: Space to query

        Returns:
            List of Tag objects.

        Raises:
            NotSupportedError: If tags capability is False
            ConnectionError: If not connected
        """
        ...

    def create_tag(self, space_id: str, name: str, color: str | None = None) -> Tag:
        """Create a new tag.

        Args:
            space_id: Space to create tag in
            name: Tag name
            color: Optional color code (backend-specific format)

        Returns:
            Created Tag object.

        Raises:
            NotSupportedError: If tags capability is False
            ConnectionError: If not connected
        """
        ...

    # =========================================================================
    # Generic Object Operations
    # =========================================================================

    def get_object(self, space_id: str, object_id: str) -> BackendObject:
        """Get any object by ID, regardless of type.

        Retrieves the full object including all properties, content,
        and type information. Works for Tasks, Pages, Collections,
        and any other object type the backend supports.

        Args:
            space_id: Space containing the object
            object_id: Object identifier (raw ID or extracted from URL)

        Returns:
            BackendObject with all properties populated.

        Raises:
            NotFoundError: If object doesn't exist
            ConnectionError: If not connected
        """
        ...

    def update_object(
        self,
        space_id: str,
        object_id: str,
        updates: dict[str, object],
    ) -> BackendObject:
        """Update an object's properties by key-value pairs.

        Accepts a dict of property keys to new values. Only the provided
        keys are updated; other properties remain unchanged.

        Special keys:
            - 'name': Updates the object's title/name
            - 'description': Updates the description field
            - 'icon': Updates the icon/emoji

        All other keys are matched against the object's property keys.

        Args:
            space_id: Space containing the object
            object_id: Object to update
            updates: Dict mapping property keys to new values.
                     Values should match the property's format
                     (str for text, bool for checkbox, etc.)

        Returns:
            Updated BackendObject.

        Raises:
            NotFoundError: If object doesn't exist
            ConnectionError: If not connected
            ValidationError: If a property key doesn't exist or value is invalid
        """
        ...


# Type alias for adapter classes (useful for registry typing)
AdapterClass = type[KnowledgeBaseAdapter]
