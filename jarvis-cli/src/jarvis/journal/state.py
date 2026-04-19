"""State management for journal entries and deep dives."""

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from jarvis.journal.models import DeepDive, JournalEntryReference

# Default journal data directory
JOURNAL_DIR = Path.home() / ".jarvis" / "journal"
ENTRIES_FILE = JOURNAL_DIR / "entries.json"
DEEP_DIVES_DIR = JOURNAL_DIR / "deep_dives"
DRAFTS_DIR = JOURNAL_DIR / "drafts"


def ensure_journal_dirs() -> None:
    """Create journal directories if they don't exist."""
    JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    DEEP_DIVES_DIR.mkdir(exist_ok=True)
    DRAFTS_DIR.mkdir(exist_ok=True)


def load_entries() -> list[JournalEntryReference]:
    """Load all entry references from disk.

    Returns:
        List of journal entry references, newest first.
    """
    if not ENTRIES_FILE.exists():
        return []

    try:
        data = json.loads(ENTRIES_FILE.read_text(encoding="utf-8"))
        return [JournalEntryReference(**e) for e in data.get("entries", [])]
    except (json.JSONDecodeError, KeyError, ValueError):
        return []


def save_entry_reference(ref: JournalEntryReference) -> None:
    """Add or update an entry reference in the index.

    Args:
        ref: Journal entry reference to save
    """
    ensure_journal_dirs()

    entries = load_entries()

    # Check if already exists (update) or new (append)
    existing_idx = next((i for i, e in enumerate(entries) if e.id == ref.id), None)

    if existing_idx is not None:
        entries[existing_idx] = ref
    else:
        entries.insert(0, ref)  # Newest first

    _write_entries(entries)


def delete_entry_reference(entry_id: str) -> bool:
    """Remove an entry reference from the index.

    Args:
        entry_id: ID of the entry to remove

    Returns:
        True if entry was found and removed, False otherwise
    """
    entries = load_entries()
    original_len = len(entries)
    entries = [e for e in entries if e.id != entry_id]

    if len(entries) < original_len:
        _write_entries(entries)
        return True
    return False


def get_entry_reference(entry_id: str) -> JournalEntryReference | None:
    """Get a specific entry reference by ID.

    Args:
        entry_id: ID of the entry to find

    Returns:
        Entry reference or None if not found
    """
    entries = load_entries()
    return next((e for e in entries if e.id == entry_id), None)


def _write_entries(entries: list[JournalEntryReference]) -> None:
    """Write entries index to disk.

    Args:
        entries: List of entry references to save
    """
    ensure_journal_dirs()
    data: dict[str, Any] = {
        "version": "1.0",
        "updated_at": datetime.now().isoformat(),
        "entries": [e.model_dump(mode="json") for e in entries],
    }
    ENTRIES_FILE.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def load_deep_dives(entry_id: str) -> list[DeepDive]:
    """Load deep dives for an entry.

    Args:
        entry_id: ID of the journal entry

    Returns:
        List of deep dives for this entry
    """
    dd_file = DEEP_DIVES_DIR / f"{entry_id}.json"
    if not dd_file.exists():
        return []

    try:
        data = json.loads(dd_file.read_text(encoding="utf-8"))
        return [DeepDive(**dd) for dd in data.get("deep_dives", [])]
    except (json.JSONDecodeError, KeyError, ValueError):
        return []


def save_deep_dive(entry_id: str, deep_dive: DeepDive) -> None:
    """Save a deep dive for an entry.

    Args:
        entry_id: ID of the journal entry
        deep_dive: Deep dive to save
    """
    ensure_journal_dirs()

    existing = load_deep_dives(entry_id)
    existing.append(deep_dive)

    data = {
        "entry_id": entry_id,
        "deep_dives": [dd.model_dump(mode="json") for dd in existing],
    }

    dd_file = DEEP_DIVES_DIR / f"{entry_id}.json"
    dd_file.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    # Update the entry reference to indicate it has a deep dive
    ref = get_entry_reference(entry_id)
    if ref and not ref.has_deep_dive:
        ref.has_deep_dive = True
        save_entry_reference(ref)


def save_draft(content: str) -> Path:
    """Save draft content for recovery in case of save failure.

    Args:
        content: Journal entry content to save

    Returns:
        Path to the saved draft file
    """
    ensure_journal_dirs()

    # Include microseconds to ensure unique filenames for rapid saves
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    draft_file = DRAFTS_DIR / f"{timestamp}.txt"
    draft_file.write_text(content, encoding="utf-8")
    return draft_file


def load_draft(draft_path: Path) -> str | None:
    """Load draft content from a file.

    Args:
        draft_path: Path to the draft file

    Returns:
        Draft content or None if file doesn't exist
    """
    if not draft_path.exists():
        return None
    return draft_path.read_text(encoding="utf-8")


def list_drafts() -> list[Path]:
    """List all draft files.

    Returns:
        List of draft file paths, newest first
    """
    if not DRAFTS_DIR.exists():
        return []

    drafts = list(DRAFTS_DIR.glob("*.txt"))
    return sorted(drafts, key=lambda p: p.stat().st_mtime, reverse=True)


def delete_draft(draft_path: Path) -> bool:
    """Delete a draft file.

    Args:
        draft_path: Path to the draft to delete

    Returns:
        True if deleted, False if file didn't exist
    """
    if draft_path.exists():
        draft_path.unlink()
        return True
    return False


def cleanup_old_drafts(max_age_days: int = 7) -> int:
    """Remove drafts older than max_age_days.

    Args:
        max_age_days: Maximum age of drafts to keep

    Returns:
        Number of drafts deleted
    """
    if not DRAFTS_DIR.exists():
        return 0

    cutoff = datetime.now() - timedelta(days=max_age_days)
    deleted = 0

    for draft in DRAFTS_DIR.glob("*.txt"):
        if datetime.fromtimestamp(draft.stat().st_mtime) < cutoff:
            draft.unlink()
            deleted += 1

    return deleted


def get_entries_by_date_range(
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int | None = None,
) -> list[JournalEntryReference]:
    """Get entries filtered by date range.

    Args:
        start_date: Start of date range (inclusive), filters by entry_date
        end_date: End of date range (inclusive), filters by entry_date
        limit: Maximum number of entries to return

    Returns:
        Filtered list of entry references
    """
    entries = load_entries()

    if start_date:
        entries = [e for e in entries if e.entry_date >= start_date]

    if end_date:
        entries = [e for e in entries if e.entry_date <= end_date]

    if limit:
        entries = entries[:limit]

    return entries


def search_entries(query: str, limit: int = 20) -> list[JournalEntryReference]:
    """Search entries by title or content preview.

    Args:
        query: Search query (case-insensitive)
        limit: Maximum number of results

    Returns:
        Matching entry references
    """
    entries = load_entries()
    query_lower = query.lower()

    matching = [
        e
        for e in entries
        if query_lower in e.title.lower() or query_lower in e.content_preview.lower()
    ]

    return matching[:limit]
