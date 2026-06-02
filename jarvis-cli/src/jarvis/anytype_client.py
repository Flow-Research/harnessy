"""AnyType API client wrapper."""

import mimetypes
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

import requests
from rich.console import Console

from jarvis.models import Priority, Task

console = Console()


_RATE_LIMIT_MARKERS = (
    "maximum request limit",
    "rate limit",
    "rate-limit",
    "too many requests",
    "429",
)


def _looks_rate_limited(message: str) -> bool:
    return any(marker in message.lower() for marker in _RATE_LIMIT_MARKERS)


def _add_to_collection_success(result: object) -> bool:
    if result is True:
        return True
    if isinstance(result, str):
        lowered = result.strip().lower()
        return lowered in {"ok", "true"} or "success" in lowered or "added" in lowered
    if isinstance(result, dict):
        status = str(result.get("status") or result.get("message") or "").lower()
        if result.get("error"):
            return False
        return (
            bool(result.get("success"))
            or status in {"ok", "success"}
            or "success" in status
            or "added" in status
        )
    return False


class AnyTypeClient:
    """Client for interacting with AnyType API.

    Requires AnyType desktop app to be running on localhost:31009.
    """

    def __init__(self) -> None:
        """Initialize the client (not connected yet)."""
        self._client: Any = None
        self._authenticated = False

    def connect(self) -> None:
        """Connect and authenticate with AnyType.

        On first use, this will trigger a 4-digit code popup in the AnyType app.
        """
        try:
            from anytype import Anytype
        except ImportError:
            raise RuntimeError(
                "anytype-client package not installed. Run: uv pip install anytype-client"
            )

        try:
            self._client = Anytype()
            self._client.auth()
            self._authenticated = True
        except Exception as e:
            raise RuntimeError(
                f"Could not connect to AnyType. Is the desktop app running?\nError: {e}"
            )

    def get_spaces(self) -> list[tuple[str, str]]:
        """Get all available spaces.

        Returns:
            List of (space_id, space_name) tuples

        Raises:
            RuntimeError: If not authenticated or no spaces found
        """
        if not self._authenticated:
            raise RuntimeError("Not authenticated. Call connect() first.")

        spaces = self._client.get_spaces()
        if not spaces:
            raise RuntimeError("No AnyType spaces found.")

        return [(s.id, s.name) for s in spaces]

    def get_default_space(self) -> str:
        """Get the first available space ID.

        Returns:
            Space ID string

        Raises:
            RuntimeError: If not authenticated or no spaces found
        """
        spaces = self.get_spaces()
        return spaces[0][0]

    def upload_file(self, space_id: str, path: Path) -> str:
        """Upload a local file as a native AnyType file object.

        AnyType added file endpoints after the Python client package version
        used here, so this method talks to the local REST API directly.

        Args:
            space_id: AnyType space ID.
            path: Local file to upload.

        Returns:
            The uploaded file object's ID.
        """
        if not self._authenticated:
            raise RuntimeError("Not authenticated. Call connect() first.")
        if self._client is None or self._client._apiEndpoints is None:
            raise RuntimeError("AnyType client is not connected.")

        api = self._client._apiEndpoints
        url = f"{api.api_url}/spaces/{space_id}/files"
        headers = dict(api.headers)
        headers.pop("Content-Type", None)
        headers["Anytype-Version"] = "2025-11-08"
        media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        try:
            with path.open("rb") as f:
                response = requests.post(
                    url,
                    headers=headers,
                    files={"file": (path.name, f, media_type)},
                    timeout=120,
                )
        except OSError as e:
            raise RuntimeError(f"Could not read file '{path}': {e}") from e
        return self._parse_file_upload_response(response)

    def delete_file(self, space_id: str, file_id: str, *, skip_bin: bool = False) -> bool:
        """Delete a native AnyType file object."""
        if not self._authenticated:
            raise RuntimeError("Not authenticated. Call connect() first.")
        if self._client is None or self._client._apiEndpoints is None:
            raise RuntimeError("AnyType client is not connected.")

        api = self._client._apiEndpoints
        url = f"{api.api_url}/spaces/{space_id}/files/{file_id}"
        headers = dict(api.headers)
        headers["Anytype-Version"] = "2025-11-08"
        response = requests.delete(
            url,
            headers=headers,
            params={"skip_bin": str(skip_bin).lower()},
            timeout=60,
        )
        if 200 <= response.status_code < 300:
            return True
        raise RuntimeError(self._api_error_message(response))

    def _parse_file_upload_response(self, response: requests.Response) -> str:
        if not (200 <= response.status_code < 300):
            raise RuntimeError(self._api_error_message(response))
        try:
            data = response.json()
        except ValueError as e:
            raise RuntimeError("AnyType file upload returned non-JSON response") from e
        object_id = data.get("object_id") or data.get("id")
        if not object_id:
            raise RuntimeError(f"AnyType file upload response missing object_id: {data}")
        return str(object_id)

    def _api_error_message(self, response: requests.Response) -> str:
        try:
            payload = response.json()
            message = payload.get("message") or payload
        except ValueError:
            message = response.text
        return f"AnyType API error {response.status_code}: {message}"

    def get_tasks_in_range(
        self,
        space_id: str,
        start: date,
        end: date,
    ) -> list[Task]:
        """Fetch all tasks within a date range.

        Args:
            space_id: AnyType space ID
            start: Start date (inclusive)
            end: End date (inclusive)

        Returns:
            List of Task models
        """
        if not self._authenticated:
            raise RuntimeError("Not authenticated. Call connect() first.")

        space = self._client.get_space(space_id)

        # Get the Task type and search for all tasks
        try:
            task_type = space.get_type_byname("Task")
        except ValueError:
            # Fallback: try lowercase or return empty if no Task type exists
            try:
                task_type = space.get_type_byname("task")
            except ValueError:
                console.print("[yellow]No 'Task' type found in this space.[/yellow]")
                return []

        # Search for all tasks in the space (high limit to get all)
        results = space.search(query="", type=task_type, limit=1000) or []

        tasks: list[Task] = []
        for obj in results:
            task = self._to_task(obj, space_id)
            # Filter by date range
            if task.scheduled_date and start <= task.scheduled_date <= end:
                tasks.append(task)

        return tasks

    # System properties that cannot be set via API
    SYSTEM_PROPERTIES = {
        "creator",
        "created_by",
        "created_date",
        "last_modified_by",
        "last_modified_date",
        "last_opened_date",
        "backlinks",
        "links",
    }

    def update_task_date(
        self,
        space_id: str,
        task_id: str,
        new_date: date,
    ) -> bool:
        """Update a task's due date (used as scheduled date).

        Args:
            space_id: AnyType space ID
            task_id: Task object ID
            new_date: New date to set

        Returns:
            True if successful, False otherwise
        """
        if not self._authenticated:
            raise RuntimeError("Not authenticated. Call connect() first.")

        try:
            # Get the task to retrieve its current properties
            space = self._client.get_space(space_id)
            obj = space.get_object(task_id)

            # Build update payload with due_date property
            # AnyType API expects ISO 8601 format for dates
            date_iso = new_date.isoformat() + "T00:00:00Z"

            # Filter out system properties and update due_date
            properties = []
            found_due_date = False
            for prop in obj.properties:
                prop_key = prop.get("key", "")

                # Skip system properties that can't be set
                if prop_key in self.SYSTEM_PROPERTIES:
                    continue

                prop_copy = dict(prop)
                if prop_key == "due_date":
                    prop_copy["date"] = date_iso
                    found_due_date = True
                properties.append(prop_copy)

            # If due_date property doesn't exist, add it
            if not found_due_date:
                properties.append(
                    {
                        "object": "property",
                        "key": "due_date",
                        "name": "Due date",
                        "format": "date",
                        "date": date_iso,
                    }
                )

            # Send update via API
            update_data = {
                "name": obj.name,
                "properties": properties,
            }

            self._client._apiEndpoints.updateObject(space_id, task_id, update_data)
            return True

        except Exception as e:
            console.print(f"[red]Error updating task: {e}[/red]")
            return False

    def _to_task(self, obj: Any, space_id: str) -> Task:
        """Convert AnyType object to Task model.

        Args:
            obj: AnyType object from API
            space_id: Space ID the object belongs to

        Returns:
            Task model
        """
        # Extract properties from the properties array
        props = self._extract_properties(obj)

        # Parse dates safely - use due_date as scheduled_date if no scheduled_date
        scheduled = self._parse_date(props.get("scheduled_date") or props.get("due_date"))
        due = self._parse_date(props.get("due_date"))

        # Get timestamps from properties
        now = datetime.now()
        created = self._parse_datetime(props.get("created_date")) or now
        updated = self._parse_datetime(props.get("last_modified_date")) or now

        # Extract tags from multi_select
        tags = props.get("tags", [])

        # Check done status
        is_done = props.get("done", False)

        # Convert priority number to string (1=high, 2=medium, 3=low)
        priority_raw = props.get("priority")
        priority_str = None
        if priority_raw is not None:
            priority_map = {1: "high", 2: "medium", 3: "low"}
            if isinstance(priority_raw, (int, float)):
                priority_str = priority_map.get(int(priority_raw))
            elif isinstance(priority_raw, str):
                priority_str = priority_raw
        priority_value = Priority.from_string(priority_str) if priority_str else None

        # Get task name, falling back to "Untitled" if empty or missing
        task_name = getattr(obj, "name", None) or "Untitled"

        return Task(
            id=obj.id,
            space_id=space_id,
            title=task_name,
            due_date=due or scheduled,  # Use due_date or fall back to scheduled
            priority=priority_value,
            tags=tags,
            is_done=is_done,
            created_at=created,
            updated_at=updated,
        )

    def _extract_properties(self, obj: Any) -> dict[str, Any]:
        """Extract properties from AnyType object into a flat dict.

        Args:
            obj: AnyType object

        Returns:
            Dict mapping property keys to their values
        """
        result: dict[str, Any] = {}
        properties = getattr(obj, "properties", []) or []

        for prop in properties:
            key = prop.get("key", "")
            fmt = prop.get("format", "")

            # Extract value based on format
            if fmt == "date":
                result[key] = prop.get("date")
            elif fmt == "checkbox":
                result[key] = prop.get("checkbox", False)
            elif fmt == "multi_select":
                # Extract tag names from multi_select
                tags = prop.get("multi_select", []) or []
                result[key] = [t.get("name", "") for t in tags if t.get("name")]
            elif fmt == "select":
                select = prop.get("select")
                if select:
                    result[key] = select.get("name")
            elif fmt == "number":
                result[key] = prop.get("number")
            elif fmt == "text":
                result[key] = prop.get("text")

        # Map 'tag' to 'tags' for consistency
        if "tag" in result:
            result["tags"] = result.pop("tag")

        return result

    def _parse_datetime(self, value: Any) -> datetime | None:
        """Parse a datetime from various formats.

        Args:
            value: Datetime value (string, datetime, or None)

        Returns:
            Parsed datetime or None
        """
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                # Handle ISO format with Z suffix
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
        return None

    def _parse_date(self, value: Any) -> date | None:
        """Parse a date from various formats.

        Args:
            value: Date value (string, date, or None)

        Returns:
            Parsed date or None
        """
        if value is None:
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            try:
                return date.fromisoformat(value[:10])  # Handle datetime strings
            except ValueError:
                return None
        return None

    # =========================================================================
    # Journal Integration Methods
    # =========================================================================

    def _get_object_links(self, space_id: str, object_id: str) -> list[str]:
        """Get the IDs of objects linked from a collection/object.

        Args:
            space_id: AnyType space ID
            object_id: Object ID to get links from

        Returns:
            List of linked object IDs
        """
        space = self._client.get_space(space_id)
        obj = space.get_object(object_id)
        properties = getattr(obj, "properties", []) or []

        for prop in properties:
            if prop.get("key") == "links":
                return prop.get("objects") or []
        return []

    def _find_child_by_name(self, space_id: str, parent_id: str, child_name: str) -> str | None:
        """Find a child object by name within a parent's links.

        Args:
            space_id: AnyType space ID
            parent_id: Parent object ID
            child_name: Name of child to find

        Returns:
            Child object ID if found, None otherwise
        """
        space = self._client.get_space(space_id)
        link_ids = self._get_object_links(space_id, parent_id)

        for link_id in link_ids:
            try:
                obj = space.get_object(link_id)
                if getattr(obj, "name", "") == child_name:
                    return obj.id
            except Exception:
                continue
        return None

    def list_collection_objects(
        self, space_id: str, collection_id: str, *, limit: int = 1000
    ) -> list[dict[str, Any]]:
        """List objects currently visible in a Collection/List.

        Uses the first list view exposed by the REST API. If the list-view
        endpoint is unavailable for a legacy object, falls back to the object's
        links property.
        """
        if not self._authenticated:
            raise RuntimeError("Not authenticated. Call connect() first.")
        if self._client is None or self._client._apiEndpoints is None:
            raise RuntimeError("AnyType client is not connected.")

        api = self._client._apiEndpoints
        page_limit = min(max(limit, 1), 100)
        try:
            views_payload = api.getListViews(space_id, collection_id, 0, 10)
            views = views_payload.get("data", []) if isinstance(views_payload, dict) else []
            if views:
                view_id = str(views[0].get("id") or "")
                if view_id:
                    objects: list[dict[str, Any]] = []
                    offset = 0
                    while len(objects) < limit:
                        payload = api.getObjectsInList(
                            space_id, collection_id, view_id, offset, page_limit
                        )
                        data = payload.get("data", []) if isinstance(payload, dict) else []
                        objects.extend([obj for obj in data if isinstance(obj, dict)])
                        if len(data) < page_limit:
                            break
                        offset += page_limit
                    return objects[:limit]
        except Exception:
            pass

        objects = []
        for object_id in self._get_object_links(space_id, collection_id)[:limit]:
            try:
                payload = api.getObject(space_id, object_id)
                data = payload.get("data", payload) if isinstance(payload, dict) else payload
                if isinstance(data, dict):
                    objects.append(data)
            except Exception:
                continue
        return objects

    def remove_from_collection(self, space_id: str, collection_id: str, object_id: str) -> bool:
        """Remove an object link from a Collection/List without deleting the object."""
        if not self._authenticated:
            raise RuntimeError("Not authenticated. Call connect() first.")
        if self._client is None or self._client._apiEndpoints is None:
            raise RuntimeError("AnyType client is not connected.")

        self._client._apiEndpoints.deleteObjectsFromList(space_id, collection_id, object_id)
        return True

    def get_or_create_collection(self, space_id: str, name: str) -> str:
        """Get or create a collection (top-level container) by name.

        Args:
            space_id: AnyType space ID
            name: Collection name (e.g., "Journal")

        Returns:
            Collection object ID

        Raises:
            RuntimeError: If not authenticated or creation fails
        """
        if not self._authenticated:
            raise RuntimeError("Not authenticated. Call connect() first.")

        space = self._client.get_space(space_id)

        # Search for existing collection by exact name match
        try:
            collection_type = space.get_type_byname("Collection")
        except ValueError:
            raise RuntimeError("Collection type not found in this space.")

        # Search for collection with matching name
        results = space.search(query=name, type=collection_type, limit=50) or []
        for obj in results:
            if getattr(obj, "name", "") == name:
                return obj.id

        # Not found, create new collection
        return self._create_collection(space_id, name, None)

    def get_or_create_container(self, space_id: str, parent_id: str, name: str) -> str:
        """Get or create a container (collection) under a parent.

        First checks the parent's links for an existing child with the name.
        If not found, creates a new collection and adds it to the parent.

        Args:
            space_id: AnyType space ID
            parent_id: Parent collection ID
            name: Container name (e.g., "2026" or "January")

        Returns:
            Container object ID

        Raises:
            RuntimeError: If not authenticated or creation fails
        """
        if not self._authenticated:
            raise RuntimeError("Not authenticated. Call connect() first.")

        # First, check parent's links for existing child
        existing_id = self._find_child_by_name(space_id, parent_id, name)
        if existing_id:
            return existing_id

        # Not found in parent's links, create new collection and add to parent
        new_id = self._create_collection(space_id, name, parent_id)
        return new_id

    def _create_collection(self, space_id: str, name: str, parent_id: str | None) -> str:
        """Create a collection and optionally add to parent.

        Args:
            space_id: AnyType space ID
            name: Collection name
            parent_id: Optional parent collection ID to add this to

        Returns:
            Created collection object ID

        Raises:
            RuntimeError: If creation fails
        """
        try:
            from anytype.object import Object

            space = self._client.get_space(space_id)

            # Get the Collection type
            collection_type = space.get_type_byname("Collection")
            obj = Object(name=name, type=collection_type)
            created = space.create_object(obj)

            # Add to parent collection if specified
            if parent_id:
                self._add_to_collection(space_id, parent_id, created.id)

            return created.id

        except Exception as e:
            raise RuntimeError(f"Failed to create collection '{name}': {e}")

    def _add_to_collection(self, space_id: str, collection_id: str, object_id: str) -> bool:
        """Add an object to a collection.

        The AnyType API requires calling addObjectsToList with multiple payload
        formats in succession to properly establish the bidirectional link
        (backlinks). A single call returns success but doesn't create the link.

        Args:
            space_id: AnyType space ID
            collection_id: Collection to add to
            object_id: Object to add

        Returns:
            True if API calls succeeded and object should be visible in collection
        """
        # Multiple formats are needed to establish proper bidirectional links.
        # This is a quirk of the AnyType API: a single accepted payload can
        # return success without reliably making the object visible in the list.
        formats = [
            {"object_ids": [object_id]},
            {"ids": [object_id]},
            {"objects": [object_id]},
            {"objectIds": [object_id]},
        ]
        max_attempts = 6
        last_errors: list[str] = []

        for attempt in range(max_attempts):
            success_count = 0
            attempt_errors: list[str] = []
            rate_limited = False
            for fmt in formats:
                try:
                    result = self._client._apiEndpoints.addObjectsToList(
                        space_id, collection_id, fmt
                    )
                    if _add_to_collection_success(result):
                        success_count += 1
                except Exception as exc:
                    message = str(exc) or exc.__class__.__name__
                    attempt_errors.append(message)
                    rate_limited = rate_limited or _looks_rate_limited(message)
                    # Some formats may not be supported; continue with others.
                    pass

            if success_count > 0:
                return True

            last_errors = attempt_errors
            if rate_limited and attempt < max_attempts - 1:
                time.sleep(min(2**attempt, 20))
                continue

            if rate_limited:
                detail = "; ".join(last_errors) if last_errors else "request limit reached"
                raise RuntimeError(
                    "Anytype request limit while adding object "
                    f"'{object_id}' to Collection '{collection_id}': {detail}"
                )
            if attempt_errors:
                detail = "; ".join(attempt_errors)
                raise RuntimeError(
                    f"Could not add object '{object_id}' to Collection "
                    f"'{collection_id}': {detail}"
                )
            return False

        return False

    def create_page(
        self,
        space_id: str,
        name: str,
        content: str,
        parent_id: str | None = None,
    ) -> str:
        """Create a page with content and add to parent collection.

        Args:
            space_id: AnyType space ID
            name: Page title
            content: Page content (markdown)
            parent_id: Parent collection ID to add this page to

        Returns:
            Created page object ID

        Raises:
            RuntimeError: If not authenticated or creation fails
        """
        if not self._authenticated:
            raise RuntimeError("Not authenticated. Call connect() first.")

        try:
            from anytype.object import Object

            space = self._client.get_space(space_id)

            # Get the Page type and create an Object with it
            page_type = space.get_type_byname("Page")
            obj = Object(name=name, type=page_type)

            # Add content to the page body before creation
            if content:
                obj.add_text(content)

            created = space.create_object(obj)

            # Add to parent collection if specified
            if parent_id:
                self._add_to_collection(space_id, parent_id, created.id)

            return created.id

        except Exception as e:
            raise RuntimeError(f"Failed to create page '{name}': {e}")

    # =========================================================================
    # Task Creation Methods
    # =========================================================================

    def create_task(
        self,
        space_id: str,
        title: str,
        due_date: date | None = None,
        priority: str | None = None,
        tags: list[str] | None = None,
        description: str | None = None,
    ) -> str:
        """Create a task in AnyType.

        Args:
            space_id: AnyType space ID
            title: Task title
            due_date: Optional due date
            priority: Optional priority (high/medium/low)
            tags: Optional list of tags
            description: Optional description (markdown)

        Returns:
            Created task object ID

        Raises:
            RuntimeError: If not authenticated or creation fails
        """
        if not self._authenticated:
            raise RuntimeError("Not authenticated. Call connect() first.")

        try:
            # Use raw API to avoid library bug with empty select properties
            # Get Task type key
            space = self._client.get_space(space_id)
            try:
                task_type = space.get_type_byname("Task")
            except ValueError:
                try:
                    task_type = space.get_type_byname("task")
                except ValueError:
                    raise RuntimeError("Task type not found in this space")

            # Create object using raw API
            create_data = {
                "name": title,
                "type_key": task_type.key,
            }

            # Add description as body if provided
            if description:
                create_data["body"] = description

            result = self._client._apiEndpoints.createObject(space_id, create_data)

            if not result or "object" not in result:
                raise RuntimeError("Failed to create task - no result returned")

            task_id = result["object"]["id"]

            # Build properties for update
            properties = []

            # Add due_date property
            if due_date:
                date_iso = due_date.isoformat() + "T00:00:00Z"
                properties.append(
                    {
                        "object": "property",
                        "key": "due_date",
                        "name": "Due date",
                        "format": "date",
                        "date": date_iso,
                    }
                )

            # Add priority property (as number: high=1, medium=2, low=3)
            if priority:
                priority_map = {"high": 1, "medium": 2, "low": 3}
                priority_num = priority_map.get(priority.lower(), 2)
                properties.append(
                    {
                        "object": "property",
                        "key": "priority",
                        "name": "Priority",
                        "format": "number",
                        "number": priority_num,
                    }
                )

            # Update with properties if any
            if properties:
                update_data = {
                    "name": title,
                    "properties": properties,
                }
                try:
                    self._client._apiEndpoints.updateObject(space_id, task_id, update_data)
                except Exception as update_error:
                    message = str(update_error)
                    priority_key_error = 'unknown property key: "priority"'
                    if priority and priority_key_error in message:
                        fallback_properties = [
                            prop for prop in properties if prop.get("key") != "priority"
                        ]
                        if fallback_properties:
                            fallback_data = {
                                "name": title,
                                "properties": fallback_properties,
                            }
                            self._client._apiEndpoints.updateObject(
                                space_id,
                                task_id,
                                fallback_data,
                            )
                        console.print(
                            "[yellow]Warning: Priority property is not configured "
                            "in this AnyType space. Task created without priority.[/yellow]"
                        )
                    else:
                        raise

            # Try to add tags separately (they may fail if tags don't exist)
            if tags:
                try:
                    tag_properties = [
                        {
                            "object": "property",
                            "key": "tag",
                            "name": "Tag",
                            "format": "multi_select",
                            "multi_select": list(tags),
                        }
                    ]
                    tag_update = {
                        "name": title,
                        "properties": tag_properties,
                    }
                    self._client._apiEndpoints.updateObject(space_id, task_id, tag_update)
                except Exception as tag_error:
                    # Tags failed - likely because they don't exist in AnyType
                    # Task is still created, just without tags
                    console.print(
                        f"[yellow]Warning: Could not set tags (they may not exist "
                        f"in AnyType): {tag_error}[/yellow]"
                    )

            return task_id

        except Exception as e:
            raise RuntimeError(f"Failed to create task: {e}")

    def delete_object(self, space_id: str, object_id: str) -> bool:
        """Delete an object from AnyType.

        Args:
            space_id: AnyType space ID
            object_id: Object ID to delete

        Returns:
            True if successful, False otherwise
        """
        if not self._authenticated:
            raise RuntimeError("Not authenticated. Call connect() first.")

        try:
            self._client._apiEndpoints.deleteObject(space_id, object_id)
            return True
        except Exception as e:
            console.print(f"[red]Error deleting object: {e}[/red]")
            return False

    def get_page_content(self, space_id: str, page_id: str) -> str:
        """Get the content of a page.

        Args:
            space_id: AnyType space ID
            page_id: Page object ID

        Returns:
            Page content as string

        Raises:
            RuntimeError: If not authenticated or page not found
        """
        if not self._authenticated:
            raise RuntimeError("Not authenticated. Call connect() first.")

        try:
            space = self._client.get_space(space_id)
            obj = space.get_object(page_id)

            # AnyType stores content in 'markdown' field, not 'body' or 'content'
            # The library doesn't map this correctly, so we check multiple fields
            content = getattr(obj, "markdown", "")
            if not content:
                content = getattr(obj, "body", "")
            if not content:
                content = getattr(obj, "snippet", "")
            if not content:
                content = getattr(obj, "description", "")

            return content or ""

        except Exception as e:
            raise RuntimeError(f"Failed to get page content: {e}")
