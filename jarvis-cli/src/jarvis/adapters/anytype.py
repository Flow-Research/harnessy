"""AnyType adapter implementation.

This adapter wraps the existing AnyTypeClient to provide a Protocol-compliant
interface for the backend abstraction layer.
"""

from datetime import date, datetime
from typing import Any

from ..anytype_client import AnyTypeClient
from ..config.schema import JarvisConfig
from ..models import (
    BackendObject,
    JournalEntry,
    ObjectProperty,
    Priority,
    PropertyFormat,
    Space,
    Tag,
    Task,
)
from .exceptions import (
    AuthError,
    ConnectionError,
    NotFoundError,
    ValidationError,
)


class AnyTypeAdapter:
    """Adapter for AnyType backend.

    Wraps the existing AnyTypeClient to implement the KnowledgeBaseAdapter
    Protocol, providing a unified interface for task and journal operations.

    AnyType connects to a locally-running desktop app via localhost:31009.
    On first connection, it prompts for a 4-digit authentication code.

    Capabilities:
        - tasks: Full CRUD support
        - journal: Full CRUD support with hierarchical organization
        - tags: Read and create (via task creation)
        - search: Basic text search
        - priorities: Numeric (1-3) mapped to high/medium/low
        - due_dates: Full support
        - daily_notes: Not supported (no automatic daily note)
        - relations: Limited support (collections only)
        - custom_properties: Not currently exposed

    Example:
        adapter = AnyTypeAdapter(config)
        adapter.connect()
        tasks = adapter.get_tasks(space_id)
    """

    def __init__(self, config: JarvisConfig | None = None) -> None:
        """Initialize the adapter.

        Args:
            config: Optional configuration. AnyType has minimal config needs
                   since it uses localhost gRPC.
        """
        self._config = config
        self._client = AnyTypeClient()
        self._default_space_id: str | None = None

        # Load default space from config if available
        if config and config.backends.anytype.default_space_id:
            self._default_space_id = config.backends.anytype.default_space_id

    @property
    def capabilities(self) -> dict[str, bool]:
        """Declare supported capabilities."""
        return {
            "tasks": True,
            "journal": True,
            "tags": True,
            "search": True,
            "priorities": True,
            "due_dates": True,
            "daily_notes": False,  # AnyType doesn't auto-create daily notes
            "relations": True,  # Collections support relations
            "custom_properties": False,  # Not exposed via adapter yet
        }

    @property
    def backend_name(self) -> str:
        """Return the backend identifier."""
        return "anytype"

    # =========================================================================
    # Connection Management
    # =========================================================================

    def connect(self) -> None:
        """Connect and authenticate with AnyType.

        On first connection, the AnyType desktop app will show a 4-digit
        authentication code that the user must approve.

        Raises:
            ConnectionError: If AnyType desktop app is not running
            AuthError: If authentication fails
        """
        try:
            self._client.connect()
        except RuntimeError as e:
            error_msg = str(e)
            if "authenticate" in error_msg.lower() or "auth" in error_msg.lower():
                raise AuthError(error_msg, backend="anytype")
            raise ConnectionError(error_msg, backend="anytype")

    def disconnect(self) -> None:
        """Disconnect from AnyType.

        AnyType uses a persistent connection, so this is mostly a no-op.
        """
        # AnyType client doesn't have explicit disconnect
        pass

    def is_connected(self) -> bool:
        """Check if connected to AnyType.

        Returns:
            True if authenticated, False otherwise.
        """
        return self._client._authenticated

    # =========================================================================
    # Space Operations
    # =========================================================================

    def list_spaces(self) -> list[Space]:
        """List all available AnyType spaces.

        Returns:
            List of Space objects.

        Raises:
            ConnectionError: If not connected
        """
        self._ensure_connected()
        try:
            space_tuples = self._client.get_spaces()
            return [
                Space(id=sid, name=sname, backend="anytype")
                for sid, sname in space_tuples
            ]
        except RuntimeError as e:
            raise ConnectionError(str(e), backend="anytype")

    def get_default_space(self) -> str:
        """Get the default space ID.

        Returns the configured default space if set, otherwise the first
        available space.

        Returns:
            Space ID string.

        Raises:
            ConnectionError: If not connected
            NotFoundError: If no spaces exist
        """
        self._ensure_connected()

        if self._default_space_id:
            return self._default_space_id

        try:
            space_id = self._client.get_default_space()
            self._default_space_id = space_id
            return space_id
        except RuntimeError as e:
            if "no" in str(e).lower() and "space" in str(e).lower():
                raise NotFoundError(
                    "No AnyType spaces found",
                    backend="anytype",
                    resource_type="space",
                )
            raise ConnectionError(str(e), backend="anytype")

    def set_default_space(self, space_id: str) -> None:
        """Set the default space for operations.

        Args:
            space_id: ID of space to make default

        Raises:
            NotFoundError: If space doesn't exist
        """
        self._ensure_connected()

        # Verify space exists
        spaces = self.list_spaces()
        if not any(s.id == space_id for s in spaces):
            raise NotFoundError(
                f"Space '{space_id}' not found",
                backend="anytype",
                resource_type="space",
                resource_id=space_id,
            )

        self._default_space_id = space_id

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
        """Create a new task in AnyType.

        Args:
            space_id: Space to create task in
            title: Task title (1-500 characters)
            due_date: Optional due date
            priority: Optional priority level
            tags: Optional list of tag names
            description: Optional description/notes

        Returns:
            Created Task object with ID populated.

        Raises:
            ConnectionError: If not connected
            ValidationError: If title is invalid
        """
        self._ensure_connected()
        self._validate_title(title)

        # Convert Priority enum to string
        priority_str = priority.value if priority else None

        try:
            task_id = self._client.create_task(
                space_id=space_id,
                title=title,
                due_date=due_date,
                priority=priority_str,
                tags=tags,
                description=description,
            )
        except RuntimeError as e:
            raise ConnectionError(str(e), backend="anytype")

        # Return a Task model
        now = datetime.now()
        return Task(
            id=task_id,
            space_id=space_id,
            title=title,
            description=description,
            due_date=due_date,
            priority=priority,
            tags=tags or [],
            is_done=False,
            created_at=now,
            updated_at=now,
        )

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
        self._ensure_connected()

        try:
            space = self._client._client.get_space(space_id)
            obj = space.get_object(task_id)
            return self._anytype_object_to_task(obj, space_id)
        except Exception as e:
            error_msg = str(e).lower()
            # Handle various not found error patterns
            if any(
                pattern in error_msg
                for pattern in [
                    "not found",
                    "does not exist",
                    "failed to retrieve",
                    "object not",
                ]
            ):
                raise NotFoundError(
                    f"Task '{task_id}' not found",
                    backend="anytype",
                    resource_type="task",
                    resource_id=task_id,
                )
            raise ConnectionError(str(e), backend="anytype")

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
            offset: Number of tasks to skip (for pagination)

        Returns:
            List of Task objects matching filters.

        Raises:
            ConnectionError: If not connected
            ValidationError: If offset is negative
        """
        self._ensure_connected()

        if offset < 0:
            raise ValidationError("Offset must be non-negative", backend="anytype")

        # Use existing client method if we have a date range
        if start_date and end_date:
            try:
                old_tasks = self._client.get_tasks_in_range(space_id, start_date, end_date)
            except RuntimeError as e:
                raise ConnectionError(str(e), backend="anytype")
        else:
            # Get all tasks and filter
            old_tasks = self._get_all_tasks(space_id, start_date, end_date)

        # Filter by done status
        if not include_done:
            old_tasks = [t for t in old_tasks if not t.is_done]

        # Convert old Task models to new format
        tasks = [self._old_task_to_new(t) for t in old_tasks]

        # Apply pagination
        if offset > 0:
            tasks = tasks[offset:]
        if limit is not None:
            tasks = tasks[:limit]

        return tasks

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
            tags: New tags list (optional)
            description: New description (optional)
            is_done: New completion status (optional)

        Returns:
            Updated Task object.

        Raises:
            NotFoundError: If task doesn't exist
            ConnectionError: If not connected
        """
        self._ensure_connected()

        if title is not None:
            self._validate_title(title)

        # Get current task first
        current = self.get_task(space_id, task_id)

        # Build updates dict for the generic update_object method
        updates: dict[str, object] = {}

        if title is not None:
            updates["name"] = title

        if due_date is not None:
            updates["due_date"] = due_date.isoformat()

        if priority is not None:
            updates["priority"] = priority.value

        if is_done is not None:
            updates["done"] = is_done

        if description is not None:
            updates["body"] = description

        if tags is not None:
            updates["tag"] = ",".join(tags)

        if updates:
            try:
                self.update_object(space_id, task_id, updates)
            except Exception as e:
                raise ConnectionError(
                    f"Failed to update task: {e}", backend="anytype"
                )

        # Return updated task (refetch to get latest state)
        return self.get_task(space_id, task_id)

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
        self._ensure_connected()

        # Verify task exists first
        self.get_task(space_id, task_id)

        try:
            return self._client.delete_object(space_id, task_id)
        except RuntimeError as e:
            raise ConnectionError(str(e), backend="anytype")

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

        Uses the existing JournalHierarchy for proper organization
        (Journal → Year → Month → Entry).

        Args:
            space_id: Space to create entry in
            content: Entry content (markdown)
            title: Optional title
            entry_date: Date for entry (defaults to today)

        Returns:
            Created JournalEntry object.

        Raises:
            ConnectionError: If not connected
        """
        self._ensure_connected()

        from ..journal.hierarchy import JournalHierarchy

        entry_date = entry_date or date.today()
        final_title = title or f"Entry {entry_date.day}"

        try:
            hierarchy = JournalHierarchy(self._client, space_id)
            entry_id, journal_id, year_id, month_id = hierarchy.create_entry(
                entry_date=entry_date,
                title=final_title,
                content=content,
            )
        except Exception as e:
            raise ConnectionError(str(e), backend="anytype")

        now = datetime.now()
        return JournalEntry(
            id=entry_id,
            space_id=space_id,
            title=final_title,
            content=content,
            entry_date=entry_date,
            created_at=now,
            path=f"Journal/{entry_date.year}/{entry_date.strftime('%B')}/{final_title}",
        )

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
        self._ensure_connected()

        try:
            space = self._client._client.get_space(space_id)
            obj = space.get_object(entry_id)

            content = self._client.get_page_content(space_id, entry_id)
            props = self._client._extract_properties(obj)

            # Try to extract date from properties or name
            entry_date = self._parse_entry_date(props, getattr(obj, "name", ""))

            return JournalEntry(
                id=obj.id,
                space_id=space_id,
                title=getattr(obj, "name", "Untitled"),
                content=content,
                entry_date=entry_date or date.today(),
                created_at=self._client._parse_datetime(
                    props.get("created_date")
                ) or datetime.now(),
            )
        except Exception as e:
            error_msg = str(e).lower()
            if "not found" in error_msg or "does not exist" in error_msg:
                raise NotFoundError(
                    f"Journal entry '{entry_id}' not found",
                    backend="anytype",
                    resource_type="journal_entry",
                    resource_id=entry_id,
                )
            raise ConnectionError(str(e), backend="anytype")

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
            offset: Number of entries to skip

        Returns:
            List of JournalEntry objects, newest first.

        Raises:
            ConnectionError: If not connected
        """
        self._ensure_connected()

        if offset < 0:
            raise ValidationError("Offset must be non-negative", backend="anytype")

        try:
            space = self._client._client.get_space(space_id)

            # Get Page type and search for journal entries
            page_type = space.get_type_byname("Page")
            results = space.search(query="", type=page_type, limit=500)

            entries: list[JournalEntry] = []
            for obj in results:
                try:
                    content = self._client.get_page_content(space_id, obj.id)
                    props = self._client._extract_properties(obj)

                    entry_date = self._parse_entry_date(props, getattr(obj, "name", ""))
                    if entry_date is None:
                        continue  # Skip non-journal pages

                    entries.append(JournalEntry(
                        id=obj.id,
                        space_id=space_id,
                        title=getattr(obj, "name", "Untitled"),
                        content=content,
                        entry_date=entry_date,
                        created_at=self._client._parse_datetime(
                            props.get("created_date")
                        ) or datetime.now(),
                    ))
                except Exception:
                    continue

            # Sort by date (newest first)
            entries.sort(key=lambda e: e.entry_date, reverse=True)

            # Apply pagination
            if offset > 0:
                entries = entries[offset:]
            entries = entries[:limit]

            return entries

        except Exception as e:
            raise ConnectionError(str(e), backend="anytype")

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
        self._ensure_connected()

        # Verify entry exists
        current = self.get_journal_entry(space_id, entry_id)

        # Build updates via generic object update
        updates: dict[str, object] = {}

        if title is not None:
            updates["name"] = title

        if content is not None:
            updates["body"] = content

        if updates:
            try:
                self.update_object(space_id, entry_id, updates)
            except Exception as e:
                raise ConnectionError(
                    f"Failed to update journal entry: {e}",
                    backend="anytype",
                )

        return self.get_journal_entry(space_id, entry_id)

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
        self._ensure_connected()

        # Verify entry exists
        self.get_journal_entry(space_id, entry_id)

        try:
            return self._client.delete_object(space_id, entry_id)
        except RuntimeError as e:
            raise ConnectionError(str(e), backend="anytype")

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
            offset: Number of results to skip

        Returns:
            List of matching JournalEntry objects.

        Raises:
            ConnectionError: If not connected
        """
        self._ensure_connected()

        if offset < 0:
            raise ValidationError("Offset must be non-negative", backend="anytype")

        try:
            space = self._client._client.get_space(space_id)
            page_type = space.get_type_byname("Page")
            results = space.search(query=query, type=page_type, limit=100)

            entries: list[JournalEntry] = []
            for obj in results:
                try:
                    content = self._client.get_page_content(space_id, obj.id)
                    props = self._client._extract_properties(obj)

                    entry_date = self._parse_entry_date(props, getattr(obj, "name", ""))
                    if entry_date is None:
                        continue

                    entries.append(JournalEntry(
                        id=obj.id,
                        space_id=space_id,
                        title=getattr(obj, "name", "Untitled"),
                        content=content,
                        entry_date=entry_date,
                        created_at=self._client._parse_datetime(
                            props.get("created_date")
                        ) or datetime.now(),
                    ))
                except Exception:
                    continue

            # Apply pagination
            if offset > 0:
                entries = entries[offset:]
            entries = entries[:limit]

            return entries

        except Exception as e:
            raise ConnectionError(str(e), backend="anytype")

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
            ConnectionError: If not connected
        """
        self._ensure_connected()

        try:
            space = self._client._client.get_space(space_id)

            # In AnyType, tags are typically stored as multi-select options
            # We need to extract them from existing tasks
            tags_seen: dict[str, Tag] = {}

            # Get tasks and extract unique tags
            task_type = space.get_type_byname("Task")
            results = space.search(query="", type=task_type, limit=500)

            for obj in results:
                props = self._client._extract_properties(obj)
                task_tags = props.get("tags", [])
                for tag_name in task_tags:
                    if tag_name and tag_name not in tags_seen:
                        tags_seen[tag_name] = Tag(
                            id=tag_name,  # AnyType uses name as ID for tags
                            name=tag_name,
                        )

            return list(tags_seen.values())

        except Exception as e:
            raise ConnectionError(str(e), backend="anytype")

    def create_tag(self, space_id: str, name: str, color: str | None = None) -> Tag:
        """Create a new tag.

        Note: In AnyType, tags are created implicitly when used on a task.
        This method returns a Tag object without actually creating it in AnyType.

        Args:
            space_id: Space to create tag in
            name: Tag name
            color: Optional color code (ignored for AnyType)

        Returns:
            Tag object.

        Raises:
            ConnectionError: If not connected
        """
        self._ensure_connected()

        # AnyType creates tags implicitly when used
        # We just return the tag object
        return Tag(
            id=name,
            name=name,
            color=color,
        )

    # =========================================================================
    # Generic Object Operations
    # =========================================================================

    # AnyType system properties that cannot be updated via API
    _SYSTEM_PROPERTY_KEYS = {
        "creator",
        "created_by",
        "created_date",
        "last_modified_by",
        "last_modified_date",
        "last_opened_date",
        "backlinks",
        "links",
    }

    # Map AnyType property format strings to PropertyFormat enum
    _FORMAT_MAP: dict[str, PropertyFormat] = {
        "text": PropertyFormat.TEXT,
        "number": PropertyFormat.NUMBER,
        "date": PropertyFormat.DATE,
        "checkbox": PropertyFormat.CHECKBOX,
        "select": PropertyFormat.SELECT,
        "multi_select": PropertyFormat.MULTI_SELECT,
        "url": PropertyFormat.URL,
        "email": PropertyFormat.EMAIL,
        "phone": PropertyFormat.PHONE,
        "files": PropertyFormat.FILES,
        "objects": PropertyFormat.OBJECTS,
    }

    def get_object(self, space_id: str, object_id: str) -> BackendObject:
        """Get any object by ID, regardless of type.

        Args:
            space_id: Space containing the object
            object_id: Object identifier

        Returns:
            BackendObject with all properties populated.

        Raises:
            NotFoundError: If object doesn't exist
            ConnectionError: If not connected
        """
        self._ensure_connected()

        try:
            space = self._client._client.get_space(space_id)
            obj = space.get_object(object_id)
        except Exception as e:
            error_msg = str(e).lower()
            if any(
                p in error_msg
                for p in [
                    "not found",
                    "does not exist",
                    "failed to retrieve",
                    "object not",
                ]
            ):
                raise NotFoundError(
                    f"Object '{object_id}' not found",
                    backend="anytype",
                    resource_type="object",
                    resource_id=object_id,
                )
            raise ConnectionError(str(e), backend="anytype")

        return self._anytype_object_to_backend_object(obj, space_id)

    def update_object(
        self,
        space_id: str,
        object_id: str,
        updates: dict[str, object],
    ) -> BackendObject:
        """Update an object's properties by key-value pairs.

        Args:
            space_id: Space containing the object
            object_id: Object to update
            updates: Dict mapping property keys (or 'name', 'description',
                     'icon') to new values.

        Returns:
            Updated BackendObject.

        Raises:
            NotFoundError: If object doesn't exist
            ConnectionError: If not connected
            ValidationError: If a property key is invalid
        """
        self._ensure_connected()

        # Fetch current object to get its properties and name
        try:
            space = self._client._client.get_space(space_id)
            obj = space.get_object(object_id)
        except Exception as e:
            error_msg = str(e).lower()
            if any(
                p in error_msg
                for p in [
                    "not found",
                    "does not exist",
                    "failed to retrieve",
                    "object not",
                ]
            ):
                raise NotFoundError(
                    f"Object '{object_id}' not found",
                    backend="anytype",
                    resource_type="object",
                    resource_id=object_id,
                )
            raise ConnectionError(str(e), backend="anytype")

        # Build update payload
        new_name = updates.pop("name", None) or getattr(obj, "name", "")
        update_payload: dict[str, Any] = {"name": str(new_name)}

        if "description" in updates:
            update_payload["description"] = str(updates.pop("description"))

        if "icon" in updates:
            icon_val = updates.pop("icon")
            update_payload["icon"] = {"emoji": str(icon_val), "format": "emoji"}

        # Handle body/content update (markdown body patching)
        # Requires API version 2025-11-08+
        # Note: UpdateObjectRequest uses "markdown" key, not "body"
        has_body_update = False
        if "body" in updates:
            update_payload["markdown"] = str(updates.pop("body"))
            has_body_update = True
        elif "content" in updates:
            update_payload["markdown"] = str(updates.pop("content"))
            has_body_update = True
        elif "markdown" in updates:
            update_payload["markdown"] = str(updates.pop("markdown"))
            has_body_update = True

        # Process property updates
        if updates:
            # Get existing properties, filter system ones
            existing_props = getattr(obj, "properties", []) or []
            properties: list[dict[str, Any]] = []
            updated_keys: set[str] = set()

            for prop in existing_props:
                prop_key = prop.get("key", "")
                if prop_key in self._SYSTEM_PROPERTY_KEYS:
                    continue

                prop_copy = dict(prop)

                if prop_key in updates:
                    # Apply the update to this property
                    new_val = updates[prop_key]
                    fmt = prop.get("format", "")
                    prop_copy = self._apply_property_update(
                        prop_copy, fmt, new_val
                    )
                    updated_keys.add(prop_key)

                properties.append(prop_copy)

            # Check for keys that didn't match any existing property
            unmatched = set(updates.keys()) - updated_keys
            if unmatched:
                raise ValidationError(
                    f"Unknown property keys: "
                    f"{', '.join(sorted(unmatched))}. "
                    f"Use 'jarvis object get <id>' to see available "
                    f"properties.",
                    backend="anytype",
                )

            update_payload["properties"] = properties

        # Send update
        try:
            api = self._client._client._apiEndpoints
            if has_body_update:
                # Body patching requires API version 2025-11-08+.
                # Temporarily upgrade the version header for this call.
                original_version = api.headers.get("Anytype-Version")
                api.headers["Anytype-Version"] = "2025-11-08"
                try:
                    api.updateObject(
                        space_id, object_id, update_payload
                    )
                finally:
                    if original_version:
                        api.headers["Anytype-Version"] = original_version
            else:
                api.updateObject(
                    space_id, object_id, update_payload
                )
        except Exception as e:
            raise ConnectionError(
                f"Failed to update object: {e}", backend="anytype"
            )

        # Re-fetch and return updated object
        return self.get_object(space_id, object_id)

    # =========================================================================
    # Sync Operations (folder/file → Anytype Pages and Collections)
    # =========================================================================
    #
    # These methods power `jarvis sync`. They use the SDK's high-level
    # `Space.create_object` / `update_object` plus the lower-level
    # `apiEndpoints.addObjectsToList` to attach a created object as a child
    # of a target Collection. The Anytype API treats Collections as "lists"
    # at the endpoint layer (POST /spaces/{spaceId}/lists/{listId}/objects).

    def create_collection_in(
        self,
        space_id: str,
        parent_collection_id: str | None,
        name: str,
    ) -> str:
        """Create a Collection-typed Object, optionally as a child of another Collection.

        Args:
            space_id: Space to create the Collection in.
            parent_collection_id: If given, the new Collection is attached as
                a child of this parent via the lists endpoint. None = top-level.
            name: Display name of the new Collection.

        Returns:
            The new Collection's object_id.

        Raises:
            ConnectionError: If not connected or the API call fails.
        """
        from anytype import Object as AnytypeObject

        self._ensure_connected()
        try:
            space = self._client._client.get_space(space_id)
            type_collection = space.get_type_byname("Collection")
            obj = AnytypeObject(name=name, type=type_collection)
            created = space.create_object(obj)
            if parent_collection_id:
                space._apiEndpoints.addObjectsToList(
                    space_id, parent_collection_id, {"objects": [created.id]}
                )
            return str(created.id)
        except Exception as e:
            raise ConnectionError(str(e), backend="anytype")

    def create_page_in(
        self,
        space_id: str,
        parent_collection_id: str | None,
        name: str,
        body_markdown: str,
    ) -> str:
        """Create a Page with markdown body, optionally inside a Collection.

        Args:
            space_id: Space to create the Page in.
            parent_collection_id: If given, attach the Page to that Collection.
                None = top-level (Page lives in the Space root).
            name: Page title.
            body_markdown: Page body in Anytype-compatible markdown.

        Returns:
            The new Page's object_id.

        Raises:
            ConnectionError: If not connected or the API call fails.
        """
        from anytype import Object as AnytypeObject

        self._ensure_connected()
        try:
            space = self._client._client.get_space(space_id)
            type_page = space.get_type_byname("Page")
            obj = AnytypeObject(name=name, type=type_page)
            obj.body = body_markdown
            created = space.create_object(obj)
            if parent_collection_id:
                space._apiEndpoints.addObjectsToList(
                    space_id, parent_collection_id, {"objects": [created.id]}
                )
            return str(created.id)
        except Exception as e:
            raise ConnectionError(str(e), backend="anytype")

    def update_page_content(
        self,
        space_id: str,
        object_id: str,
        body_markdown: str,
    ) -> None:
        """Replace an existing Page's body with new markdown content.

        Args:
            space_id: Space containing the Page.
            object_id: Page to update.
            body_markdown: New body content.

        Raises:
            NotFoundError: If the Page doesn't exist.
            ConnectionError: If not connected or the API call fails.
        """
        self._ensure_connected()
        try:
            space = self._client._client.get_space(space_id)
            obj = space.get_object(object_id)
            obj.body = body_markdown
            space.update_object(obj)
        except Exception as e:
            msg = str(e).lower()
            if any(p in msg for p in ["not found", "does not exist"]):
                raise NotFoundError(
                    f"Object '{object_id}' not found",
                    backend="anytype",
                    resource_type="object",
                    resource_id=object_id,
                )
            raise ConnectionError(str(e), backend="anytype")

    def _apply_property_update(
        self, prop: dict[str, Any], fmt: str, new_value: object
    ) -> dict[str, Any]:
        """Apply a value update to a property dict based on its format.

        Args:
            prop: The property dict to update (will be mutated).
            fmt: The property format string.
            new_value: The new value to set.

        Returns:
            The updated property dict.
        """
        if fmt == "date":
            # Accept date string or date object
            val = str(new_value)
            if len(val) == 10:  # YYYY-MM-DD
                val += "T00:00:00Z"
            prop["date"] = val
        elif fmt == "checkbox":
            if isinstance(new_value, str):
                prop["checkbox"] = new_value.lower() in (
                    "true", "yes", "1", "on",
                )
            else:
                prop["checkbox"] = bool(new_value)
        elif fmt == "number":
            prop["number"] = float(str(new_value))
        elif fmt == "text":
            prop["text"] = str(new_value)
        elif fmt == "select":
            prop["select"] = {"name": str(new_value)}
        elif fmt == "multi_select":
            # Accept comma-separated string or list
            if isinstance(new_value, str):
                tags = [
                    t.strip() for t in new_value.split(",") if t.strip()
                ]
            elif isinstance(new_value, list):
                tags = [str(t) for t in new_value]
            else:
                tags = [str(new_value)]
            prop["multi_select"] = tags
        elif fmt == "url":
            prop["url"] = str(new_value)
        elif fmt == "email":
            prop["email"] = str(new_value)
        elif fmt == "phone":
            prop["phone"] = str(new_value)
        else:
            # Best effort: try text-like assignment
            prop["text"] = str(new_value)

        return prop

    def _anytype_object_to_backend_object(
        self, obj: Any, space_id: str
    ) -> BackendObject:
        """Convert a raw AnyType API object to a BackendObject.

        Args:
            obj: AnyType object from API
            space_id: Space ID

        Returns:
            BackendObject with all properties mapped.
        """
        # Determine type
        obj_type = getattr(obj, "type", None)
        if isinstance(obj_type, dict):
            type_name = obj_type.get("name", "Unknown")
            type_key = obj_type.get("key", "")
        else:
            type_name = (
                getattr(obj_type, "name", "Unknown")
                if obj_type
                else "Unknown"
            )
            type_key = (
                getattr(obj_type, "key", "") if obj_type else ""
            )

        # Icon
        icon_obj = getattr(obj, "icon", None)
        icon = ""
        if icon_obj:
            icon = getattr(icon_obj, "emoji", "") or ""

        # Content
        content = ""
        for attr in ("markdown", "body", "snippet", "description"):
            val = getattr(obj, attr, "")
            if val:
                content = val
                break

        # Properties
        raw_props = getattr(obj, "properties", []) or []
        properties: list[ObjectProperty] = []
        created_at = None
        updated_at = None

        for prop in raw_props:
            if not isinstance(prop, dict):
                continue

            key = prop.get("key", "")
            fmt_str = prop.get("format", "")
            name = prop.get("name", key)
            is_system = key in self._SYSTEM_PROPERTY_KEYS
            fmt = self._FORMAT_MAP.get(fmt_str, PropertyFormat.UNKNOWN)

            # Extract value based on format
            value = self._extract_property_value(prop, fmt_str)

            # Capture timestamps
            if key == "created_date" and value:
                created_at = self._client._parse_datetime(value)
            if key == "last_modified_date" and value:
                updated_at = self._client._parse_datetime(value)

            properties.append(
                ObjectProperty(
                    key=key,
                    name=name,
                    format=fmt,
                    value=value,
                    raw=prop,
                    is_system=is_system,
                )
            )

        # Raw JSON for reference
        raw_json = getattr(obj, "_json", {}) or {}

        return BackendObject(
            id=obj.id,
            space_id=space_id,
            name=getattr(obj, "name", "Untitled") or "Untitled",
            object_type=type_name,
            type_key=type_key,
            icon=icon,
            description=getattr(obj, "description", "") or "",
            snippet=getattr(obj, "snippet", "") or "",
            content=content,
            properties=properties,
            created_at=created_at,
            updated_at=updated_at,
            backend="anytype",
            raw=raw_json,
        )

    @staticmethod
    def _extract_property_value(
        prop: dict[str, Any], fmt: str
    ) -> Any:
        """Extract the value from a property dict based on its format.

        Args:
            prop: Property dict from AnyType API.
            fmt: Format string.

        Returns:
            The extracted value, or None.
        """
        if fmt == "date":
            return prop.get("date")
        elif fmt == "checkbox":
            return prop.get("checkbox", False)
        elif fmt == "number":
            return prop.get("number")
        elif fmt == "text":
            return prop.get("text")
        elif fmt == "select":
            sel = prop.get("select")
            return sel.get("name") if isinstance(sel, dict) else sel
        elif fmt == "multi_select":
            tags = prop.get("multi_select", []) or []
            if isinstance(tags, list):
                return [
                    t.get("name", str(t))
                    if isinstance(t, dict)
                    else str(t)
                    for t in tags
                ]
            return []
        elif fmt == "url":
            return prop.get("url")
        elif fmt == "email":
            return prop.get("email")
        elif fmt == "phone":
            return prop.get("phone")
        elif fmt == "objects":
            return prop.get("objects", [])
        elif fmt == "files":
            return prop.get("files", [])
        return None

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _ensure_connected(self) -> None:
        """Ensure we're connected to AnyType.

        Raises:
            ConnectionError: If not connected
        """
        if not self.is_connected():
            raise ConnectionError(
                "Not connected to AnyType. Call connect() first.",
                backend="anytype",
            )

    def _validate_title(self, title: str) -> None:
        """Validate a title string.

        Args:
            title: Title to validate

        Raises:
            ValidationError: If title is invalid
        """
        if not title or len(title) == 0:
            raise ValidationError("Title cannot be empty", backend="anytype")
        if len(title) > 500:
            raise ValidationError(
                f"Title too long: {len(title)} characters (max 500)",
                backend="anytype",
            )

    def _get_all_tasks(
        self,
        space_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[Any]:
        """Get all tasks from AnyType with optional date filtering.

        Args:
            space_id: Space to query
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            List of old-style Task models from AnyTypeClient
        """
        try:
            space = self._client._client.get_space(space_id)
            task_type = space.get_type_byname("Task")
            results = space.search(query="", type=task_type, limit=1000)

            tasks = []
            for obj in results:
                task = self._client._to_task(obj, space_id)

                # Apply date filters
                if start_date and task.scheduled_date and task.scheduled_date < start_date:
                    continue
                if end_date and task.scheduled_date and task.scheduled_date > end_date:
                    continue

                tasks.append(task)

            return tasks
        except Exception:
            return []

    def _old_task_to_new(self, old_task: Any) -> Task:
        """Convert old-style Task to new Task model.

        Args:
            old_task: Task from AnyTypeClient

        Returns:
            New-style Task model
        """
        # Parse priority
        priority = Priority.from_string(old_task.priority) if old_task.priority else None

        return Task(
            id=old_task.id,
            space_id=old_task.space_id,
            title=old_task.name,
            description=getattr(old_task, "description", None),
            due_date=old_task.due_date or old_task.scheduled_date,
            priority=priority,
            tags=old_task.tags or [],
            is_done=old_task.is_done,
            created_at=old_task.created_at,
            updated_at=old_task.updated_at,
        )

    def _anytype_object_to_task(self, obj: Any, space_id: str) -> Task:
        """Convert AnyType object directly to new Task model.

        Args:
            obj: AnyType object from API
            space_id: Space ID

        Returns:
            New-style Task model
        """
        old_task = self._client._to_task(obj, space_id)
        return self._old_task_to_new(old_task)

    def _parse_entry_date(self, props: dict[str, Any], name: str) -> date | None:
        """Try to parse journal entry date from properties or name.

        Args:
            props: Extracted properties
            name: Object name

        Returns:
            Parsed date or None if not a journal entry
        """
        # Try date from properties
        date_val = props.get("date") or props.get("entry_date")
        if date_val:
            return self._client._parse_date(date_val)

        # Try to extract from name (e.g., "15. Entry title" or "Entry 15")
        import re
        match = re.search(r"^(\d{1,2})[\.\s]", name)
        if match:
            # This is likely a journal entry with day prefix
            # But we can't determine the full date from just the day
            return None

        return None
