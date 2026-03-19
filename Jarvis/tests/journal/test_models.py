"""Tests for journal domain models."""

from datetime import date, datetime

import pytest

from jarvis.journal.models import (
    DeepDive,
    ExtractedMetadata,
    InsightsResult,
    JournalEntry,
    JournalEntryReference,
)


class TestJournalEntry:
    """Tests for JournalEntry model."""

    def test_create_journal_entry(self) -> None:
        """Test creating a basic journal entry."""
        entry = JournalEntry(
            id="entry_123",
            space_id="space_456",
            title="Breakthrough on API Design",
            content="Had a breakthrough on the API design today...",
            entry_date=date(2026, 1, 24),
            path="Journal/2026/January",
            tags=["work", "technical"],
            created_at=datetime(2026, 1, 24, 14, 32, 0),
            journal_id="journal_001",
            year_id="year_2026",
            month_id="month_jan",
        )

        assert entry.id == "entry_123"
        assert entry.space_id == "space_456"
        assert entry.title == "Breakthrough on API Design"
        assert entry.content == "Had a breakthrough on the API design today..."
        assert entry.entry_date == date(2026, 1, 24)
        assert entry.path == "Journal/2026/January"
        assert entry.tags == ["work", "technical"]
        assert entry.journal_id == "journal_001"

    def test_day_prefix_computed_field(self) -> None:
        """Test that day_prefix is correctly computed."""
        entry = JournalEntry(
            id="entry_1",
            space_id="space_1",
            title="Test Entry",
            content="Content",
            entry_date=date(2026, 1, 24),
            path="Journal/2026/January",
            created_at=datetime.now(),
            journal_id="j1",
            year_id="y1",
            month_id="m1",
        )

        assert entry.day_prefix == "24"

    def test_day_prefix_single_digit(self) -> None:
        """Test day_prefix for single digit days."""
        entry = JournalEntry(
            id="entry_1",
            space_id="space_1",
            title="Test Entry",
            content="Content",
            entry_date=date(2026, 1, 5),
            path="Journal/2026/January",
            created_at=datetime.now(),
            journal_id="j1",
            year_id="y1",
            month_id="m1",
        )

        assert entry.day_prefix == "5"

    def test_full_title_computed_field(self) -> None:
        """Test that full_title combines day prefix and title."""
        entry = JournalEntry(
            id="entry_1",
            space_id="space_1",
            title="Morning Reflection",
            content="Content",
            entry_date=date(2026, 1, 24),
            path="Journal/2026/January",
            created_at=datetime.now(),
            journal_id="j1",
            year_id="y1",
            month_id="m1",
        )

        assert entry.full_title == "24 - Morning Reflection"

    def test_entry_with_empty_tags(self) -> None:
        """Test entry with no tags uses empty list default."""
        entry = JournalEntry(
            id="entry_1",
            space_id="space_1",
            title="Test",
            content="Content",
            entry_date=date(2026, 1, 24),
            path="Journal/2026/January",
            created_at=datetime.now(),
            journal_id="j1",
            year_id="y1",
            month_id="m1",
        )

        assert entry.tags == []

    def test_entry_serialization(self) -> None:
        """Test entry can be serialized to dict."""
        entry = JournalEntry(
            id="entry_1",
            space_id="space_1",
            title="Test",
            content="Content",
            entry_date=date(2026, 1, 24),
            path="Journal/2026/January",
            created_at=datetime(2026, 1, 24, 10, 0, 0),
            journal_id="j1",
            year_id="y1",
            month_id="m1",
        )

        data = entry.model_dump()
        assert data["id"] == "entry_1"
        assert data["entry_date"] == date(2026, 1, 24)
        assert data["day_prefix"] == "24"
        assert data["full_title"] == "24 - Test"


class TestJournalEntryReference:
    """Tests for JournalEntryReference model."""

    def test_create_entry_reference(self) -> None:
        """Test creating an entry reference."""
        ref = JournalEntryReference(
            id="entry_123",
            space_id="space_456",
            path="Journal/2026/January",
            title="24 - Breakthrough",
            entry_date=date(2026, 1, 24),
            created_at=datetime(2026, 1, 24, 14, 32, 0),
            tags=["work"],
            has_deep_dive=True,
            content_preview="Had a breakthrough...",
        )

        assert ref.id == "entry_123"
        assert ref.path == "Journal/2026/January"
        assert ref.title == "24 - Breakthrough"
        assert ref.has_deep_dive is True
        assert ref.content_preview == "Had a breakthrough..."

    def test_reference_defaults(self) -> None:
        """Test entry reference default values."""
        ref = JournalEntryReference(
            id="entry_1",
            space_id="space_1",
            path="Journal/2026/January",
            title="24 - Test",
            entry_date=date(2026, 1, 24),
            created_at=datetime.now(),
        )

        assert ref.tags == []
        assert ref.has_deep_dive is False
        assert ref.content_preview == ""

    def test_reference_json_serialization(self) -> None:
        """Test reference can be serialized to JSON-compatible format."""
        ref = JournalEntryReference(
            id="entry_1",
            space_id="space_1",
            path="Journal/2026/January",
            title="24 - Test",
            entry_date=date(2026, 1, 24),
            created_at=datetime(2026, 1, 24, 10, 0, 0),
        )

        data = ref.model_dump(mode="json")
        assert data["id"] == "entry_1"
        assert data["entry_date"] == "2026-01-24"
        assert isinstance(data["created_at"], str)


class TestDeepDive:
    """Tests for DeepDive model."""

    def test_create_deep_dive(self) -> None:
        """Test creating a deep dive."""
        dd = DeepDive(
            id="dd_001",
            entry_id="entry_123",
            user_request="explore the underlying feelings",
            ai_response="You mentioned feeling 'stretched thin'...",
            format_type="emotional_exploration",
            created_at=datetime(2026, 1, 24, 14, 35, 0),
        )

        assert dd.id == "dd_001"
        assert dd.entry_id == "entry_123"
        assert dd.user_request == "explore the underlying feelings"
        assert dd.format_type == "emotional_exploration"

    def test_deep_dive_serialization(self) -> None:
        """Test deep dive serialization."""
        dd = DeepDive(
            id="dd_001",
            entry_id="entry_123",
            user_request="action items",
            ai_response="Here are some action items...",
            format_type="action_items",
            created_at=datetime(2026, 1, 24, 14, 35, 0),
        )

        data = dd.model_dump(mode="json")
        assert data["id"] == "dd_001"
        assert data["format_type"] == "action_items"
        assert isinstance(data["created_at"], str)


class TestInsightsResult:
    """Tests for InsightsResult model."""

    def test_create_insights_result(self) -> None:
        """Test creating an insights result."""
        insights = InsightsResult(
            analysis_window="Jan 10 - Jan 24",
            entry_count=12,
            themes=["work-life balance", "API design"],
            patterns=["journal most on weekday mornings", "positive entries use clarity"],
            observations="Your entries this week show more resolution...",
            generated_at=datetime(2026, 1, 24, 15, 0, 0),
        )

        assert insights.analysis_window == "Jan 10 - Jan 24"
        assert insights.entry_count == 12
        assert len(insights.themes) == 2
        assert len(insights.patterns) == 2

    def test_insights_defaults(self) -> None:
        """Test insights with default empty lists."""
        insights = InsightsResult(
            analysis_window="Jan 2026",
            entry_count=5,
            observations="Limited data available.",
            generated_at=datetime.now(),
        )

        assert insights.themes == []
        assert insights.patterns == []


class TestExtractedMetadata:
    """Tests for ExtractedMetadata model."""

    def test_create_metadata(self) -> None:
        """Test creating extracted metadata."""
        metadata = ExtractedMetadata(
            tags=["work", "relationships", "growth"],
            mood="mixed",
            topics=["project deadline", "conversation with partner"],
        )

        assert metadata.tags == ["work", "relationships", "growth"]
        assert metadata.mood == "mixed"
        assert len(metadata.topics) == 2

    def test_metadata_defaults(self) -> None:
        """Test metadata default values."""
        metadata = ExtractedMetadata()

        assert metadata.tags == []
        assert metadata.mood == "neutral"
        assert metadata.topics == []

    def test_mood_types(self) -> None:
        """Test all valid mood types."""
        for mood in ["positive", "negative", "neutral", "mixed"]:
            metadata = ExtractedMetadata(mood=mood)  # type: ignore[arg-type]
            assert metadata.mood == mood

    def test_invalid_mood_raises_error(self) -> None:
        """Test that invalid mood raises validation error."""
        with pytest.raises(ValueError):
            ExtractedMetadata(mood="invalid")  # type: ignore[arg-type]
