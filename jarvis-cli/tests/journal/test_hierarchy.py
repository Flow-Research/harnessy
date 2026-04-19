"""Tests for journal hierarchy manager."""

from datetime import date
from unittest.mock import MagicMock

import pytest

from jarvis.journal.hierarchy import JournalHierarchy


@pytest.fixture
def mock_client() -> MagicMock:
    """Create a mock AnyType client."""
    client = MagicMock()
    client.get_or_create_collection.return_value = "journal_id_123"
    client.get_or_create_container.return_value = "container_id_456"
    client.create_page.return_value = "entry_id_789"
    return client


@pytest.fixture
def hierarchy(mock_client: MagicMock) -> JournalHierarchy:
    """Create a hierarchy manager with mock client."""
    return JournalHierarchy(mock_client, "space_123")


class TestJournalHierarchy:
    """Tests for JournalHierarchy class."""

    def test_init(self, mock_client: MagicMock) -> None:
        """Test hierarchy initialization."""
        h = JournalHierarchy(mock_client, "space_123")

        assert h.client == mock_client
        assert h.space_id == "space_123"
        assert h._journal_id is None
        assert h._year_cache == {}
        assert h._month_cache == {}

    def test_months_constant(self) -> None:
        """Test that MONTHS constant is correct."""
        assert len(JournalHierarchy.MONTHS) == 12
        assert JournalHierarchy.MONTHS[0] == "January"
        assert JournalHierarchy.MONTHS[11] == "December"


class TestGetJournalCollection:
    """Tests for get_journal_collection method."""

    def test_creates_collection_on_first_call(
        self, hierarchy: JournalHierarchy, mock_client: MagicMock
    ) -> None:
        """Test that collection is created on first call."""
        result = hierarchy.get_journal_collection()

        assert result == "journal_id_123"
        mock_client.get_or_create_collection.assert_called_once_with(
            "space_123", "Journal"
        )

    def test_caches_journal_id(
        self, hierarchy: JournalHierarchy, mock_client: MagicMock
    ) -> None:
        """Test that journal ID is cached."""
        hierarchy.get_journal_collection()
        hierarchy.get_journal_collection()

        # Should only call once due to caching
        mock_client.get_or_create_collection.assert_called_once()


class TestGetYearContainer:
    """Tests for get_year_container method."""

    def test_creates_year_container(
        self, hierarchy: JournalHierarchy, mock_client: MagicMock
    ) -> None:
        """Test year container creation."""
        result = hierarchy.get_year_container(2026)

        assert result == "container_id_456"
        mock_client.get_or_create_container.assert_called_with(
            "space_123", "journal_id_123", "2026"
        )

    def test_caches_year_id(
        self, hierarchy: JournalHierarchy, mock_client: MagicMock
    ) -> None:
        """Test that year ID is cached."""
        hierarchy.get_year_container(2026)
        hierarchy.get_year_container(2026)

        # Collection call + 1 year call (cached on second)
        assert mock_client.get_or_create_container.call_count == 1

    def test_different_years_not_cached_together(
        self, hierarchy: JournalHierarchy, mock_client: MagicMock
    ) -> None:
        """Test that different years are cached separately."""
        mock_client.get_or_create_container.side_effect = [
            "year_2025",
            "year_2026",
        ]

        result_2025 = hierarchy.get_year_container(2025)
        result_2026 = hierarchy.get_year_container(2026)

        assert result_2025 == "year_2025"
        assert result_2026 == "year_2026"


class TestGetMonthContainer:
    """Tests for get_month_container method."""

    def test_creates_month_container(
        self, hierarchy: JournalHierarchy, mock_client: MagicMock
    ) -> None:
        """Test month container creation."""
        mock_client.get_or_create_container.side_effect = [
            "year_2026",  # Year container
            "month_jan",  # Month container
        ]

        result = hierarchy.get_month_container(2026, 1)

        assert result == "month_jan"
        # Check the month call
        calls = mock_client.get_or_create_container.call_args_list
        assert calls[-1][0] == ("space_123", "year_2026", "January")

    def test_caches_month_id(
        self, hierarchy: JournalHierarchy, mock_client: MagicMock
    ) -> None:
        """Test that month ID is cached."""
        hierarchy.get_month_container(2026, 1)
        hierarchy.get_month_container(2026, 1)

        # Year + Month calls only once each
        assert mock_client.get_or_create_container.call_count == 2

    def test_invalid_month_raises_error(self, hierarchy: JournalHierarchy) -> None:
        """Test that invalid month raises ValueError."""
        with pytest.raises(ValueError, match="Month must be 1-12"):
            hierarchy.get_month_container(2026, 0)

        with pytest.raises(ValueError, match="Month must be 1-12"):
            hierarchy.get_month_container(2026, 13)

    def test_all_months_have_correct_names(
        self, hierarchy: JournalHierarchy, mock_client: MagicMock
    ) -> None:
        """Test that all 12 months use correct names."""
        expected_months = [
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

        mock_client.get_or_create_container.side_effect = (
            ["year_2026"] + [f"month_{i}" for i in range(12)]
        )

        for month_num, expected_name in enumerate(expected_months, 1):
            hierarchy._month_cache.clear()  # Clear cache for each test
            hierarchy.get_month_container(2026, month_num)

            # Check the last call was for the correct month name
            call_args = mock_client.get_or_create_container.call_args[0]
            assert call_args[2] == expected_name


class TestGetPath:
    """Tests for get_path method."""

    def test_returns_correct_path(self, hierarchy: JournalHierarchy) -> None:
        """Test path generation."""
        path = hierarchy.get_path(date(2026, 1, 24))
        assert path == "Journal/2026/January"

    def test_different_dates(self, hierarchy: JournalHierarchy) -> None:
        """Test path for different dates."""
        assert hierarchy.get_path(date(2025, 12, 31)) == "Journal/2025/December"
        assert hierarchy.get_path(date(2026, 6, 15)) == "Journal/2026/June"


class TestCreateEntry:
    """Tests for create_entry method."""

    def test_creates_entry_with_full_title(
        self, hierarchy: JournalHierarchy, mock_client: MagicMock
    ) -> None:
        """Test entry creation with day prefix in title."""
        mock_client.get_or_create_container.side_effect = [
            "year_2026",
            "month_jan",
        ]

        entry_id, journal_id, year_id, month_id = hierarchy.create_entry(
            date(2026, 1, 24),
            "Morning Reflection",
            "Today I reflected on...",
        )

        assert entry_id == "entry_id_789"
        assert journal_id == "journal_id_123"
        assert year_id == "year_2026"
        assert month_id == "month_jan"

        # Verify create_page was called with correct arguments
        mock_client.create_page.assert_called_once_with(
            "space_123",
            name="24 - Morning Reflection",
            content="Today I reflected on...",
            parent_id="month_jan",
        )

    def test_creates_hierarchy_if_needed(
        self, hierarchy: JournalHierarchy, mock_client: MagicMock
    ) -> None:
        """Test that hierarchy is created when entry is created."""
        mock_client.get_or_create_container.side_effect = [
            "year_2026",
            "month_jan",
        ]

        hierarchy.create_entry(date(2026, 1, 24), "Test", "Content")

        # Verify hierarchy was set up
        mock_client.get_or_create_collection.assert_called_once()
        assert mock_client.get_or_create_container.call_count == 2


class TestClearCache:
    """Tests for clear_cache method."""

    def test_clears_all_caches(
        self, hierarchy: JournalHierarchy, mock_client: MagicMock
    ) -> None:
        """Test that all caches are cleared."""
        # Populate caches
        mock_client.get_or_create_container.side_effect = [
            "year_2026",
            "month_jan",
        ]
        hierarchy.get_journal_collection()
        hierarchy.get_year_container(2026)
        hierarchy.get_month_container(2026, 1)

        # Clear
        hierarchy.clear_cache()

        # Verify caches are empty
        assert hierarchy._journal_id is None
        assert hierarchy._year_cache == {}
        assert hierarchy._month_cache == {}

    def test_allows_refetch_after_clear(
        self, hierarchy: JournalHierarchy, mock_client: MagicMock
    ) -> None:
        """Test that clearing cache allows refetching."""
        # First fetch
        hierarchy.get_journal_collection()

        # Clear and refetch
        hierarchy.clear_cache()
        hierarchy.get_journal_collection()

        # Should have called twice
        assert mock_client.get_or_create_collection.call_count == 2
