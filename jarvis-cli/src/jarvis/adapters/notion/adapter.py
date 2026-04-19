"""Notion adapter implementation.

Implements KnowledgeBaseAdapter for Notion as the backend.
Uses the official notion-sdk-py library.
"""

from datetime import date
from typing import TYPE_CHECKING, Any

from ...config import JarvisConfig, get_backend_token
from ...models import (
    BackendObject,
    JournalEntry,
    ObjectProperty,
    Priority,
    PropertyFormat,
    Space,
    Tag,
    Task,
)
from ..exceptions import (
    AuthError,
    ConfigError,
    ConnectionError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)
from ..retry import with_retry
from .mappings import (
    blocks_to_content,
    content_to_notion_blocks,
    journal_to_notion_properties,
    notion_to_journal_entry,
    notion_to_task,
    task_to_notion_properties,
)

if TYPE_CHECKING:
    from notion_client import Client

# Maximum title/content lengths
MAX_TITLE_LENGTH = 500
MAX_CONTENT_LENGTH = 10000


class NotionAdapter:
    """Adapter for Notion knowledge base.

    Uses Notion API via notion-sdk-py.

    Requires:
        - JARVIS_NOTION_TOKEN environment variable
        - Configured database IDs in config.yaml

    Example config:
        backends:
          notion:
            workspace_id: "abc123"
            task_database_id: "def456"
            journal_database_id: "ghi789"
    """

    # Pin Notion API version for stability
    NOTION_API_VERSION = "2022-06-28"

    def __init__(self, config: JarvisConfig | None = None) -> None:
        """Initialize the Notion adapter.

        Args:
            config: Optional Jarvis config. If None, uses default config.
        """
        self._config = config
        self._client: "Client | None" = None
        self._connected = False

    @property
    def capabilities(self) -> dict[str, bool]:
        """Declare supported capabilities.

        Returns:
            Dict mapping capability names to support status.
        """
        return {
            "tasks": True,
            "journal": True,
            "tags": True,
            "search": True,
            "priorities": True,
            "due_dates": True,
            "daily_notes": False,  # Notion doesn't auto-create daily pages
            "relations": True,
            "custom_properties": True,
        }

    @property
    def backend_name(self) -> str:
        """Return the backend identifier."""
        return "notion"

    def connect(self) -> None:
        """Connect to Notion API.

        Raises:
            AuthError: If token is missing or invalid.
            ConnectionError: If connection cannot be established.
        """
        try:
            # Import here to allow graceful failure if not installed
            from notion_client import Client
            from notion_client.errors import APIResponseError
        except ImportError as e:
            raise ConnectionError(
                "notion-client package is not installed. "
                "Install with: pip install notion-client",
                backend=self.backend_name,
            ) from e

        try:
            token = get_backend_token("notion")
        except Exception as e:
            raise AuthError(str(e), backend=self.backend_name) from e

        try:
            self._client = Client(auth=token, notion_version=self.NOTION_API_VERSION)
            # Verify connection by fetching user info
            self._client.users.me()
            self._connected = True
        except APIResponseError as e:
            if e.status == 401:
                raise AuthError(
                    "Invalid Notion token. Generate a new one at: "
                    "https://www.notion.so/my-integrations",
                    backend=self.backend_name,
                ) from e
            raise ConnectionError(
                f"Failed to connect to Notion: {e.message}",
                backend=self.backend_name,
            ) from e

    def disconnect(self) -> None:
        """Close connection to Notion (no-op, stateless API)."""
        self._client = None
        self._connected = False

    def is_connected(self) -> bool:
        """Check if currently connected to Notion.

        Returns:
            True if connected, False otherwise.
        """
        return self._connected and self._client is not None

    def _require_connection(self) -> None:
        """Ensure we're connected.

        Raises:
            ConnectionError: If not connected.
        """
        if not self.is_connected():
            raise ConnectionError("Not connected", backend=self.backend_name)

    def _require_notion_config(self) -> Any:
        """Get Notion config or raise.

        Returns:
            NotionConfig instance.

        Raises:
            ConfigError: If Notion is not configured.
        """
        if self._config is None or self._config.backends.notion is None:
            raise ConfigError(
                "Notion backend is not configured. "
                "Add [backends.notion] section to ~/.jarvis/config.yaml",
                backend=self.backend_name,
            )
        return self._config.backends.notion

    def _validate_title(self, title: str) -> None:
        """Validate title is not empty and within limits.

        Args:
            title: Title to validate.

        Raises:
            ValidationError: If title is invalid.
        """
        if not title or not title.strip():
            raise ValidationError(
                "Title cannot be empty", backend=self.backend_name, field="title"
            )
        if len(title) > MAX_TITLE_LENGTH:
            raise ValidationError(
                f"Title exceeds maximum length of {MAX_TITLE_LENGTH} characters",
                backend=self.backend_name,
                field="title",
            )

    def _validate_offset(self, offset: int) -> None:
        """Validate offset is non-negative.

        Args:
            offset: Offset to validate.

        Raises:
            ValidationError: If offset is negative.
        """
        if offset < 0:
            raise ValidationError(
                "Offset must be non-negative",
                backend=self.backend_name,
                field="offset",
            )

    def _handle_api_error(self, error: Any) -> None:
        """Convert Notion API errors to typed exceptions.

        Args:
            error: APIResponseError from notion-client.

        Raises:
            AuthError: For 401 errors.
            NotFoundError: For 404 errors.
            RateLimitError: For 429 errors.
            ConnectionError: For other errors.
        """
        error_message = str(error)

        if error.status == 401:
            raise AuthError(
                "Notion authentication failed", backend=self.backend_name
            ) from error
        elif error.status == 404:
            raise NotFoundError(error_message, backend=self.backend_name) from error
        elif error.status == 429:
            retry_after = error.headers.get("Retry-After") if error.headers else None
            raise RateLimitError(
                "Notion rate limit exceeded",
                backend=self.backend_name,
                retry_after=float(retry_after) if retry_after else None,
            ) from error
        else:
            raise ConnectionError(
                f"Notion API error: {error_message}", backend=self.backend_name
            ) from error

    # =========================================================================
    # Space Operations
    # =========================================================================

    def list_spaces(self) -> list[Space]:
        """Notion doesn't have spaces - return workspace as single space.

        Returns:
            List with single Space representing the Notion workspace.

        Raises:
            ConnectionError: If not connected.
        """
        self._require_connection()
        notion_config = self._require_notion_config()

        return [
            Space(
                id=notion_config.workspace_id,
                name="Notion Workspace",
                backend=self.backend_name,
            )
        ]

    def get_default_space(self) -> str:
        """Get the Notion workspace ID.

        Returns:
            Workspace ID.

        Raises:
            ConfigError: If Notion not configured.
        """
        notion_config = self._require_notion_config()
        return notion_config.workspace_id

    def set_default_space(self, space_id: str) -> None:
        """Set default space (no-op for Notion).

        Notion only has one workspace per integration.

        Args:
            space_id: Ignored.
        """
        # Notion only has one workspace per integration
        pass

    # =========================================================================
    # Task Operations
    # =========================================================================

    @with_retry(max_attempts=3, base_delay=1.0)
    def create_task(
        self,
        space_id: str,
        title: str,
        due_date: date | None = None,
        priority: Priority | None = None,
        tags: list[str] | None = None,
        description: str | None = None,
    ) -> Task:
        """Create a task in Notion Tasks database.

        Args:
            space_id: Workspace ID (used for consistency).
            title: Task title.
            due_date: Optional due date.
            priority: Optional priority level.
            tags: Optional list of tag names.
            description: Optional task description.

        Returns:
            Created Task object.

        Raises:
            ConnectionError: If not connected.
            ValidationError: If title is invalid.
        """
        from notion_client.errors import APIResponseError

        self._require_connection()
        self._validate_title(title)
        notion_config = self._require_notion_config()

        properties = task_to_notion_properties(
            title=title,
            due_date=due_date,
            priority=priority,
            tags=tags,
            mappings=notion_config.property_mappings,
        )

        # Add description as page content
        children = None
        if description:
            children = content_to_notion_blocks(description)

        try:
            response = self._client.pages.create(  # type: ignore[union-attr]
                parent={"database_id": notion_config.task_database_id},
                properties=properties,
                children=children if children else None,
            )
            return notion_to_task(response, space_id)
        except APIResponseError as e:
            self._handle_api_error(e)
            raise  # Never reached, but makes type checker happy

    @with_retry(max_attempts=3, base_delay=1.0)
    def get_task(self, space_id: str, task_id: str) -> Task:
        """Get a single task by ID.

        Args:
            space_id: Workspace ID.
            task_id: Notion page ID.

        Returns:
            Task object.

        Raises:
            NotFoundError: If task doesn't exist.
            ConnectionError: If not connected.
        """
        from notion_client.errors import APIResponseError

        self._require_connection()

        try:
            response = self._client.pages.retrieve(page_id=task_id)  # type: ignore[union-attr]
            return notion_to_task(response, space_id)
        except APIResponseError as e:
            self._handle_api_error(e)
            raise

    @with_retry(max_attempts=3, base_delay=1.0)
    def get_tasks(
        self,
        space_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
        include_done: bool = False,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Task]:
        """Query tasks from Notion database.

        Args:
            space_id: Workspace ID.
            start_date: Filter tasks due on or after this date.
            end_date: Filter tasks due on or before this date.
            include_done: Include completed tasks.
            limit: Maximum number of tasks to return.
            offset: Number of tasks to skip.

        Returns:
            List of Task objects.

        Raises:
            ConnectionError: If not connected.
            ValidationError: If offset is negative.
        """
        from notion_client.errors import APIResponseError

        self._require_connection()
        self._validate_offset(offset)
        notion_config = self._require_notion_config()
        mappings = notion_config.property_mappings

        # Build filter
        filters: list[dict[str, Any]] = []

        if not include_done:
            filters.append(
                {
                    "property": mappings.get("done", "Done"),
                    "checkbox": {"equals": False},
                }
            )

        if start_date:
            filters.append(
                {
                    "property": mappings.get("due_date", "Due Date"),
                    "date": {"on_or_after": start_date.isoformat()},
                }
            )

        if end_date:
            filters.append(
                {
                    "property": mappings.get("due_date", "Due Date"),
                    "date": {"on_or_before": end_date.isoformat()},
                }
            )

        filter_obj = None
        if filters:
            filter_obj = {"and": filters} if len(filters) > 1 else filters[0]

        try:
            tasks: list[Task] = []
            has_more = True
            start_cursor = None
            skipped = 0

            while has_more:
                page_size = min(100, (limit or 100) + offset - len(tasks))
                if page_size <= 0:
                    break

                response = self._client.databases.query(  # type: ignore[union-attr]
                    database_id=notion_config.task_database_id,
                    filter=filter_obj,
                    start_cursor=start_cursor,
                    page_size=page_size,
                )

                for page in response["results"]:
                    if skipped < offset:
                        skipped += 1
                        continue

                    tasks.append(notion_to_task(page, space_id))

                    if limit and len(tasks) >= limit:
                        return tasks

                has_more = response.get("has_more", False)
                start_cursor = response.get("next_cursor")

            return tasks
        except APIResponseError as e:
            self._handle_api_error(e)
            raise

    @with_retry(max_attempts=3, base_delay=1.0)
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

        Args:
            space_id: Workspace ID.
            task_id: Notion page ID.
            title: New title (optional).
            due_date: New due date (optional).
            priority: New priority (optional).
            tags: New tags list (optional).
            description: New description (optional).
            is_done: New completion status (optional).

        Returns:
            Updated Task object.

        Raises:
            NotFoundError: If task doesn't exist.
            ConnectionError: If not connected.
            ValidationError: If title is invalid.
        """
        from notion_client.errors import APIResponseError

        self._require_connection()
        if title is not None:
            self._validate_title(title)
        notion_config = self._require_notion_config()
        mappings = notion_config.property_mappings

        # Build properties to update
        properties: dict[str, Any] = {}

        if title is not None:
            properties[mappings.get("title", "Name")] = {
                "title": [{"text": {"content": title}}]
            }

        if due_date is not None:
            properties[mappings.get("due_date", "Due Date")] = {
                "date": {"start": due_date.isoformat()}
            }

        if priority is not None:
            properties[mappings.get("priority", "Priority")] = {
                "select": {"name": priority.value.capitalize()}
            }

        if tags is not None:
            properties[mappings.get("tags", "Tags")] = {
                "multi_select": [{"name": tag} for tag in tags]
            }

        if is_done is not None:
            properties[mappings.get("done", "Done")] = {"checkbox": is_done}

        try:
            # Update page properties
            if properties:
                self._client.pages.update(page_id=task_id, properties=properties)  # type: ignore[union-attr]

            # Update description (replace all content)
            if description is not None:
                # First, archive existing blocks
                existing_blocks = self._client.blocks.children.list(block_id=task_id)  # type: ignore[union-attr]
                for block in existing_blocks.get("results", []):
                    self._client.blocks.delete(block_id=block["id"])  # type: ignore[union-attr]

                # Add new content
                if description:
                    blocks = content_to_notion_blocks(description)
                    if blocks:
                        self._client.blocks.children.append(  # type: ignore[union-attr]
                            block_id=task_id, children=blocks
                        )

            # Fetch and return updated task
            response = self._client.pages.retrieve(page_id=task_id)  # type: ignore[union-attr]
            return notion_to_task(response, space_id)
        except APIResponseError as e:
            self._handle_api_error(e)
            raise

    @with_retry(max_attempts=3, base_delay=1.0)
    def delete_task(self, space_id: str, task_id: str) -> bool:
        """Delete (archive) a task.

        Notion doesn't truly delete - it archives the page.

        Args:
            space_id: Workspace ID.
            task_id: Notion page ID.

        Returns:
            True if archived successfully.

        Raises:
            NotFoundError: If task doesn't exist.
            ConnectionError: If not connected.
        """
        from notion_client.errors import APIResponseError

        self._require_connection()

        try:
            self._client.pages.update(page_id=task_id, archived=True)  # type: ignore[union-attr]
            return True
        except APIResponseError as e:
            self._handle_api_error(e)
            raise

    # =========================================================================
    # Journal Operations
    # =========================================================================

    @with_retry(max_attempts=3, base_delay=1.0)
    def create_journal_entry(
        self,
        space_id: str,
        content: str,
        title: str | None = None,
        entry_date: date | None = None,
    ) -> JournalEntry:
        """Create a new journal entry.

        Args:
            space_id: Workspace ID.
            content: Entry content (markdown).
            title: Optional title.
            entry_date: Date for entry (defaults to today).

        Returns:
            Created JournalEntry object.

        Raises:
            ConnectionError: If not connected.
        """
        from notion_client.errors import APIResponseError

        self._require_connection()
        notion_config = self._require_notion_config()

        # Generate title from content if not provided
        if not title:
            title = content[:50] + "..." if len(content) > 50 else content
            title = title.replace("\n", " ")

        entry_date = entry_date or date.today()

        properties = journal_to_notion_properties(
            title=title,
            entry_date=entry_date,
            mappings=notion_config.property_mappings,
        )

        # Add content as page blocks
        children = content_to_notion_blocks(content) if content else None

        try:
            response = self._client.pages.create(  # type: ignore[union-attr]
                parent={"database_id": notion_config.journal_database_id},
                properties=properties,
                children=children if children else None,
            )

            entry = notion_to_journal_entry(response, space_id)
            # Set content since we know it
            entry = JournalEntry(
                id=entry.id,
                space_id=entry.space_id,
                title=entry.title,
                content=content,
                entry_date=entry.entry_date,
                tags=entry.tags,
                created_at=entry.created_at,
            )
            return entry
        except APIResponseError as e:
            self._handle_api_error(e)
            raise

    @with_retry(max_attempts=3, base_delay=1.0)
    def get_journal_entry(self, space_id: str, entry_id: str) -> JournalEntry:
        """Get a single journal entry by ID.

        Args:
            space_id: Workspace ID.
            entry_id: Notion page ID.

        Returns:
            JournalEntry object.

        Raises:
            NotFoundError: If entry doesn't exist.
            ConnectionError: If not connected.
        """
        from notion_client.errors import APIResponseError

        self._require_connection()

        try:
            # Get page properties
            response = self._client.pages.retrieve(page_id=entry_id)  # type: ignore[union-attr]
            entry = notion_to_journal_entry(response, space_id)

            # Get page content
            blocks_response = self._client.blocks.children.list(block_id=entry_id)  # type: ignore[union-attr]
            content = blocks_to_content(blocks_response.get("results", []))

            # Return with content
            return JournalEntry(
                id=entry.id,
                space_id=entry.space_id,
                title=entry.title,
                content=content,
                entry_date=entry.entry_date,
                tags=entry.tags,
                created_at=entry.created_at,
            )
        except APIResponseError as e:
            self._handle_api_error(e)
            raise

    @with_retry(max_attempts=3, base_delay=1.0)
    def get_journal_entries(
        self,
        space_id: str,
        limit: int = 10,
        offset: int = 0,
    ) -> list[JournalEntry]:
        """List journal entries with pagination.

        Args:
            space_id: Workspace ID.
            limit: Maximum entries to return.
            offset: Number of entries to skip.

        Returns:
            List of JournalEntry objects, newest first.

        Raises:
            ConnectionError: If not connected.
            ValidationError: If offset is negative.
        """
        from notion_client.errors import APIResponseError

        self._require_connection()
        self._validate_offset(offset)
        notion_config = self._require_notion_config()
        mappings = notion_config.property_mappings

        try:
            entries: list[JournalEntry] = []
            has_more = True
            start_cursor = None
            skipped = 0

            # Sort by date descending
            sorts = [{"property": mappings.get("date", "Date"), "direction": "descending"}]

            while has_more:
                page_size = min(100, limit + offset - len(entries))
                if page_size <= 0:
                    break

                response = self._client.databases.query(  # type: ignore[union-attr]
                    database_id=notion_config.journal_database_id,
                    sorts=sorts,
                    start_cursor=start_cursor,
                    page_size=page_size,
                )

                for page in response["results"]:
                    if skipped < offset:
                        skipped += 1
                        continue

                    entries.append(notion_to_journal_entry(page, space_id))

                    if len(entries) >= limit:
                        return entries

                has_more = response.get("has_more", False)
                start_cursor = response.get("next_cursor")

            return entries
        except APIResponseError as e:
            self._handle_api_error(e)
            raise

    @with_retry(max_attempts=3, base_delay=1.0)
    def update_journal_entry(
        self,
        space_id: str,
        entry_id: str,
        content: str | None = None,
        title: str | None = None,
    ) -> JournalEntry:
        """Update an existing journal entry.

        Args:
            space_id: Workspace ID.
            entry_id: Notion page ID.
            content: New content (optional).
            title: New title (optional).

        Returns:
            Updated JournalEntry object.

        Raises:
            NotFoundError: If entry doesn't exist.
            ConnectionError: If not connected.
        """
        from notion_client.errors import APIResponseError

        self._require_connection()
        notion_config = self._require_notion_config()
        mappings = notion_config.property_mappings

        try:
            # Update title if provided
            if title is not None:
                properties = {
                    mappings.get("title", "Name"): {
                        "title": [{"text": {"content": title}}]
                    }
                }
                self._client.pages.update(page_id=entry_id, properties=properties)  # type: ignore[union-attr]

            # Update content if provided
            if content is not None:
                # Archive existing blocks
                existing_blocks = self._client.blocks.children.list(block_id=entry_id)  # type: ignore[union-attr]
                for block in existing_blocks.get("results", []):
                    self._client.blocks.delete(block_id=block["id"])  # type: ignore[union-attr]

                # Add new content
                if content:
                    blocks = content_to_notion_blocks(content)
                    if blocks:
                        self._client.blocks.children.append(  # type: ignore[union-attr]
                            block_id=entry_id, children=blocks
                        )

            # Fetch and return updated entry
            return self.get_journal_entry(space_id, entry_id)
        except APIResponseError as e:
            self._handle_api_error(e)
            raise

    @with_retry(max_attempts=3, base_delay=1.0)
    def delete_journal_entry(self, space_id: str, entry_id: str) -> bool:
        """Delete (archive) a journal entry.

        Args:
            space_id: Workspace ID.
            entry_id: Notion page ID.

        Returns:
            True if archived successfully.

        Raises:
            NotFoundError: If entry doesn't exist.
            ConnectionError: If not connected.
        """
        from notion_client.errors import APIResponseError

        self._require_connection()

        try:
            self._client.pages.update(page_id=entry_id, archived=True)  # type: ignore[union-attr]
            return True
        except APIResponseError as e:
            self._handle_api_error(e)
            raise

    @with_retry(max_attempts=3, base_delay=1.0)
    def search_journal(
        self,
        space_id: str,
        query: str,
        limit: int = 10,
        offset: int = 0,
    ) -> list[JournalEntry]:
        """Search journal entries by content.

        Args:
            space_id: Workspace ID.
            query: Search query string.
            limit: Maximum results to return.
            offset: Number of results to skip.

        Returns:
            List of matching JournalEntry objects.

        Raises:
            ConnectionError: If not connected.
            ValidationError: If offset is negative.
        """
        from notion_client.errors import APIResponseError

        self._require_connection()
        self._validate_offset(offset)
        notion_config = self._require_notion_config()

        try:
            # Use Notion search API
            response = self._client.search(  # type: ignore[union-attr]
                query=query,
                filter={"property": "object", "value": "page"},
                page_size=min(100, limit + offset),
            )

            entries: list[JournalEntry] = []
            skipped = 0

            for page in response.get("results", []):
                # Filter to only journal database pages
                parent = page.get("parent", {})
                if parent.get("database_id") != notion_config.journal_database_id:
                    continue

                if skipped < offset:
                    skipped += 1
                    continue

                entries.append(notion_to_journal_entry(page, space_id))

                if len(entries) >= limit:
                    break

            return entries
        except APIResponseError as e:
            self._handle_api_error(e)
            raise

    # =========================================================================
    # Tag Operations
    # =========================================================================

    @with_retry(max_attempts=3, base_delay=1.0)
    def list_tags(self, space_id: str) -> list[Tag]:
        """List all tags from the tasks database.

        Notion stores tags as multi-select options in the database schema.

        Args:
            space_id: Workspace ID.

        Returns:
            List of Tag objects.

        Raises:
            ConnectionError: If not connected.
        """
        from notion_client.errors import APIResponseError

        self._require_connection()
        notion_config = self._require_notion_config()
        mappings = notion_config.property_mappings

        try:
            # Get database schema to extract tag options
            response = self._client.databases.retrieve(  # type: ignore[union-attr]
                database_id=notion_config.task_database_id
            )

            tags_property = response["properties"].get(
                mappings.get("tags", "Tags"), {}
            )

            if tags_property.get("type") != "multi_select":
                return []

            options = tags_property.get("multi_select", {}).get("options", [])
            return [
                Tag(id=opt["id"], name=opt["name"], color=opt.get("color"))
                for opt in options
            ]
        except APIResponseError as e:
            self._handle_api_error(e)
            raise

    def create_tag(self, space_id: str, name: str, color: str | None = None) -> Tag:
        """Create a new tag.

        In Notion, tags are created automatically when used in multi-select.
        This method just returns a Tag object with the given name.

        Args:
            space_id: Workspace ID.
            name: Tag name.
            color: Optional color (Notion colors: default, gray, brown, orange,
                   yellow, green, blue, purple, pink, red).

        Returns:
            Tag object.
        """
        # Notion creates tags automatically when first used
        # Valid colors: default, gray, brown, orange, yellow, green, blue, purple, pink, red
        return Tag(id=name, name=name, color=color)

    # =========================================================================
    # Generic Object Operations
    # =========================================================================

    # Map Notion property type strings to PropertyFormat
    _NOTION_FORMAT_MAP: dict[str, PropertyFormat] = {
        "title": PropertyFormat.TEXT,
        "rich_text": PropertyFormat.TEXT,
        "number": PropertyFormat.NUMBER,
        "date": PropertyFormat.DATE,
        "checkbox": PropertyFormat.CHECKBOX,
        "select": PropertyFormat.SELECT,
        "multi_select": PropertyFormat.MULTI_SELECT,
        "url": PropertyFormat.URL,
        "email": PropertyFormat.EMAIL,
        "phone_number": PropertyFormat.PHONE,
        "files": PropertyFormat.FILES,
        "relation": PropertyFormat.OBJECTS,
    }

    # Notion system/read-only property types
    _NOTION_SYSTEM_TYPES = {
        "created_time",
        "last_edited_time",
        "created_by",
        "last_edited_by",
        "formula",
        "rollup",
        "unique_id",
    }

    @with_retry(max_attempts=3, base_delay=1.0)
    def get_object(self, space_id: str, object_id: str) -> BackendObject:
        """Get any Notion page/database item by ID.

        Args:
            space_id: Workspace ID.
            object_id: Notion page ID.

        Returns:
            BackendObject with all properties populated.

        Raises:
            NotFoundError: If object doesn't exist.
            ConnectionError: If not connected.
        """
        from datetime import datetime

        from notion_client.errors import APIResponseError

        self._require_connection()

        try:
            response = self._client.pages.retrieve(  # type: ignore[union-attr]
                page_id=object_id
            )
        except APIResponseError as e:
            self._handle_api_error(e)
            raise

        return self._notion_page_to_backend_object(response, space_id)

    @with_retry(max_attempts=3, base_delay=1.0)
    def update_object(
        self,
        space_id: str,
        object_id: str,
        updates: dict[str, object],
    ) -> BackendObject:
        """Update a Notion page's properties by key-value pairs.

        Args:
            space_id: Workspace ID.
            object_id: Notion page ID.
            updates: Dict mapping property names to new values.

        Returns:
            Updated BackendObject.

        Raises:
            NotFoundError: If object doesn't exist.
            ConnectionError: If not connected.
            ValidationError: If a property name is invalid.
        """
        from notion_client.errors import APIResponseError

        self._require_connection()

        # Fetch current page to understand property types
        try:
            page = self._client.pages.retrieve(  # type: ignore[union-attr]
                page_id=object_id
            )
        except APIResponseError as e:
            self._handle_api_error(e)
            raise

        page_properties = page.get("properties", {})  # type: ignore[union-attr]
        notion_updates: dict[str, Any] = {}
        icon_update = None
        body_content: str | None = None

        for key, new_value in updates.items():
            # Handle special keys
            if key == "icon":
                icon_update = {"emoji": str(new_value), "type": "emoji"}
                continue

            if key in ("body", "content"):
                body_content = str(new_value)
                continue

            # Find the property in the page
            if key not in page_properties:
                # Try case-insensitive match
                matched = None
                for prop_name in page_properties:
                    if prop_name.lower() == key.lower():
                        matched = prop_name
                        break
                if not matched:
                    raise ValidationError(
                        f"Property '{key}' not found on this object. "
                        f"Available: "
                        f"{', '.join(page_properties.keys())}",
                        backend="notion",
                    )
                key = matched

            prop_data = page_properties[key]
            prop_type = prop_data.get("type", "")
            notion_updates[key] = self._build_notion_property_update(
                prop_type, new_value
            )

        try:
            update_kwargs: dict[str, Any] = {"page_id": object_id}
            if notion_updates:
                update_kwargs["properties"] = notion_updates
            if icon_update:
                update_kwargs["icon"] = icon_update

            self._client.pages.update(  # type: ignore[union-attr]
                **update_kwargs
            )

            # Update body/content (replace all blocks)
            if body_content is not None:
                existing_blocks = (
                    self._client.blocks.children.list(  # type: ignore[union-attr]
                        block_id=object_id
                    )
                )
                for block in existing_blocks.get("results", []):
                    self._client.blocks.delete(  # type: ignore[union-attr]
                        block_id=block["id"]
                    )

                if body_content:
                    blocks = content_to_notion_blocks(body_content)
                    if blocks:
                        self._client.blocks.children.append(  # type: ignore[union-attr]
                            block_id=object_id, children=blocks
                        )

            # Re-fetch and return
            return self.get_object(space_id, object_id)
        except APIResponseError as e:
            self._handle_api_error(e)
            raise

    def _build_notion_property_update(
        self, prop_type: str, value: object
    ) -> dict[str, Any]:
        """Build a Notion API property update payload.

        Args:
            prop_type: Notion property type string.
            value: New value to set.

        Returns:
            Dict suitable for the Notion pages.update API.
        """
        if prop_type == "title":
            return {"title": [{"text": {"content": str(value)}}]}
        elif prop_type == "rich_text":
            return {"rich_text": [{"text": {"content": str(value)}}]}
        elif prop_type == "number":
            return {"number": float(str(value))}
        elif prop_type == "date":
            val = str(value)
            return {"date": {"start": val[:10]}}  # YYYY-MM-DD
        elif prop_type == "checkbox":
            if isinstance(value, str):
                return {
                    "checkbox": value.lower() in (
                        "true", "yes", "1", "on",
                    )
                }
            return {"checkbox": bool(value)}
        elif prop_type == "select":
            return {"select": {"name": str(value)}}
        elif prop_type == "multi_select":
            if isinstance(value, str):
                tags = [
                    t.strip() for t in value.split(",") if t.strip()
                ]
            elif isinstance(value, list):
                tags = [str(t) for t in value]
            else:
                tags = [str(value)]
            return {"multi_select": [{"name": t} for t in tags]}
        elif prop_type == "url":
            return {"url": str(value)}
        elif prop_type == "email":
            return {"email": str(value)}
        elif prop_type == "phone_number":
            return {"phone_number": str(value)}
        else:
            # Best effort: treat as rich_text
            return {"rich_text": [{"text": {"content": str(value)}}]}

    def _notion_page_to_backend_object(
        self, page: Any, space_id: str
    ) -> BackendObject:
        """Convert a Notion page API response to BackendObject.

        Args:
            page: Raw Notion page response dict.
            space_id: Workspace ID.

        Returns:
            BackendObject with all properties mapped.
        """
        from datetime import datetime

        page_id = page.get("id", "")
        page_properties = page.get("properties", {})

        # Determine object type from parent
        parent = page.get("parent", {})
        if parent.get("type") == "database_id":
            object_type = "Database Item"
        elif parent.get("type") == "page_id":
            object_type = "Page"
        else:
            object_type = "Page"

        # Extract title (find the title property)
        name = "Untitled"
        for prop_name, prop_data in page_properties.items():
            if prop_data.get("type") == "title":
                title_arr = prop_data.get("title", [])
                if title_arr:
                    name = "".join(
                        t.get("plain_text", "") for t in title_arr
                    )
                break

        # Icon
        icon = ""
        icon_data = page.get("icon")
        if icon_data:
            if icon_data.get("type") == "emoji":
                icon = icon_data.get("emoji", "")

        # Convert all properties
        properties: list[ObjectProperty] = []
        for prop_name, prop_data in page_properties.items():
            prop_type = prop_data.get("type", "")
            fmt = self._NOTION_FORMAT_MAP.get(
                prop_type, PropertyFormat.UNKNOWN
            )
            is_system = prop_type in self._NOTION_SYSTEM_TYPES
            value = self._extract_notion_property_value(
                prop_data, prop_type
            )

            properties.append(
                ObjectProperty(
                    key=prop_name,
                    name=prop_name,
                    format=fmt,
                    value=value,
                    raw=prop_data,
                    is_system=is_system,
                )
            )

        # Timestamps
        created_at = None
        updated_at = None
        created_str = page.get("created_time")
        if created_str:
            try:
                created_at = datetime.fromisoformat(
                    created_str.replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                pass
        updated_str = page.get("last_edited_time")
        if updated_str:
            try:
                updated_at = datetime.fromisoformat(
                    updated_str.replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                pass

        return BackendObject(
            id=page_id,
            space_id=space_id,
            name=name,
            object_type=object_type,
            type_key=(
                parent.get("database_id", "")
                or parent.get("page_id", "")
            ),
            icon=icon,
            properties=properties,
            created_at=created_at,
            updated_at=updated_at,
            backend="notion",
            raw=page,
        )

    @staticmethod
    def _extract_notion_property_value(
        prop_data: dict, prop_type: str
    ) -> Any:
        """Extract a display value from a Notion property.

        Args:
            prop_data: Property data dict from Notion API.
            prop_type: Property type string.

        Returns:
            Extracted value, or None.
        """
        if prop_type == "title":
            arr = prop_data.get("title", [])
            return (
                "".join(t.get("plain_text", "") for t in arr)
                if arr
                else None
            )
        elif prop_type == "rich_text":
            arr = prop_data.get("rich_text", [])
            return (
                "".join(t.get("plain_text", "") for t in arr)
                if arr
                else None
            )
        elif prop_type == "number":
            return prop_data.get("number")
        elif prop_type == "date":
            date_obj = prop_data.get("date")
            return date_obj.get("start") if date_obj else None
        elif prop_type == "checkbox":
            return prop_data.get("checkbox", False)
        elif prop_type == "select":
            sel = prop_data.get("select")
            return sel.get("name") if sel else None
        elif prop_type == "multi_select":
            options = prop_data.get("multi_select", [])
            return (
                [o.get("name", "") for o in options] if options else []
            )
        elif prop_type == "url":
            return prop_data.get("url")
        elif prop_type == "email":
            return prop_data.get("email")
        elif prop_type == "phone_number":
            return prop_data.get("phone_number")
        elif prop_type == "created_time":
            return prop_data.get("created_time")
        elif prop_type == "last_edited_time":
            return prop_data.get("last_edited_time")
        elif prop_type == "created_by":
            user = prop_data.get("created_by", {})
            return user.get("name") or user.get("id")
        elif prop_type == "last_edited_by":
            user = prop_data.get("last_edited_by", {})
            return user.get("name") or user.get("id")
        elif prop_type == "relation":
            relations = prop_data.get("relation", [])
            return (
                [r.get("id", "") for r in relations]
                if relations
                else []
            )
        elif prop_type == "files":
            files = prop_data.get("files", [])
            return (
                [f.get("name", "") for f in files] if files else []
            )
        elif prop_type == "formula":
            formula = prop_data.get("formula", {})
            f_type = formula.get("type")
            return formula.get(f_type) if f_type else None
        elif prop_type == "unique_id":
            uid = prop_data.get("unique_id", {})
            prefix = uid.get("prefix", "")
            number = uid.get("number", "")
            return f"{prefix}-{number}" if prefix else str(number)
        return None
