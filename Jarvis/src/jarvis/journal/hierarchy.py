"""Journal hierarchy manager for AnyType integration.

Manages the Journal → Year → Month → Entry structure in AnyType.
"""

from datetime import date

from jarvis.anytype_client import AnyTypeClient


class JournalHierarchy:
    """Manages Journal → Year → Month hierarchy in AnyType.

    This class handles the creation and navigation of the journal
    folder structure in AnyType, ensuring entries are organized
    chronologically.

    Attributes:
        client: AnyType client instance
        space_id: AnyType space ID to work in
    """

    MONTHS = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ]

    def __init__(self, client: AnyTypeClient, space_id: str) -> None:
        """Initialize the hierarchy manager.

        Args:
            client: Connected AnyType client
            space_id: Space ID to manage journal in
        """
        self.client = client
        self.space_id = space_id
        self._journal_id: str | None = None
        self._year_cache: dict[int, str] = {}
        self._month_cache: dict[tuple[int, int], str] = {}

    def get_journal_collection(self) -> str:
        """Get or create the Journal collection.

        Returns:
            Journal collection object ID
        """
        if self._journal_id:
            return self._journal_id

        self._journal_id = self.client.get_or_create_collection(
            self.space_id, "Journal"
        )
        return self._journal_id

    def get_year_container(self, year: int) -> str:
        """Get or create a year container.

        Args:
            year: Year number (e.g., 2026)

        Returns:
            Year container object ID
        """
        if year in self._year_cache:
            return self._year_cache[year]

        journal_id = self.get_journal_collection()
        year_id = self.client.get_or_create_container(
            self.space_id, journal_id, str(year)
        )
        self._year_cache[year] = year_id
        return year_id

    def get_month_container(self, year: int, month: int) -> str:
        """Get or create a month container.

        Args:
            year: Year number
            month: Month number (1-12)

        Returns:
            Month container object ID

        Raises:
            ValueError: If month is not 1-12
        """
        if not 1 <= month <= 12:
            raise ValueError(f"Month must be 1-12, got {month}")

        cache_key = (year, month)
        if cache_key in self._month_cache:
            return self._month_cache[cache_key]

        year_id = self.get_year_container(year)
        month_name = self.MONTHS[month - 1]
        month_id = self.client.get_or_create_container(
            self.space_id, year_id, month_name
        )
        self._month_cache[cache_key] = month_id
        return month_id

    def get_path(self, entry_date: date) -> str:
        """Get the path string for a date.

        Args:
            entry_date: Date of the journal entry

        Returns:
            Path string like "Journal/2026/January"
        """
        month_name = self.MONTHS[entry_date.month - 1]
        return f"Journal/{entry_date.year}/{month_name}"

    def create_entry(
        self,
        entry_date: date,
        title: str,
        content: str,
    ) -> tuple[str, str, str, str]:
        """Create a journal entry in the correct location.

        Args:
            entry_date: Date of the entry
            title: Entry title (without day prefix)
            content: Entry content

        Returns:
            Tuple of (entry_id, journal_id, year_id, month_id)
        """
        # Ensure hierarchy exists
        journal_id = self.get_journal_collection()
        year_id = self.get_year_container(entry_date.year)
        month_id = self.get_month_container(entry_date.year, entry_date.month)

        # Create full title with day prefix
        full_title = f"{entry_date.day} - {title}"

        # Create the entry page
        entry_id = self.client.create_page(
            self.space_id,
            name=full_title,
            content=content,
            parent_id=month_id,
        )

        return entry_id, journal_id, year_id, month_id

    def clear_cache(self) -> None:
        """Clear all cached IDs.

        Useful when the hierarchy may have changed externally.
        """
        self._journal_id = None
        self._year_cache.clear()
        self._month_cache.clear()
