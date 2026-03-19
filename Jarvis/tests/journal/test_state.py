"""Tests for journal state management."""

from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from jarvis.journal.models import DeepDive, JournalEntryReference
from jarvis.journal.state import (
    cleanup_old_drafts,
    delete_draft,
    delete_entry_reference,
    ensure_journal_dirs,
    get_entries_by_date_range,
    get_entry_reference,
    list_drafts,
    load_deep_dives,
    load_draft,
    load_entries,
    save_deep_dive,
    save_draft,
    save_entry_reference,
    search_entries,
)


@pytest.fixture
def temp_journal_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set up temporary journal directory."""
    journal_dir = tmp_path / "journal"
    monkeypatch.setattr("jarvis.journal.state.JOURNAL_DIR", journal_dir)
    monkeypatch.setattr("jarvis.journal.state.ENTRIES_FILE", journal_dir / "entries.json")
    monkeypatch.setattr("jarvis.journal.state.DEEP_DIVES_DIR", journal_dir / "deep_dives")
    monkeypatch.setattr("jarvis.journal.state.DRAFTS_DIR", journal_dir / "drafts")
    return journal_dir


@pytest.fixture
def sample_entry_ref() -> JournalEntryReference:
    """Create a sample entry reference."""
    return JournalEntryReference(
        id="entry_001",
        space_id="space_123",
        path="Journal/2026/January",
        title="24 - Test Entry",
        entry_date=date(2026, 1, 24),
        created_at=datetime(2026, 1, 24, 14, 0, 0),
        tags=["test"],
        has_deep_dive=False,
        content_preview="This is a test entry...",
    )


class TestEnsureJournalDirs:
    """Tests for ensure_journal_dirs."""

    def test_creates_directories(self, temp_journal_dir: Path) -> None:
        """Test that all required directories are created."""
        ensure_journal_dirs()

        assert temp_journal_dir.exists()
        assert (temp_journal_dir / "deep_dives").exists()
        assert (temp_journal_dir / "drafts").exists()

    def test_idempotent(self, temp_journal_dir: Path) -> None:
        """Test that calling multiple times is safe."""
        ensure_journal_dirs()
        ensure_journal_dirs()

        assert temp_journal_dir.exists()


class TestLoadEntriesErrorHandling:
    """Tests for error handling in load_entries."""

    def test_load_entries_with_corrupted_json(
        self, temp_journal_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that corrupted JSON returns empty list."""
        ensure_journal_dirs()
        entries_file = temp_journal_dir / "entries.json"
        entries_file.write_text("not valid json {{{", encoding="utf-8")
        monkeypatch.setattr("jarvis.journal.state.ENTRIES_FILE", entries_file)

        entries = load_entries()
        assert entries == []


class TestLoadDeepDivesErrorHandling:
    """Tests for error handling in load_deep_dives."""

    def test_load_deep_dives_with_corrupted_json(
        self, temp_journal_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that corrupted deep dives JSON returns empty list."""
        ensure_journal_dirs()
        dd_dir = temp_journal_dir / "deep_dives"
        dd_file = dd_dir / "entry_001.json"
        dd_file.write_text("corrupted json {{", encoding="utf-8")
        monkeypatch.setattr("jarvis.journal.state.DEEP_DIVES_DIR", dd_dir)

        dives = load_deep_dives("entry_001")
        assert dives == []


class TestListDraftsEdgeCases:
    """Tests for edge cases in list_drafts."""

    def test_list_drafts_no_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that list_drafts returns empty when directory doesn't exist."""
        nonexistent = tmp_path / "nonexistent_drafts"
        monkeypatch.setattr("jarvis.journal.state.DRAFTS_DIR", nonexistent)

        drafts = list_drafts()
        assert drafts == []


class TestCleanupOldDraftsEdgeCases:
    """Tests for edge cases in cleanup_old_drafts."""

    def test_cleanup_old_drafts_no_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that cleanup returns 0 when directory doesn't exist."""
        nonexistent = tmp_path / "nonexistent_drafts"
        monkeypatch.setattr("jarvis.journal.state.DRAFTS_DIR", nonexistent)

        deleted = cleanup_old_drafts()
        assert deleted == 0


class TestEntryReferences:
    """Tests for entry reference operations."""

    def test_load_entries_empty(self, temp_journal_dir: Path) -> None:
        """Test loading entries when no file exists."""
        entries = load_entries()
        assert entries == []

    def test_save_and_load_entry(
        self, temp_journal_dir: Path, sample_entry_ref: JournalEntryReference
    ) -> None:
        """Test saving and loading an entry reference."""
        save_entry_reference(sample_entry_ref)

        entries = load_entries()
        assert len(entries) == 1
        assert entries[0].id == "entry_001"
        assert entries[0].title == "24 - Test Entry"

    def test_save_multiple_entries_newest_first(self, temp_journal_dir: Path) -> None:
        """Test that newer entries appear first."""
        ref1 = JournalEntryReference(
            id="entry_001",
            space_id="space_1",
            path="Journal/2026/January",
            title="24 - First",
            entry_date=date(2026, 1, 24),
            created_at=datetime(2026, 1, 24, 10, 0, 0),
        )
        ref2 = JournalEntryReference(
            id="entry_002",
            space_id="space_1",
            path="Journal/2026/January",
            title="24 - Second",
            entry_date=date(2026, 1, 24),
            created_at=datetime(2026, 1, 24, 14, 0, 0),
        )

        save_entry_reference(ref1)
        save_entry_reference(ref2)

        entries = load_entries()
        assert len(entries) == 2
        assert entries[0].id == "entry_002"  # Newest first
        assert entries[1].id == "entry_001"

    def test_update_existing_entry(
        self, temp_journal_dir: Path, sample_entry_ref: JournalEntryReference
    ) -> None:
        """Test updating an existing entry reference."""
        save_entry_reference(sample_entry_ref)

        # Update the entry
        updated_ref = JournalEntryReference(
            id="entry_001",
            space_id="space_123",
            path="Journal/2026/January",
            title="24 - Updated Title",
            entry_date=date(2026, 1, 24),
            created_at=datetime(2026, 1, 24, 14, 0, 0),
            has_deep_dive=True,
        )
        save_entry_reference(updated_ref)

        entries = load_entries()
        assert len(entries) == 1
        assert entries[0].title == "24 - Updated Title"
        assert entries[0].has_deep_dive is True

    def test_delete_entry_reference(
        self, temp_journal_dir: Path, sample_entry_ref: JournalEntryReference
    ) -> None:
        """Test deleting an entry reference."""
        save_entry_reference(sample_entry_ref)

        result = delete_entry_reference("entry_001")
        assert result is True

        entries = load_entries()
        assert len(entries) == 0

    def test_delete_nonexistent_entry(self, temp_journal_dir: Path) -> None:
        """Test deleting a non-existent entry returns False."""
        result = delete_entry_reference("nonexistent")
        assert result is False

    def test_get_entry_reference(
        self, temp_journal_dir: Path, sample_entry_ref: JournalEntryReference
    ) -> None:
        """Test getting a specific entry reference."""
        save_entry_reference(sample_entry_ref)

        entry = get_entry_reference("entry_001")
        assert entry is not None
        assert entry.id == "entry_001"

    def test_get_nonexistent_entry(self, temp_journal_dir: Path) -> None:
        """Test getting a non-existent entry returns None."""
        entry = get_entry_reference("nonexistent")
        assert entry is None


class TestDeepDives:
    """Tests for deep dive operations."""

    def test_load_deep_dives_empty(self, temp_journal_dir: Path) -> None:
        """Test loading deep dives when none exist."""
        dives = load_deep_dives("entry_001")
        assert dives == []

    def test_save_and_load_deep_dive(self, temp_journal_dir: Path) -> None:
        """Test saving and loading a deep dive."""
        dd = DeepDive(
            id="dd_001",
            entry_id="entry_001",
            user_request="explore feelings",
            ai_response="You mentioned feeling stressed...",
            format_type="emotional",
            created_at=datetime(2026, 1, 24, 15, 0, 0),
        )

        save_deep_dive("entry_001", dd)

        dives = load_deep_dives("entry_001")
        assert len(dives) == 1
        assert dives[0].id == "dd_001"
        assert dives[0].user_request == "explore feelings"

    def test_save_multiple_deep_dives(self, temp_journal_dir: Path) -> None:
        """Test saving multiple deep dives for one entry."""
        dd1 = DeepDive(
            id="dd_001",
            entry_id="entry_001",
            user_request="explore feelings",
            ai_response="Response 1...",
            format_type="emotional",
            created_at=datetime(2026, 1, 24, 15, 0, 0),
        )
        dd2 = DeepDive(
            id="dd_002",
            entry_id="entry_001",
            user_request="action items",
            ai_response="Response 2...",
            format_type="action_items",
            created_at=datetime(2026, 1, 24, 16, 0, 0),
        )

        save_deep_dive("entry_001", dd1)
        save_deep_dive("entry_001", dd2)

        dives = load_deep_dives("entry_001")
        assert len(dives) == 2

    def test_save_deep_dive_updates_entry_reference(
        self, temp_journal_dir: Path, sample_entry_ref: JournalEntryReference
    ) -> None:
        """Test that saving a deep dive updates the entry reference."""
        save_entry_reference(sample_entry_ref)

        dd = DeepDive(
            id="dd_001",
            entry_id="entry_001",
            user_request="test",
            ai_response="response",
            format_type="test",
            created_at=datetime.now(),
        )
        save_deep_dive("entry_001", dd)

        entry = get_entry_reference("entry_001")
        assert entry is not None
        assert entry.has_deep_dive is True


class TestDrafts:
    """Tests for draft operations."""

    def test_save_draft(self, temp_journal_dir: Path) -> None:
        """Test saving a draft."""
        content = "This is draft content."
        path = save_draft(content)

        assert path.exists()
        assert path.read_text() == content

    def test_load_draft(self, temp_journal_dir: Path) -> None:
        """Test loading a draft."""
        content = "Draft to load."
        path = save_draft(content)

        loaded = load_draft(path)
        assert loaded == content

    def test_load_nonexistent_draft(self, temp_journal_dir: Path) -> None:
        """Test loading a non-existent draft returns None."""
        result = load_draft(temp_journal_dir / "nonexistent.txt")
        assert result is None

    def test_list_drafts(self, temp_journal_dir: Path) -> None:
        """Test listing drafts."""
        save_draft("Draft 1")
        save_draft("Draft 2")

        drafts = list_drafts()
        assert len(drafts) == 2

    def test_list_drafts_newest_first(self, temp_journal_dir: Path) -> None:
        """Test that newer drafts appear first."""
        _ = temp_journal_dir  # Fixture used for side effects
        save_draft("Draft 1")
        path2 = save_draft("Draft 2")

        drafts = list_drafts()
        assert drafts[0] == path2  # Newest first

    def test_delete_draft(self, temp_journal_dir: Path) -> None:
        """Test deleting a draft."""
        path = save_draft("To delete")
        assert path.exists()

        result = delete_draft(path)
        assert result is True
        assert not path.exists()

    def test_delete_nonexistent_draft(self, temp_journal_dir: Path) -> None:
        """Test deleting a non-existent draft returns False."""
        result = delete_draft(temp_journal_dir / "nonexistent.txt")
        assert result is False

    def test_cleanup_old_drafts(self, temp_journal_dir: Path) -> None:
        """Test cleaning up old drafts."""
        ensure_journal_dirs()

        # Create a draft and make it old
        drafts_dir = temp_journal_dir / "drafts"
        old_draft = drafts_dir / "old_draft.txt"
        old_draft.write_text("Old content")

        # Set modification time to 10 days ago
        import os

        old_time = (datetime.now() - timedelta(days=10)).timestamp()
        os.utime(old_draft, (old_time, old_time))

        # Create a new draft
        save_draft("New content")

        # Cleanup with 7 day threshold
        deleted = cleanup_old_drafts(max_age_days=7)

        assert deleted == 1
        assert not old_draft.exists()
        assert len(list_drafts()) == 1


class TestQueryOperations:
    """Tests for query operations."""

    def test_get_entries_by_date_range(self, temp_journal_dir: Path) -> None:
        """Test filtering entries by date range."""
        ref1 = JournalEntryReference(
            id="entry_001",
            space_id="space_1",
            path="Journal/2026/January",
            title="1 - Early",
            entry_date=date(2026, 1, 1),
            created_at=datetime(2026, 1, 1, 10, 0, 0),
        )
        ref2 = JournalEntryReference(
            id="entry_002",
            space_id="space_1",
            path="Journal/2026/January",
            title="15 - Middle",
            entry_date=date(2026, 1, 15),
            created_at=datetime(2026, 1, 15, 10, 0, 0),
        )
        ref3 = JournalEntryReference(
            id="entry_003",
            space_id="space_1",
            path="Journal/2026/January",
            title="30 - Late",
            entry_date=date(2026, 1, 30),
            created_at=datetime(2026, 1, 30, 10, 0, 0),
        )

        save_entry_reference(ref1)
        save_entry_reference(ref2)
        save_entry_reference(ref3)

        # Filter by date range (using entry_date, not created_at)
        start = date(2026, 1, 10)
        end = date(2026, 1, 20)
        filtered = get_entries_by_date_range(start_date=start, end_date=end)

        assert len(filtered) == 1
        assert filtered[0].id == "entry_002"

    def test_get_entries_with_limit(self, temp_journal_dir: Path) -> None:
        """Test limiting number of entries returned."""
        for i in range(5):
            ref = JournalEntryReference(
                id=f"entry_{i:03d}",
                space_id="space_1",
                path="Journal/2026/January",
                title=f"{i+1} - Entry {i}",
                entry_date=date(2026, 1, i + 1),
                created_at=datetime(2026, 1, i + 1, 10, 0, 0),
            )
            save_entry_reference(ref)

        entries = get_entries_by_date_range(limit=3)
        assert len(entries) == 3

    def test_search_entries_by_title(self, temp_journal_dir: Path) -> None:
        """Test searching entries by title."""
        ref1 = JournalEntryReference(
            id="entry_001",
            space_id="space_1",
            path="Journal/2026/January",
            title="24 - Morning Reflection",
            entry_date=date(2026, 1, 24),
            created_at=datetime.now(),
            content_preview="Started the day with coffee...",
        )
        ref2 = JournalEntryReference(
            id="entry_002",
            space_id="space_1",
            path="Journal/2026/January",
            title="24 - API Design Breakthrough",
            entry_date=date(2026, 1, 24),
            created_at=datetime.now(),
            content_preview="Finally figured out the API...",
        )

        save_entry_reference(ref1)
        save_entry_reference(ref2)

        results = search_entries("reflection")
        assert len(results) == 1
        assert results[0].id == "entry_001"

    def test_search_entries_by_content_preview(self, temp_journal_dir: Path) -> None:
        """Test searching entries by content preview."""
        ref = JournalEntryReference(
            id="entry_001",
            space_id="space_1",
            path="Journal/2026/January",
            title="24 - Test",
            entry_date=date(2026, 1, 24),
            created_at=datetime.now(),
            content_preview="Thinking about coffee and code...",
        )
        save_entry_reference(ref)

        results = search_entries("coffee")
        assert len(results) == 1

    def test_search_entries_case_insensitive(self, temp_journal_dir: Path) -> None:
        """Test that search is case-insensitive."""
        ref = JournalEntryReference(
            id="entry_001",
            space_id="space_1",
            path="Journal/2026/January",
            title="24 - Morning Reflection",
            entry_date=date(2026, 1, 24),
            created_at=datetime.now(),
        )
        save_entry_reference(ref)

        results = search_entries("MORNING")
        assert len(results) == 1

    def test_search_entries_respects_limit(self, temp_journal_dir: Path) -> None:
        """Test that search respects the limit parameter."""
        for i in range(10):
            ref = JournalEntryReference(
                id=f"entry_{i:03d}",
                space_id="space_1",
                path="Journal/2026/January",
                title=f"{i+1} - Test Entry",
                entry_date=date(2026, 1, i + 1),
                created_at=datetime.now(),
            )
            save_entry_reference(ref)

        results = search_entries("Test", limit=5)
        assert len(results) == 5
