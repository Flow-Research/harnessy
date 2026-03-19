# Technical Specification: Jarvis Journaling

**AI-Powered Freeform Journaling for AnyType**

---

## 1. Overview

### Purpose

This document provides a complete technical blueprint for implementing the Journaling capability within Jarvis. It extends the existing Jarvis architecture with journal entry capture, AnyType hierarchical storage, AI-powered insights, and persistent context tracking.

### Scope

- Journal entry capture (inline, editor, interactive modes)
- AnyType hierarchical storage (Journal → Year → Month → Entry)
- AI title generation and deep dive analysis
- Entry retrieval (list, read, search)
- Cross-entry insights
- Context persistence for journal data

### Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Entry Storage | AnyType Page objects | Native type, supports rich content |
| Hierarchy | Collection → Year → Month containers | Mirrors calendar mental model |
| AI Model | Claude Sonnet 4 | Matches existing task scheduler, good balance of speed/quality |
| Local Context | JSON files in `~/.jarvis/journal/` | Consistent with existing state management |
| CLI Integration | Click command group under `jarvis journal` | Follows `jarvis <domain> <action>` pattern |

### References

- [Product Specification](./product_spec.md)
- [Task Scheduler Technical Spec](../01_task-scheduler/technical_spec.md)
- [AnyType API Documentation](https://developers.anytype.io/)

---

## 2. System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           User's Machine                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐     ┌──────────────────────────────────────────────┐ │
│  │   AnyType    │     │                   Jarvis                      │ │
│  │   Desktop    │◄───►│  ┌──────────┐  ┌──────────┐  ┌────────────┐  │ │
│  │              │     │  │ Journal  │  │ AnyType  │  │     AI     │  │ │
│  │  localhost:  │     │  │   CLI    │──│  Client  │──│   Client   │  │ │
│  │    31009     │     │  └──────────┘  └──────────┘  └────────────┘  │ │
│  └──────────────┘     │       │              │              │         │ │
│         │             │       ▼              ▼              ▼         │ │
│         │             │  ┌──────────┐  ┌──────────┐  ┌────────────┐  │ │
│         ▼             │  │ Journal  │  │ Hierarchy│  │   Prompt   │  │ │
│  ┌──────────────┐     │  │  State   │  │  Manager │  │  Templates │  │ │
│  │   Journal    │     │  └──────────┘  └──────────┘  └────────────┘  │ │
│  │  Collection  │     │       │                                       │ │
│  │  └─ 2026     │     │       ▼                                       │ │
│  │     └─ Jan   │     │  ┌──────────────────────────────────────┐    │ │
│  │       └─Entry│     │  │          ~/.jarvis/journal/          │    │ │
│  └──────────────┘     │  │  ├── entries.json                    │    │ │
│                       │  │  ├── deep_dives/                     │    │ │
│                       │  │  └── drafts/                         │    │ │
│                       │  └──────────────────────────────────────┘    │ │
│                       └──────────────────────────────────────────────┘ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Component Overview

| Component | Responsibility |
|-----------|---------------|
| **Journal CLI** | Command parsing, entry capture modes, user interaction |
| **Journal State** | Entry references, deep dive storage, draft recovery |
| **Hierarchy Manager** | Journal/Year/Month container management in AnyType |
| **AI Prompts** | Title generation, deep dive, insights prompt templates |
| **Entry Capture** | Inline, editor, interactive input handling |

### Module Structure (Additions to Existing)

```
src/jarvis/
├── __init__.py
├── __main__.py
├── cli.py                    # Existing: add journal command group
├── models.py                 # Existing: add JournalEntry, DeepDive models
├── anytype_client.py         # Existing: extend with journal methods
├── ai_client.py              # Existing: extend with journal prompts
├── state.py                  # Existing: extend for journal state
├── prompts.py                # Existing: add journal prompt templates
│
├── journal/                  # NEW: Journal-specific module
│   ├── __init__.py
│   ├── commands.py           # CLI commands for journal
│   ├── capture.py            # Entry capture modes (inline, editor, interactive)
│   ├── hierarchy.py          # AnyType hierarchy management
│   ├── state.py              # Journal-specific state (entries.json, deep_dives/)
│   ├── prompts.py            # Journal-specific AI prompts
│   └── insights.py           # Cross-entry analysis logic
│
├── analyzer.py               # Existing
├── context_reader.py         # Existing
└── ...
```

---

## 3. Data Architecture

### Domain Models

#### JournalEntry

```python
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field, computed_field


class JournalEntry(BaseModel):
    """Represents a journal entry stored in AnyType."""

    id: str = Field(description="AnyType object ID")
    space_id: str = Field(description="AnyType space ID")
    title: str = Field(description="AI-generated or manual title")
    content: str = Field(description="Full entry text")
    entry_date: date = Field(description="Date of the entry")
    path: str = Field(description="AnyType path: Journal/Year/Month")
    tags: list[str] = Field(default_factory=list, description="AI-extracted tags")
    created_at: datetime = Field(description="When entry was created")

    # Container references
    journal_id: str = Field(description="Journal collection ID")
    year_id: str = Field(description="Year container ID")
    month_id: str = Field(description="Month container ID")

    @computed_field
    @property
    def day_prefix(self) -> str:
        """Day number prefix for title (e.g., '24')."""
        return str(self.entry_date.day)

    @computed_field
    @property
    def full_title(self) -> str:
        """Complete title with day prefix."""
        return f"{self.day_prefix} - {self.title}"
```

#### JournalEntryReference

```python
class JournalEntryReference(BaseModel):
    """Lightweight reference to a journal entry for local storage."""

    id: str = Field(description="AnyType object ID")
    space_id: str = Field(description="AnyType space ID")
    path: str = Field(description="Journal/Year/Month path")
    title: str = Field(description="Entry title with day prefix")
    date: date = Field(description="Entry date")
    created_at: datetime = Field(description="Creation timestamp")
    tags: list[str] = Field(default_factory=list)
    has_deep_dive: bool = Field(default=False)
    content_preview: str = Field(default="", description="First 100 chars")
```

#### DeepDive

```python
class DeepDive(BaseModel):
    """AI-generated deep dive analysis of a journal entry."""

    id: str = Field(description="Unique deep dive ID")
    entry_id: str = Field(description="Associated journal entry ID")
    user_request: str = Field(description="What the user asked for")
    ai_response: str = Field(description="AI's deep dive content")
    format_type: str = Field(description="e.g., 'emotional', 'action_items', 'socratic'")
    created_at: datetime = Field(description="When generated")
```

#### InsightsResult

```python
class InsightsResult(BaseModel):
    """Result of cross-entry AI analysis."""

    analysis_window: str = Field(description="Time range analyzed")
    entry_count: int = Field(description="Number of entries analyzed")
    themes: list[str] = Field(description="Recurring themes identified")
    patterns: list[str] = Field(description="Behavioral patterns noticed")
    observations: str = Field(description="Free-form AI observations")
    generated_at: datetime
```

### State Storage Schema

**Location:** `~/.jarvis/journal/`

```
~/.jarvis/
├── config.json                 # Existing: add journal_collection_id
├── pending.json                # Existing: task suggestions
└── journal/
    ├── entries.json            # Entry references index
    ├── deep_dives/
    │   ├── {entry_id_1}.json   # Deep dive for entry 1
    │   └── {entry_id_2}.json   # Deep dive for entry 2
    └── drafts/
        └── {timestamp}.txt     # Recovery drafts for failed saves
```

#### entries.json Schema

```json
{
  "version": "1.0",
  "updated_at": "2026-01-24T14:32:00Z",
  "journal_collection_id": "bafyrei_journal...",
  "entries": [
    {
      "id": "bafyrei_entry_1...",
      "space_id": "bafyrei_space...",
      "path": "Journal/2026/January",
      "title": "24 - Breakthrough on API Design",
      "date": "2026-01-24",
      "created_at": "2026-01-24T14:32:00Z",
      "tags": ["work", "technical", "positive"],
      "has_deep_dive": true,
      "content_preview": "Had a breakthrough on the API design today..."
    }
  ]
}
```

#### Deep Dive File Schema ({entry_id}.json)

```json
{
  "entry_id": "bafyrei_entry_1...",
  "deep_dives": [
    {
      "id": "dd_001",
      "user_request": "explore the underlying feelings",
      "ai_response": "You mentioned feeling 'stretched thin'...",
      "format_type": "emotional_exploration",
      "created_at": "2026-01-24T14:35:00Z"
    }
  ]
}
```

---

## 4. API Specification

### AnyType API Extensions

Building on the existing `AnyTypeClient`, add these methods:

#### create_page

```python
def create_page(
    self,
    space_id: str,
    name: str,
    content: str,
    parent_id: str | None = None,
) -> str:
    """Create a Page object in AnyType.

    Args:
        space_id: AnyType space ID
        name: Page title
        content: Page body content
        parent_id: Optional parent container ID

    Returns:
        Created object ID
    """
```

#### get_or_create_collection

```python
def get_or_create_collection(
    self,
    space_id: str,
    name: str,
) -> str:
    """Find or create a collection by name.

    Args:
        space_id: AnyType space ID
        name: Collection name (e.g., "Journal")

    Returns:
        Collection object ID
    """
```

#### get_or_create_container

```python
def get_or_create_container(
    self,
    space_id: str,
    parent_id: str,
    name: str,
) -> str:
    """Find or create a container under a parent.

    Used for Year and Month containers.

    Args:
        space_id: AnyType space ID
        parent_id: Parent container ID
        name: Container name (e.g., "2026" or "January")

    Returns:
        Container object ID
    """
```

#### search_pages

```python
def search_pages(
    self,
    space_id: str,
    query: str,
    parent_id: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Search for Page objects.

    Args:
        space_id: AnyType space ID
        query: Search query
        parent_id: Optional parent to scope search
        limit: Maximum results

    Returns:
        List of matching page objects
    """
```

#### get_children

```python
def get_children(
    self,
    space_id: str,
    parent_id: str,
    limit: int = 100,
) -> list[dict]:
    """Get child objects of a container.

    Args:
        space_id: AnyType space ID
        parent_id: Parent container ID
        limit: Maximum results

    Returns:
        List of child objects
    """
```

### CLI Commands Specification

#### jarvis journal write

```
Usage: jarvis journal write [OPTIONS] [TEXT]

  Write a new journal entry.

Arguments:
  [TEXT]  Entry content (optional, opens editor if omitted)

Options:
  -i, --interactive  Multi-line interactive mode
  -e, --editor       Force editor mode even with text argument
  --no-deep-dive     Skip deep dive prompt
  --title TEXT       Manual title (skip AI generation)
  --space TEXT       AnyType space name or ID
  --help             Show this message and exit.

Examples:
  jarvis journal write "Quick thought about the project"
  jarvis journal write  # Opens $EDITOR
  jarvis journal write -i  # Interactive multi-line
```

#### jarvis journal list

```
Usage: jarvis journal list [OPTIONS]

  List recent journal entries.

Options:
  --limit INTEGER     Number of entries to show (default: 10)
  --month TEXT        Filter by month (e.g., "January" or "2026-01")
  --space TEXT        AnyType space name or ID
  --json              Output as JSON
  --help              Show this message and exit.
```

#### jarvis journal read

```
Usage: jarvis journal read [OPTIONS] IDENTIFIER

  Read a specific journal entry.

Arguments:
  IDENTIFIER  Date (YYYY-MM-DD) or entry ID

Options:
  --with-deep-dive    Include deep dive if exists
  --space TEXT        AnyType space name or ID
  --help              Show this message and exit.
```

#### jarvis journal search

```
Usage: jarvis journal search [OPTIONS] QUERY

  Search journal entries.

Arguments:
  QUERY  Search query

Options:
  --limit INTEGER     Maximum results (default: 20)
  --since TEXT        Time window (e.g., "2 weeks", "January")
  --space TEXT        AnyType space name or ID
  --help              Show this message and exit.
```

#### jarvis journal insights

```
Usage: jarvis journal insights [OPTIONS]

  AI analysis across journal entries.

Options:
  --since TEXT        Analysis window (default: "2 weeks")
  --month TEXT        Specific month to analyze
  --limit INTEGER     Max entries to analyze (default: 50)
  --space TEXT        AnyType space name or ID
  --help              Show this message and exit.
```

#### jarvis j (alias)

```
Usage: jarvis j [OPTIONS] [TEXT]

  Alias for 'jarvis journal write'.
```

---

## 5. Infrastructure & Deployment

### Dependencies

No new dependencies required. Uses existing:

| Dependency | Purpose | Status |
|------------|---------|--------|
| `anytype-client` | AnyType API operations | Existing |
| `anthropic` | Claude API for AI features | Existing |
| `click` | CLI framework | Existing |
| `rich` | Terminal formatting | Existing |
| `pydantic` | Data models | Existing |

### Configuration Extensions

Add to existing settings:

```python
# In config or environment
JARVIS_JOURNAL_COLLECTION = "Journal"  # Default collection name
JARVIS_JOURNAL_ENTRY_TYPE = "Page"     # AnyType type for entries
JARVIS_DEEP_DIVE_ENABLED = True        # Enable deep dive prompts
```

### File System Requirements

```bash
# Ensure journal directory exists on first use
~/.jarvis/journal/
~/.jarvis/journal/deep_dives/
~/.jarvis/journal/drafts/
```

---

## 6. Security Architecture

### Data Privacy

| Data Type | Storage | Sent Externally |
|-----------|---------|-----------------|
| Journal content | AnyType + local preview | Yes (to Claude for title/deep dive) |
| Entry metadata | Local JSON | No |
| Deep dive responses | Local JSON | No (received from Claude) |
| Draft content | Local text files | No |

### Security Considerations

1. **Journal content privacy**: Entry content is sent to Claude for AI features. Users should be aware of this.
2. **Local storage**: All journal references and deep dives stored in `~/.jarvis/journal/` with standard file permissions.
3. **Draft recovery**: Failed saves stored locally, auto-cleaned after 7 days.
4. **No cloud sync**: Journal context stays local; AnyType handles its own sync.

---

## 7. Integration Architecture

### Entry Capture Module

```python
# journal/capture.py

import os
import subprocess
import tempfile
from enum import Enum


class CaptureMode(str, Enum):
    INLINE = "inline"
    EDITOR = "editor"
    INTERACTIVE = "interactive"


def capture_entry(
    mode: CaptureMode,
    initial_text: str = "",
) -> str | None:
    """Capture journal entry content.

    Args:
        mode: Capture mode to use
        initial_text: Pre-filled text for inline mode

    Returns:
        Entry content or None if cancelled
    """
    if mode == CaptureMode.INLINE:
        return initial_text if initial_text.strip() else None

    elif mode == CaptureMode.EDITOR:
        return _capture_via_editor(initial_text)

    elif mode == CaptureMode.INTERACTIVE:
        return _capture_interactive()


def _capture_via_editor(initial_text: str = "") -> str | None:
    """Open $EDITOR for entry capture."""
    editor = os.environ.get("EDITOR", "nano")

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".md",
        delete=False
    ) as f:
        f.write(initial_text)
        temp_path = f.name

    try:
        subprocess.run([editor, temp_path], check=True)
        with open(temp_path, "r") as f:
            content = f.read().strip()
        return content if content else None
    finally:
        os.unlink(temp_path)


def _capture_interactive() -> str | None:
    """Interactive multi-line capture."""
    from rich.console import Console

    console = Console()
    console.print("[dim]Enter your journal entry (Ctrl+D or empty line to finish):[/dim]")
    console.print()

    lines = []
    try:
        while True:
            line = input()
            if not line and lines and not lines[-1]:
                # Two empty lines = done
                break
            lines.append(line)
    except EOFError:
        pass

    content = "\n".join(lines).strip()
    return content if content else None
```

### Hierarchy Manager

```python
# journal/hierarchy.py

from datetime import date
from jarvis.anytype_client import AnyTypeClient


class JournalHierarchy:
    """Manages Journal → Year → Month hierarchy in AnyType."""

    MONTHS = [
        "January", "February", "March", "April",
        "May", "June", "July", "August",
        "September", "October", "November", "December"
    ]

    def __init__(self, client: AnyTypeClient, space_id: str):
        self.client = client
        self.space_id = space_id
        self._journal_id: str | None = None
        self._year_cache: dict[int, str] = {}
        self._month_cache: dict[tuple[int, int], str] = {}

    def get_journal_collection(self) -> str:
        """Get or create the Journal collection."""
        if self._journal_id:
            return self._journal_id

        self._journal_id = self.client.get_or_create_collection(
            self.space_id, "Journal"
        )
        return self._journal_id

    def get_year_container(self, year: int) -> str:
        """Get or create a year container."""
        if year in self._year_cache:
            return self._year_cache[year]

        journal_id = self.get_journal_collection()
        year_id = self.client.get_or_create_container(
            self.space_id, journal_id, str(year)
        )
        self._year_cache[year] = year_id
        return year_id

    def get_month_container(self, year: int, month: int) -> str:
        """Get or create a month container."""
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
        """Get the path string for a date."""
        month_name = self.MONTHS[entry_date.month - 1]
        return f"Journal/{entry_date.year}/{month_name}"

    def create_entry(
        self,
        entry_date: date,
        title: str,
        content: str,
    ) -> str:
        """Create a journal entry in the correct location.

        Returns:
            Created entry object ID
        """
        month_id = self.get_month_container(
            entry_date.year,
            entry_date.month
        )

        full_title = f"{entry_date.day} - {title}"

        return self.client.create_page(
            self.space_id,
            name=full_title,
            content=content,
            parent_id=month_id,
        )
```

### AI Prompt Templates

```python
# journal/prompts.py

TITLE_GENERATION_SYSTEM = """You are a journaling assistant that generates concise,
meaningful titles for journal entries.

Guidelines:
- Create titles that are 3-7 words
- Capture the essence or main theme, not every detail
- Avoid generic titles like "Journal Entry" or "Today's Thoughts"
- Include emotional tone when relevant (e.g., "Breakthrough Moment on Project X")
- Use active, descriptive language

Output ONLY the title, nothing else."""

TITLE_GENERATION_PROMPT = """Generate a concise title for this journal entry:

---
{content}
---

Title:"""


DEEP_DIVE_SYSTEM = """You are a thoughtful journaling companion that helps users
reflect more deeply on their entries.

Your approach:
- Reference specific content from the user's entry
- Ask thoughtful questions rather than lecturing
- Match the user's emotional tone
- Be warm but not effusive
- Provide genuine insight, not platitudes

The user will specify what kind of analysis they want. Adapt your response
to match their request."""

DEEP_DIVE_PROMPT = """The user wrote this journal entry:

---
{content}
---

They want a deep dive with this focus: {focus}

Provide a thoughtful, personalized response that explores their entry
through this lens. Keep it to 2-4 paragraphs."""


INSIGHTS_SYSTEM = """You are an insightful pattern recognition assistant
that analyzes journal entries over time.

Your approach:
- Identify non-obvious patterns and themes
- Use specific examples from entries
- Note behavioral patterns (when they journal, recurring topics)
- Be honest about limited data
- Surface both positive patterns and areas of potential concern
- Avoid generic observations

Output your analysis in a conversational, supportive tone."""

INSIGHTS_PROMPT = """Analyze these journal entries from {time_range}:

---
{entries}
---

Number of entries analyzed: {count}

Provide insights covering:
1. Recurring themes (topics that appear multiple times)
2. Patterns (behavioral, emotional, or temporal)
3. One key observation or insight

Keep your response focused and specific to this person's entries."""


METADATA_EXTRACTION_SYSTEM = """You extract tags and themes from journal entries.

Output a JSON object with:
- tags: list of 1-5 relevant tags (lowercase, single words or short phrases)
- mood: detected mood (positive, negative, neutral, mixed)
- topics: list of main topics discussed

Example: {"tags": ["work", "relationships", "growth"], "mood": "mixed", "topics": ["project deadline", "conversation with partner"]}"""

METADATA_EXTRACTION_PROMPT = """Extract metadata from this journal entry:

---
{content}
---

JSON:"""
```

### Journal State Management

```python
# journal/state.py

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from jarvis.journal.models import JournalEntryReference, DeepDive


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
    """Load all entry references from disk."""
    if not ENTRIES_FILE.exists():
        return []

    try:
        data = json.loads(ENTRIES_FILE.read_text())
        return [
            JournalEntryReference(**e)
            for e in data.get("entries", [])
        ]
    except (json.JSONDecodeError, KeyError):
        return []


def save_entry_reference(ref: JournalEntryReference) -> None:
    """Add an entry reference to the index."""
    ensure_journal_dirs()

    entries = load_entries()

    # Check if already exists (update) or new (append)
    existing_idx = next(
        (i for i, e in enumerate(entries) if e.id == ref.id),
        None
    )

    if existing_idx is not None:
        entries[existing_idx] = ref
    else:
        entries.insert(0, ref)  # Newest first

    _write_entries(entries)


def _write_entries(entries: list[JournalEntryReference]) -> None:
    """Write entries index to disk."""
    data = {
        "version": "1.0",
        "updated_at": datetime.now().isoformat(),
        "entries": [e.model_dump(mode="json") for e in entries]
    }
    ENTRIES_FILE.write_text(json.dumps(data, indent=2, default=str))


def load_deep_dives(entry_id: str) -> list[DeepDive]:
    """Load deep dives for an entry."""
    dd_file = DEEP_DIVES_DIR / f"{entry_id}.json"
    if not dd_file.exists():
        return []

    try:
        data = json.loads(dd_file.read_text())
        return [DeepDive(**dd) for dd in data.get("deep_dives", [])]
    except (json.JSONDecodeError, KeyError):
        return []


def save_deep_dive(entry_id: str, deep_dive: DeepDive) -> None:
    """Save a deep dive for an entry."""
    ensure_journal_dirs()

    existing = load_deep_dives(entry_id)
    existing.append(deep_dive)

    data = {
        "entry_id": entry_id,
        "deep_dives": [dd.model_dump(mode="json") for dd in existing]
    }

    dd_file = DEEP_DIVES_DIR / f"{entry_id}.json"
    dd_file.write_text(json.dumps(data, indent=2, default=str))


def save_draft(content: str) -> Path:
    """Save draft content for recovery."""
    ensure_journal_dirs()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    draft_file = DRAFTS_DIR / f"{timestamp}.txt"
    draft_file.write_text(content)
    return draft_file


def cleanup_old_drafts(max_age_days: int = 7) -> None:
    """Remove drafts older than max_age_days."""
    if not DRAFTS_DIR.exists():
        return

    from datetime import timedelta
    cutoff = datetime.now() - timedelta(days=max_age_days)

    for draft in DRAFTS_DIR.glob("*.txt"):
        if datetime.fromtimestamp(draft.stat().st_mtime) < cutoff:
            draft.unlink()
```

---

## 8. Performance & Scalability

### Performance Targets

| Operation | Target | Measurement |
|-----------|--------|-------------|
| Inline capture to save confirmation | <3s | Wall clock time |
| AI title generation | <2s | Claude API latency |
| Deep dive generation | <10s | Claude API latency |
| List 10 entries | <2s | Local + AnyType query |
| Search 100 entries | <5s | AnyType search |
| Insights (50 entries) | <15s | Claude API latency |

### Optimization Strategies

#### Entry Reference Caching

```python
# Cache entry references in memory during session
class EntryCache:
    """In-memory cache for entry references."""

    def __init__(self):
        self._entries: list[JournalEntryReference] | None = None
        self._loaded_at: datetime | None = None
        self._ttl = timedelta(minutes=5)

    def get_entries(self) -> list[JournalEntryReference]:
        if self._is_stale():
            self._entries = load_entries()
            self._loaded_at = datetime.now()
        return self._entries or []

    def _is_stale(self) -> bool:
        if not self._loaded_at:
            return True
        return datetime.now() - self._loaded_at > self._ttl

    def invalidate(self) -> None:
        self._entries = None
        self._loaded_at = None
```

#### Batch Hierarchy Resolution

```python
# Pre-resolve hierarchy on first journal access
def warm_hierarchy_cache(
    hierarchy: JournalHierarchy,
    current_date: date
) -> None:
    """Pre-cache current month containers."""
    hierarchy.get_month_container(
        current_date.year,
        current_date.month
    )
```

### Scalability Considerations

| Scenario | Limit | Handling |
|----------|-------|----------|
| Entries per user | 10,000+ | Paginated retrieval, local index |
| Deep dives per entry | 10 max | UI limit, file rotation |
| Insights analysis | 50 entries max | Token limits, date filtering |
| Draft storage | 7 days | Auto-cleanup |

---

## 9. Reliability & Operations

### Error Handling Strategy

```python
from enum import Enum


class JournalErrorCode(str, Enum):
    ANYTYPE_NOT_RUNNING = "anytype_not_running"
    COLLECTION_CREATE_FAILED = "collection_create_failed"
    ENTRY_SAVE_FAILED = "entry_save_failed"
    AI_UNAVAILABLE = "ai_unavailable"
    EMPTY_ENTRY = "empty_entry"
    ENTRY_NOT_FOUND = "entry_not_found"


class JournalError(Exception):
    """Journal-specific error."""

    def __init__(
        self,
        code: JournalErrorCode,
        message: str,
        recoverable: bool = True
    ):
        self.code = code
        self.message = message
        self.recoverable = recoverable
        super().__init__(message)
```

### Fallback Behaviors

| Failure | Fallback |
|---------|----------|
| AI title generation fails | Use "DD - Journal Entry" format |
| AnyType save fails | Save to drafts/, display path for recovery |
| Deep dive AI fails | Skip deep dive, notify user |
| Insights AI fails | Display error, suggest smaller time range |
| Collection not found | Auto-create with confirmation |

### Draft Recovery Flow

```python
def recover_from_draft(draft_path: Path) -> None:
    """Recover a journal entry from a saved draft."""
    content = draft_path.read_text()
    console.print(f"[yellow]Recovered draft from {draft_path}[/yellow]")
    console.print()
    console.print(content[:200] + "..." if len(content) > 200 else content)
    console.print()

    if Confirm.ask("Retry saving this entry?"):
        # Re-run the save flow
        ...
```

---

## 10. Development Standards

### Code Style

Consistent with existing Jarvis codebase:

- **Formatter:** Ruff
- **Linter:** Ruff
- **Type Checker:** mypy (strict mode)
- **Line Length:** 100 characters

### Testing Strategy

```python
# tests/journal/test_capture.py
import pytest
from jarvis.journal.capture import capture_entry, CaptureMode


def test_inline_capture_with_text():
    result = capture_entry(CaptureMode.INLINE, "Test entry")
    assert result == "Test entry"


def test_inline_capture_empty():
    result = capture_entry(CaptureMode.INLINE, "   ")
    assert result is None


# tests/journal/test_hierarchy.py
def test_get_path():
    from datetime import date
    from jarvis.journal.hierarchy import JournalHierarchy

    # Mock client
    hierarchy = JournalHierarchy(mock_client, "space_1")
    path = hierarchy.get_path(date(2026, 1, 24))
    assert path == "Journal/2026/January"


# tests/journal/test_state.py
def test_save_and_load_entry_reference(tmp_path, monkeypatch):
    monkeypatch.setattr("jarvis.journal.state.JOURNAL_DIR", tmp_path)

    ref = JournalEntryReference(
        id="entry_1",
        space_id="space_1",
        path="Journal/2026/January",
        title="24 - Test Entry",
        date=date(2026, 1, 24),
        created_at=datetime.now(),
    )

    save_entry_reference(ref)
    loaded = load_entries()

    assert len(loaded) == 1
    assert loaded[0].id == "entry_1"
```

### Test Coverage Targets

| Component | Target |
|-----------|--------|
| Entry capture | 90% |
| Hierarchy manager | 85% |
| State management | 90% |
| CLI commands | 80% |
| AI integration | 60% (mocked) |

---

## 11. Implementation Roadmap

### Phase 1: Foundation

| Task | Priority | Dependencies |
|------|----------|--------------|
| Journal models (JournalEntry, DeepDive) | P0 | None |
| Journal state module | P0 | Models |
| AnyType client extensions | P0 | Existing client |
| Hierarchy manager | P0 | AnyType extensions |
| Entry capture module | P0 | None |

**Deliverable:** Can create and store journal entries in AnyType

### Phase 2: Core CLI

| Task | Priority | Dependencies |
|------|----------|--------------|
| `jarvis journal write` command | P0 | All Phase 1 |
| AI title generation | P0 | AI client |
| `jarvis journal list` command | P0 | State module |
| `jarvis journal read` command | P0 | State + AnyType |
| Deep dive prompt flow | P1 | AI client |

**Deliverable:** Working write/list/read with AI titles and deep dive

### Phase 3: Retrieval & Insights

| Task | Priority | Dependencies |
|------|----------|--------------|
| `jarvis journal search` command | P0 | AnyType search |
| Deep dive persistence | P0 | State module |
| `jarvis journal insights` command | P1 | AI client |
| Metadata extraction | P2 | AI client |

**Deliverable:** Complete journaling feature set

### Phase 4: Polish

| Task | Priority | Dependencies |
|------|----------|--------------|
| `jarvis j` alias | P1 | CLI |
| Draft recovery flow | P1 | State module |
| Error handling refinement | P1 | All |
| Documentation | P1 | All |
| Integration tests | P2 | All |

**Deliverable:** Production-ready journaling capability

---

## 12. Appendices

### A. CLI Output Examples

#### Write Command

```
$ jarvis journal write "Had a breakthrough on the API design today"

✓ Saved to Journal/2026/January
  └─ 24 - Breakthrough on API Design

Would you like a deep dive? [y/N]: y
What format or focus? (e.g., emotions, action items, Socratic questions)
> explore what led to the breakthrough

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Deep Dive: The Breakthrough
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You mention the "breakthrough" but the entry focuses on the outcome.
What was different about today's approach?

A few threads to explore:
• Was there a specific moment of clarity, or a gradual realization?
• What had you been trying before that wasn't working?
• Who or what helped shift your perspective?

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

#### List Command

```
$ jarvis journal list --limit 5

📔 Recent Journal Entries
━━━━━━━━━━━━━━━━━━━━━━━━━

  Jan 24  24 - Breakthrough on API Design
          "Had a breakthrough on the API design today..."

  Jan 24  24 - Morning Reflection
          "Woke up thinking about the project deadline..."

  Jan 23  23 - Weekly Planning
          "Starting the week with clear intentions..."

  Jan 22  22 - Frustrations with Dependencies
          "Spent too long debugging dependency issues..."

  Jan 21  21 - Weekend Thoughts
          "Taking a step back from code today..."

━━━━━━━━━━━━━━━━━━━━━━━━━
5 of 47 entries shown
```

#### Insights Command

```
$ jarvis journal insights --since "2 weeks"

💡 Insights from 12 entries (Jan 10 - Jan 24)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Recurring Themes:
• Work-life balance (mentioned in 5 entries)
• API design is a current focus (4 entries)
• Sleep and energy levels (3 entries)

Patterns:
• You journal most on weekday mornings
• Positive entries often use "clarity" or "breakthrough" language
• Stress entries correlate with "should" and "need to"

Observation:
Your entries this week show more resolution than last week.
The API breakthrough seems connected to the Monday planning
session where you decided to "step back and rethink."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### B. Error Messages

| Error | User-Facing Message |
|-------|---------------------|
| `anytype_not_running` | "AnyType desktop must be running. Please start it and try again." |
| `collection_create_failed` | "Could not create Journal collection. Check AnyType permissions." |
| `entry_save_failed` | "Failed to save entry. Your text has been saved to ~/.jarvis/journal/drafts/{timestamp}.txt" |
| `ai_unavailable` | "AI features unavailable. Entry saved with default title." |
| `empty_entry` | "Entry is empty. Nothing saved." |
| `entry_not_found` | "No entry found for '{identifier}'." |

### C. Configuration Reference

| Setting | Default | Description |
|---------|---------|-------------|
| `JARVIS_JOURNAL_COLLECTION` | `"Journal"` | Collection name in AnyType |
| `JARVIS_DEEP_DIVE_ENABLED` | `true` | Prompt for deep dive after save |
| `JARVIS_DRAFT_RETENTION_DAYS` | `7` | Days to keep draft files |
| `JARVIS_INSIGHTS_MAX_ENTRIES` | `50` | Max entries for insights analysis |

### D. Related Documents

- `brainstorm.md` — Original ideation
- `product_spec.md` — Product requirements
- `../01_task-scheduler/technical_spec.md` — Existing Jarvis architecture

---

*Technical Specification v1.0*
*Created: 2026-01-24*
*Status: Ready for implementation*
