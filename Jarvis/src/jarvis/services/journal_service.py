"""Journal service for journal entry operations.

This module provides a high-level service for journal operations that
handles capability checking, adapter selection, and error translation.
"""

from datetime import date

from ..adapters.base import KnowledgeBaseAdapter
from ..adapters.exceptions import NotSupportedError
from ..models import JournalEntry
from .adapter_service import get_adapter, ensure_connected, check_capability


class JournalService:
    """Service for journal operations.

    Provides a high-level interface for journal CRUD that works with
    any backend adapter and handles capability checking.

    Usage:
        service = JournalService()
        service.connect()
        entry = service.create_entry("Morning thoughts", content="...")
    """

    def __init__(self, backend: str | None = None):
        """Initialize journal service.

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

    def _check_journal_capability(self) -> None:
        """Check if journal capability is supported.

        Raises:
            NotSupportedError: If journal is not supported
        """
        if not check_capability(self.adapter, "journal"):
            raise NotSupportedError(
                f"Backend '{self.adapter.backend_name}' does not support journal entries",
                backend=self.adapter.backend_name,
                capability="journal",
            )

    def create_entry(
        self,
        title: str,
        content: str,
        space_id: str | None = None,
        entry_date: date | None = None,
        tags: list[str] | None = None,
    ) -> JournalEntry:
        """Create a new journal entry.

        Args:
            title: Entry title
            content: Entry content (markdown supported)
            space_id: Optional space ID (uses default if not provided)
            entry_date: Optional entry date (defaults to today)
            tags: Optional list of tag names

        Returns:
            Created JournalEntry object

        Raises:
            NotSupportedError: If journal not supported
            ConnectionError: If not connected
        """
        self._check_journal_capability()

        if space_id is None:
            space_id = self.adapter.get_default_space()

        if entry_date is None:
            entry_date = date.today()

        return self.adapter.create_journal_entry(
            space_id=space_id,
            title=title,
            content=content,
            entry_date=entry_date,
            tags=tags,
        )

    def get_entry(self, entry_id: str, space_id: str | None = None) -> JournalEntry:
        """Get a single journal entry by ID.

        Args:
            entry_id: Entry identifier
            space_id: Optional space ID (uses default if not provided)

        Returns:
            JournalEntry object

        Raises:
            NotFoundError: If entry doesn't exist
            NotSupportedError: If journal not supported
        """
        self._check_journal_capability()

        if space_id is None:
            space_id = self.adapter.get_default_space()

        return self.adapter.get_journal_entry(space_id, entry_id)

    def get_entries(
        self,
        space_id: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[JournalEntry]:
        """Get journal entries with optional filters.

        Args:
            space_id: Optional space ID (uses default if not provided)
            start_date: Filter entries on or after this date
            end_date: Filter entries on or before this date
            limit: Maximum number of entries to return
            offset: Number of entries to skip

        Returns:
            List of JournalEntry objects

        Raises:
            NotSupportedError: If journal not supported
        """
        self._check_journal_capability()

        if space_id is None:
            space_id = self.adapter.get_default_space()

        return self.adapter.get_journal_entries(
            space_id=space_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset,
        )

    def search_entries(
        self,
        query: str,
        space_id: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[JournalEntry]:
        """Search journal entries.

        Args:
            query: Search query string
            space_id: Optional space ID (uses default if not provided)
            limit: Maximum number of entries to return
            offset: Number of entries to skip

        Returns:
            List of matching JournalEntry objects

        Raises:
            NotSupportedError: If journal or search not supported
        """
        self._check_journal_capability()

        if not check_capability(self.adapter, "search"):
            raise NotSupportedError(
                f"Backend '{self.adapter.backend_name}' does not support search",
                backend=self.adapter.backend_name,
                capability="search",
            )

        if space_id is None:
            space_id = self.adapter.get_default_space()

        return self.adapter.search_journal_entries(
            space_id=space_id,
            query=query,
            limit=limit,
            offset=offset,
        )

    def update_entry(
        self,
        entry_id: str,
        space_id: str | None = None,
        title: str | None = None,
        content: str | None = None,
        entry_date: date | None = None,
        tags: list[str] | None = None,
    ) -> JournalEntry:
        """Update an existing journal entry.

        Args:
            entry_id: Entry identifier
            space_id: Optional space ID (uses default if not provided)
            title: New title (None to keep existing)
            content: New content (None to keep existing)
            entry_date: New entry date (None to keep existing)
            tags: New tags (None to keep existing)

        Returns:
            Updated JournalEntry object

        Raises:
            NotFoundError: If entry doesn't exist
            NotSupportedError: If journal not supported
        """
        self._check_journal_capability()

        if space_id is None:
            space_id = self.adapter.get_default_space()

        return self.adapter.update_journal_entry(
            space_id=space_id,
            entry_id=entry_id,
            title=title,
            content=content,
            entry_date=entry_date,
            tags=tags,
        )

    def delete_entry(self, entry_id: str, space_id: str | None = None) -> bool:
        """Delete a journal entry.

        Args:
            entry_id: Entry identifier
            space_id: Optional space ID (uses default if not provided)

        Returns:
            True if deleted successfully

        Raises:
            NotFoundError: If entry doesn't exist
            NotSupportedError: If journal not supported
        """
        self._check_journal_capability()

        if space_id is None:
            space_id = self.adapter.get_default_space()

        return self.adapter.delete_journal_entry(space_id, entry_id)
