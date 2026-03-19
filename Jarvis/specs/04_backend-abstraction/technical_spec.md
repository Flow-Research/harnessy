# Technical Specification: Backend Abstraction Layer

> **Epic:** 04_backend-abstraction
> **Version:** 1.1
> **Created:** 2025-01-25
> **Status:** Reviewed
> **Source:** [product_spec.md](./product_spec.md)

---

## 1. Overview

### 1.1 Purpose

This document provides the complete technical blueprint for implementing a pluggable backend abstraction layer in Jarvis, enabling the CLI to work with multiple knowledge base systems (AnyType, Notion, and future backends) through a unified interface.

### 1.2 Scope

**In Scope:**
- `KnowledgeBaseAdapter` protocol definition
- Adapter registry and factory pattern
- Configuration management system
- Typed exception hierarchy with retry logic
- AnyType adapter (refactored from existing client)
- Notion adapter (new implementation)
- CLI integration with capability detection
- Domain model definitions

**Out of Scope:**
- Cross-backend synchronization
- Data migration tools
- GUI configuration interface
- Adapters beyond AnyType and Notion (Phase 1)

### 1.3 Technical Summary

| Aspect | Decision |
|--------|----------|
| Architecture Style | Modular monolith with strategy pattern |
| Language | Python 3.11+ |
| Adapter Interface | Protocol (structural subtyping) |
| Configuration | Pydantic Settings (YAML + env vars) |
| HTTP Client | httpx (async capable) |
| Notion SDK | notion-sdk-py |
| Error Handling | Typed exceptions with retry decorator |

---

## 2. System Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                           Jarvis CLI Layer                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐│
│  │   cli.py    │  │ task/cli.py │  │journal/cli.py│  │config/cli.py││
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘│
└─────────┼────────────────┼────────────────┼────────────────┼────────┘
          │                │                │                │
          └────────────────┴────────────────┴────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Service Layer                               │
│  ┌────────────────────┐  ┌────────────────────┐                    │
│  │   TaskService      │  │   JournalService   │                    │
│  │  - create_task()   │  │  - create_entry()  │                    │
│  │  - get_tasks()     │  │  - get_entries()   │                    │
│  │  - update_task()   │  │  - search()        │                    │
│  └─────────┬──────────┘  └─────────┬──────────┘                    │
└────────────┼────────────────────────┼───────────────────────────────┘
             │                        │
             └────────────┬───────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Adapter Layer                                  │
│  ┌────────────────────────────────────────────────────────────────┐│
│  │                    AdapterRegistry                             ││
│  │  - get_adapter() → KnowledgeBaseAdapter                        ││
│  │  - list_adapters() → list[str]                                 ││
│  │  - register_adapter(name, adapter_class)                       ││
│  └─────────────────────────┬──────────────────────────────────────┘│
│                            │                                        │
│  ┌─────────────────────────┴──────────────────────────────────────┐│
│  │              KnowledgeBaseAdapter (Protocol)                   ││
│  │  - capabilities: dict[str, bool]                               ││
│  │  - connect() / disconnect() / is_connected()                   ││
│  │  - Task CRUD operations                                        ││
│  │  - Journal CRUD operations                                     ││
│  │  - Tag operations                                              ││
│  └────────────────────────────────────────────────────────────────┘│
│                            │                                        │
│            ┌───────────────┼───────────────┐                       │
│            ▼               ▼               ▼                       │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐       │
│  │ AnyTypeAdapter  │ │ NotionAdapter   │ │ (Future...)     │       │
│  │                 │ │                 │ │                 │       │
│  │ gRPC → AnyType  │ │ HTTP → Notion   │ │                 │       │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘       │
└─────────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Domain Models                                  │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐    │
│  │   Task     │  │JournalEntry│  │   Space    │  │    Tag     │    │
│  └────────────┘  └────────────┘  └────────────┘  └────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Component Responsibilities

| Component | Responsibility |
|-----------|----------------|
| **CLI Layer** | Parse commands, format output, handle user interaction |
| **Service Layer** | Business logic, capability checking, error translation |
| **AdapterRegistry** | Adapter lifecycle, configuration injection, singleton management |
| **KnowledgeBaseAdapter** | Abstract interface for all backend operations |
| **Concrete Adapters** | Backend-specific implementations (AnyType, Notion) |
| **Domain Models** | Backend-agnostic data structures |

### 2.3 Directory Structure

```
src/jarvis/
├── __init__.py
├── __main__.py
├── cli.py                      # Main CLI entry point (modified)
├── adapters/                   # NEW: Adapter system
│   ├── __init__.py             # AdapterRegistry + exports
│   ├── base.py                 # KnowledgeBaseAdapter protocol
│   ├── exceptions.py           # Typed exceptions
│   ├── retry.py                # Retry decorator with backoff
│   ├── anytype/                # AnyType adapter package
│   │   ├── __init__.py
│   │   ├── adapter.py          # AnyTypeAdapter implementation
│   │   └── client.py           # Low-level gRPC client (refactored)
│   └── notion/                 # Notion adapter package
│       ├── __init__.py
│       ├── adapter.py          # NotionAdapter implementation
│       ├── client.py           # Notion SDK wrapper
│       └── mappings.py         # Notion ↔ Domain model conversions
├── config/                     # NEW: Configuration system
│   ├── __init__.py
│   ├── loader.py               # YAML + env var loading
│   ├── schema.py               # Pydantic config models
│   └── defaults.py             # Default configuration values
├── models/                     # NEW: Shared domain models
│   ├── __init__.py             # Re-exports all models
│   ├── task.py                 # Task model (migrated from models.py)
│   ├── journal.py              # JournalEntry model
│   ├── space.py                # Space model
│   ├── tag.py                  # Tag model
│   └── priority.py             # Priority enum
├── services/                   # NEW: Service layer
│   ├── __init__.py
│   ├── task_service.py         # Task operations with capability check
│   └── journal_service.py      # Journal operations with capability check
├── task/                       # Existing task CLI (modified)
│   ├── __init__.py
│   ├── cli.py                  # Task subcommands
│   ├── date_parser.py
│   ├── editor.py
│   └── service.py              # Legacy, to be migrated
├── journal/                    # Existing journal CLI (modified)
│   ├── __init__.py
│   ├── cli.py                  # Journal subcommands
│   ├── capture.py
│   ├── hierarchy.py            # To be abstracted
│   ├── models.py               # Migrated to models/journal.py
│   ├── prompts.py
│   └── state.py
├── ai_client.py                # Existing AI client (unchanged)
├── analyzer.py                 # Existing analyzer (modified to use adapter)
├── context_reader.py           # Existing context reader (unchanged)
├── models.py                   # Legacy, re-export from models/
├── prompts.py                  # Existing prompts (unchanged)
└── state.py                    # Existing state (unchanged)
```

---

## 3. Data Architecture

### 3.1 Domain Models

All models use Pydantic for validation and serialization.

#### 3.1.1 Priority Enum

```python
# src/jarvis/models/priority.py
from enum import Enum

class Priority(str, Enum):
    """Task priority levels."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @classmethod
    def from_string(cls, value: str | None) -> "Priority | None":
        """Parse priority from string, returning None for invalid values."""
        if value is None:
            return None
        try:
            return cls(value.lower())
        except ValueError:
            return None
```

#### 3.1.2 Space Model

```python
# src/jarvis/models/space.py
from pydantic import BaseModel, Field

class Space(BaseModel):
    """Represents a workspace/container in any backend."""

    id: str = Field(description="Backend-specific space identifier")
    name: str = Field(description="Human-readable space name")
    backend: str = Field(description="Backend type (anytype, notion, etc.)")

    class Config:
        frozen = True  # Immutable
```

#### 3.1.3 Tag Model

```python
# src/jarvis/models/tag.py
from pydantic import BaseModel, Field

class Tag(BaseModel):
    """Represents a categorization tag."""

    id: str = Field(description="Backend-specific tag identifier")
    name: str = Field(description="Tag display name")
    color: str | None = Field(default=None, description="Optional color code")

    class Config:
        frozen = True
```

#### 3.1.4 Task Model

```python
# src/jarvis/models/task.py
from datetime import date, datetime
from pydantic import BaseModel, Field, computed_field
from .priority import Priority

class Task(BaseModel):
    """Represents a task in any backend."""

    id: str = Field(description="Backend-specific task identifier")
    space_id: str = Field(description="Space this task belongs to")
    title: str = Field(description="Task title/name")
    description: str | None = Field(default=None, description="Task description")
    due_date: date | None = Field(default=None, description="Due date")
    priority: Priority | None = Field(default=None, description="Priority level")
    tags: list[str] = Field(default_factory=list, description="Tag names")
    is_done: bool = Field(default=False, description="Completion status")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last modification timestamp")

    # Computed properties for backward compatibility
    @computed_field
    @property
    def name(self) -> str:
        """Alias for title (backward compatibility)."""
        return self.title

    @computed_field
    @property
    def scheduled_date(self) -> date | None:
        """Alias for due_date (backward compatibility with existing code)."""
        return self.due_date

    @computed_field
    @property
    def is_moveable(self) -> bool:
        """Task can be rescheduled if not tagged bar_movement."""
        return "bar_movement" not in self.tags
```

#### 3.1.5 JournalEntry Model

```python
# src/jarvis/models/journal.py
from datetime import date, datetime
from pydantic import BaseModel, Field, computed_field

class JournalEntry(BaseModel):
    """Represents a journal entry in any backend."""

    id: str = Field(description="Backend-specific entry identifier")
    space_id: str = Field(description="Space this entry belongs to")
    title: str = Field(description="Entry title")
    content: str = Field(description="Entry content (markdown)")
    entry_date: date = Field(description="Date of the journal entry")
    tags: list[str] = Field(default_factory=list, description="Associated tags")
    created_at: datetime = Field(description="Creation timestamp")

    # Optional: Path for hierarchical backends (AnyType)
    path: str | None = Field(default=None, description="Hierarchical path if applicable")

    @computed_field
    @property
    def day_prefix(self) -> str:
        """Day number for title prefix."""
        return str(self.entry_date.day)
```

### 3.2 Configuration Schema

#### 3.2.1 Config File Structure

```yaml
# ~/.jarvis/config.yaml
version: 1

# Which backend to use for all operations
active_backend: anytype

# Backend-specific configuration
backends:
  anytype:
    # AnyType uses local gRPC, minimal config needed
    # Default space is auto-detected

  notion:
    # Required: Notion workspace and database IDs
    workspace_id: "your-workspace-id"
    task_database_id: "your-tasks-db-id"
    journal_database_id: "your-journal-db-id"

    # Optional: Custom property mappings
    property_mappings:
      priority: "Priority"        # Default
      due_date: "Due Date"        # Default
      tags: "Tags"                # Default
      done: "Done"                # Default

# Optional: Analytics settings
analytics:
  enabled: false  # Opt-in only
  metrics_file: "~/.jarvis/metrics.json"
```

#### 3.2.2 Pydantic Config Models

```python
# src/jarvis/config/schema.py
from pathlib import Path
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class NotionConfig(BaseModel):
    """Notion-specific configuration."""
    workspace_id: str = Field(description="Notion workspace ID")
    task_database_id: str = Field(description="Tasks database ID")
    journal_database_id: str = Field(description="Journal database ID")
    property_mappings: dict[str, str] = Field(
        default_factory=lambda: {
            "priority": "Priority",
            "due_date": "Due Date",
            "tags": "Tags",
            "done": "Done",
        }
    )

class AnyTypeConfig(BaseModel):
    """AnyType-specific configuration."""
    # AnyType has minimal config - uses localhost gRPC
    default_space_id: str | None = Field(
        default=None,
        description="Optional: Pre-select space ID"
    )

class BackendsConfig(BaseModel):
    """Container for all backend configurations."""
    anytype: AnyTypeConfig = Field(default_factory=AnyTypeConfig)
    notion: NotionConfig | None = Field(default=None)

class AnalyticsConfig(BaseModel):
    """Analytics configuration."""
    enabled: bool = Field(default=False)
    metrics_file: str = Field(default="~/.jarvis/metrics.json")

class JarvisConfig(BaseSettings):
    """Root configuration model."""

    model_config = SettingsConfigDict(
        env_prefix="JARVIS_",
        env_nested_delimiter="__",
    )

    version: int = Field(default=1)
    active_backend: str = Field(default="anytype")
    backends: BackendsConfig = Field(default_factory=BackendsConfig)
    analytics: AnalyticsConfig = Field(default_factory=AnalyticsConfig)

    @field_validator("active_backend")
    @classmethod
    def validate_backend(cls, v: str) -> str:
        valid_backends = {"anytype", "notion"}
        if v not in valid_backends:
            raise ValueError(f"Invalid backend: {v}. Must be one of: {valid_backends}")
        return v
```

#### 3.2.3 Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `JARVIS_NOTION_TOKEN` | Notion API integration token | `secret_abc123...` |
| `JARVIS_ACTIVE_BACKEND` | Override active backend | `notion` |
| `NOTION_TOKEN` | Fallback Notion token (lower priority) | `secret_abc123...` |

**Token Resolution Priority:**
1. `JARVIS_NOTION_TOKEN` (specific)
2. `NOTION_TOKEN` (generic fallback)

### 3.3 Data Flow

#### 3.3.1 Create Task Flow

```
User: jarvis t "Buy groceries" --due tomorrow --priority high
                │
                ▼
┌─────────────────────────────────────────────────────────┐
│  CLI Layer (cli.py / task/cli.py)                       │
│  1. Parse arguments                                      │
│  2. Parse date ("tomorrow" → date object)                │
│  3. Call TaskService.create_task()                       │
└─────────────────────────┬───────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────┐
│  Service Layer (services/task_service.py)               │
│  1. Get adapter from registry                            │
│  2. Check adapter.capabilities["tasks"]                  │
│  3. Get default space if not specified                   │
│  4. Call adapter.create_task(...)                        │
│  5. Return Task model                                    │
└─────────────────────────┬───────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────┐
│  Adapter Layer (e.g., NotionAdapter)                    │
│  1. Map Priority enum to Notion select value             │
│  2. Map date to Notion date format                       │
│  3. Call Notion API: pages.create(...)                   │
│  4. Map response to Task model                           │
│  5. Return Task                                          │
└─────────────────────────┬───────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────┐
│  Notion API                                             │
│  POST /v1/pages                                          │
│  Response: { id: "...", properties: {...} }              │
└─────────────────────────────────────────────────────────┘
```

---

## 4. API Specification

### 4.1 KnowledgeBaseAdapter Protocol

```python
# src/jarvis/adapters/base.py
from typing import Protocol, runtime_checkable
from datetime import date
from ..models import Task, JournalEntry, Space, Tag, Priority

@runtime_checkable
class KnowledgeBaseAdapter(Protocol):
    """Protocol that all backend adapters must implement.

    Adapters provide a consistent interface for CRUD operations
    on tasks, journal entries, and tags across different backends.

    Usage:
        adapter = registry.get_adapter()
        adapter.connect()
        tasks = adapter.get_tasks(space_id)
    """

    # =========================================================================
    # Capability Declaration
    # =========================================================================

    @property
    def capabilities(self) -> dict[str, bool]:
        """Declare supported capabilities.

        Returns:
            Dict mapping capability names to support status.

        Required capabilities:
            - tasks: Task CRUD operations
            - journal: Journal entry CRUD operations
            - tags: Tag management
            - search: Full-text search
            - priorities: Task priority levels
            - due_dates: Task due dates
            - daily_notes: Automatic daily note creation
            - relations: Links between items
            - custom_properties: User-defined fields
        """
        ...

    @property
    def backend_name(self) -> str:
        """Return the backend identifier (e.g., 'anytype', 'notion')."""
        ...

    # =========================================================================
    # Connection Management
    # =========================================================================

    def connect(self) -> None:
        """Establish connection to the backend.

        Raises:
            ConnectionError: If connection cannot be established
            AuthError: If authentication fails
        """
        ...

    def disconnect(self) -> None:
        """Close connection to the backend gracefully."""
        ...

    def is_connected(self) -> bool:
        """Check if currently connected to the backend.

        Returns:
            True if connected and authenticated, False otherwise.
        """
        ...

    # =========================================================================
    # Space Operations
    # =========================================================================

    def list_spaces(self) -> list[Space]:
        """List all available spaces/workspaces.

        Returns:
            List of Space objects.

        Raises:
            ConnectionError: If not connected
        """
        ...

    def get_default_space(self) -> str:
        """Get the default/current space ID.

        Returns:
            Space ID string.

        Raises:
            ConnectionError: If not connected
            NotFoundError: If no spaces exist
        """
        ...

    def set_default_space(self, space_id: str) -> None:
        """Set the default space for operations.

        Args:
            space_id: ID of space to make default

        Raises:
            NotFoundError: If space doesn't exist
        """
        ...

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
        """Create a new task.

        Args:
            space_id: Space to create task in
            title: Task title
            due_date: Optional due date
            priority: Optional priority level
            tags: Optional list of tag names
            description: Optional description/notes

        Returns:
            Created Task object with ID populated.

        Raises:
            NotSupportedError: If tasks capability is False
            ConnectionError: If not connected
        """
        ...

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
        ...

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
        """
        ...

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
            tags: New tags list (optional, replaces existing)
            description: New description (optional)
            is_done: New completion status (optional)

        Returns:
            Updated Task object.

        Raises:
            NotFoundError: If task doesn't exist
            ConnectionError: If not connected
        """
        ...

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
        ...

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

        Args:
            space_id: Space to create entry in
            content: Entry content (markdown)
            title: Optional title (may be auto-generated)
            entry_date: Date for entry (defaults to today)

        Returns:
            Created JournalEntry object.

        Raises:
            NotSupportedError: If journal capability is False
            ConnectionError: If not connected
        """
        ...

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
        ...

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
        ...

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
        ...

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
        ...

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
            offset: Number of results to skip (for pagination)

        Returns:
            List of matching JournalEntry objects.

        Raises:
            NotSupportedError: If search capability is False
            ConnectionError: If not connected
        """
        ...

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
            NotSupportedError: If tags capability is False
            ConnectionError: If not connected
        """
        ...

    def create_tag(self, space_id: str, name: str, color: str | None = None) -> Tag:
        """Create a new tag.

        Args:
            space_id: Space to create tag in
            name: Tag name
            color: Optional color code (backend-specific format)

        Returns:
            Created Tag object.

        Raises:
            NotSupportedError: If tags capability is False
            ConnectionError: If not connected
        """
        ...
```

### 4.2 Adapter Registry

```python
# src/jarvis/adapters/__init__.py
from typing import Type
from .base import KnowledgeBaseAdapter
from .exceptions import AdapterNotFoundError
from ..config import get_config

class AdapterRegistry:
    """Registry for adapter classes and instances.

    Manages adapter lifecycle and provides configured adapters
    to the rest of the application.

    Usage:
        registry = AdapterRegistry()
        adapter = registry.get_adapter()  # Returns configured adapter
    """

    _adapters: dict[str, Type[KnowledgeBaseAdapter]] = {}
    _instances: dict[str, KnowledgeBaseAdapter] = {}

    @classmethod
    def register(cls, name: str, adapter_class: Type[KnowledgeBaseAdapter]) -> None:
        """Register an adapter class.

        Args:
            name: Backend name (e.g., 'anytype', 'notion')
            adapter_class: Adapter class to register
        """
        cls._adapters[name] = adapter_class

    @classmethod
    def list_adapters(cls) -> list[str]:
        """List registered adapter names.

        Returns:
            List of backend names.
        """
        return list(cls._adapters.keys())

    @classmethod
    def get_adapter(cls, name: str | None = None) -> KnowledgeBaseAdapter:
        """Get a configured adapter instance.

        Args:
            name: Backend name. If None, uses active_backend from config.

        Returns:
            Configured adapter instance (singleton per backend).

        Raises:
            AdapterNotFoundError: If backend not registered
        """
        if name is None:
            config = get_config()
            name = config.active_backend

        if name not in cls._adapters:
            available = ", ".join(cls._adapters.keys())
            raise AdapterNotFoundError(
                f"Backend '{name}' not found. Available: {available}"
            )

        # Return existing instance or create new one
        if name not in cls._instances:
            adapter_class = cls._adapters[name]
            config = get_config()
            cls._instances[name] = adapter_class(config)

        return cls._instances[name]

    @classmethod
    def clear_instances(cls) -> None:
        """Clear all adapter instances (for testing)."""
        for adapter in cls._instances.values():
            if adapter.is_connected():
                adapter.disconnect()
        cls._instances.clear()


# Auto-register adapters on import
def _register_builtin_adapters() -> None:
    from .anytype import AnyTypeAdapter
    from .notion import NotionAdapter

    AdapterRegistry.register("anytype", AnyTypeAdapter)
    AdapterRegistry.register("notion", NotionAdapter)

_register_builtin_adapters()

# Convenience function
def get_adapter(name: str | None = None) -> KnowledgeBaseAdapter:
    """Get the configured adapter instance."""
    return AdapterRegistry.get_adapter(name)
```

### 4.3 Exception Hierarchy

```python
# src/jarvis/adapters/exceptions.py

class JarvisBackendError(Exception):
    """Base exception for all backend errors."""

    def __init__(self, message: str, backend: str | None = None):
        self.backend = backend
        super().__init__(message)

    def __str__(self) -> str:
        if self.backend:
            return f"[{self.backend}] {super().__str__()}"
        return super().__str__()


class ConnectionError(JarvisBackendError):
    """Cannot connect to backend."""
    pass


class AuthError(JarvisBackendError):
    """Authentication failed."""
    pass


class RateLimitError(JarvisBackendError):
    """Too many requests to backend."""

    def __init__(
        self,
        message: str,
        backend: str | None = None,
        retry_after: float | None = None
    ):
        super().__init__(message, backend)
        self.retry_after = retry_after


class NotFoundError(JarvisBackendError):
    """Resource not found."""

    def __init__(
        self,
        message: str,
        backend: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None
    ):
        super().__init__(message, backend)
        self.resource_type = resource_type
        self.resource_id = resource_id


class NotSupportedError(JarvisBackendError):
    """Operation not supported by this backend."""

    def __init__(
        self,
        message: str,
        backend: str | None = None,
        capability: str | None = None
    ):
        super().__init__(message, backend)
        self.capability = capability


class AdapterNotFoundError(JarvisBackendError):
    """Requested adapter not registered."""
    pass


class ConfigError(JarvisBackendError):
    """Configuration error."""
    pass
```

### 4.4 Retry Decorator

```python
# src/jarvis/adapters/retry.py
import time
import functools
from typing import TypeVar, Callable, ParamSpec
from .exceptions import RateLimitError, ConnectionError, AuthError

P = ParamSpec("P")
T = TypeVar("T")

def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator for retrying operations with exponential backoff.

    Retries on RateLimitError and ConnectionError.
    Fails immediately on AuthError.

    Args:
        max_attempts: Maximum number of attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff

    Returns:
        Decorated function with retry logic.
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception: Exception | None = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except AuthError:
                    # Don't retry auth errors
                    raise
                except RateLimitError as e:
                    last_exception = e
                    # Use retry_after if provided, otherwise calculate
                    delay = e.retry_after or min(
                        base_delay * (exponential_base ** attempt),
                        max_delay
                    )
                except ConnectionError as e:
                    last_exception = e
                    delay = min(
                        base_delay * (exponential_base ** attempt),
                        max_delay
                    )

                if attempt < max_attempts - 1:
                    time.sleep(delay)

            # All attempts failed
            raise last_exception or RuntimeError("Retry failed")

        return wrapper
    return decorator
```

---

## 5. Infrastructure & Deployment

### 5.1 Dependencies

**New dependencies to add to `pyproject.toml`:**

```toml
[project]
dependencies = [
    # Existing
    "anytype-client>=0.2.0",
    "anthropic>=0.40.0",
    "click>=8.1.0",
    "rich>=13.0.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "dateparser>=1.2.0",

    # NEW: Backend abstraction
    "notion-client>=2.2.0",  # Official-style Notion SDK
    "httpx>=0.27.0",         # Async HTTP client
    "pyyaml>=6.0.0",         # YAML config parsing
    "tenacity>=8.2.0",       # Advanced retry logic (optional)
]
```

### 5.2 Configuration File Location

| Platform | Config Directory | Config File |
|----------|------------------|-------------|
| macOS | `~/.jarvis/` | `~/.jarvis/config.yaml` |
| Linux | `~/.jarvis/` | `~/.jarvis/config.yaml` |
| Windows | `%USERPROFILE%\.jarvis\` | `%USERPROFILE%\.jarvis\config.yaml` |

**Directory Creation:**
```python
from pathlib import Path

def get_config_dir() -> Path:
    """Get the Jarvis configuration directory, creating if needed."""
    config_dir = Path.home() / ".jarvis"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir
```

### 5.3 Installation

No changes to installation process - remains a pip-installable package:

```bash
# From PyPI (future)
pip install jarvis-scheduler

# From source
pip install -e .

# With uv
uv pip install -e .
```

---

## 6. Security Architecture

### 6.1 Secrets Management

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Secret Resolution Flow                          │
└─────────────────────────────────────────────────────────────────────┘

Environment Variables (Source of Truth)
    │
    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  1. Check JARVIS_<BACKEND>_TOKEN (e.g., JARVIS_NOTION_TOKEN)        │
│  2. Check generic <BACKEND>_TOKEN (e.g., NOTION_TOKEN)              │
│  3. If neither found → ConfigError with helpful message             │
└─────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Token Storage Rules:                                               │
│  ✓ Environment variables ONLY                                       │
│  ✗ NEVER in config.yaml                                            │
│  ✗ NEVER in logs                                                   │
│  ✗ NEVER in error messages                                         │
└─────────────────────────────────────────────────────────────────────┘
```

### 6.2 Token Handling Implementation

```python
# src/jarvis/config/loader.py
import os
from .schema import JarvisConfig, ConfigError

def get_backend_token(backend: str) -> str:
    """Get API token for a backend from environment.

    Args:
        backend: Backend name (e.g., 'notion')

    Returns:
        API token string.

    Raises:
        ConfigError: If token not found.
    """
    # Try specific variable first
    specific_var = f"JARVIS_{backend.upper()}_TOKEN"
    token = os.environ.get(specific_var)

    if token:
        return token

    # Try generic variable
    generic_var = f"{backend.upper()}_TOKEN"
    token = os.environ.get(generic_var)

    if token:
        return token

    raise ConfigError(
        f"No API token found for {backend}. "
        f"Set {specific_var} or {generic_var} environment variable.",
        backend=backend
    )


def redact_token(token: str) -> str:
    """Redact a token for safe logging/display.

    Args:
        token: Full token string

    Returns:
        Redacted string showing only first 4 chars.

    Note:
        Always shows exactly 4 characters to prevent information
        leakage about token length or structure.
    """
    if len(token) <= 4:
        return "****"
    return f"{token[:4]}****"
```

### 6.3 Security Checklist

| Requirement | Implementation |
|-------------|----------------|
| Tokens in env vars only | `get_backend_token()` enforces this |
| No tokens in logs | All logging uses `redact_token()` |
| No tokens in errors | Exception handlers sanitize messages |
| HTTPS for API calls | `httpx` defaults to HTTPS; reject HTTP |
| Config file permissions | Warn if config readable by others |

### 6.4 Input Validation

All user input is validated at the service layer before reaching adapters.

| Field | Constraints | Validation |
|-------|-------------|------------|
| `title` | 1-500 characters, non-empty after trim | Pydantic `Field(min_length=1, max_length=500)` |
| `description` | 0-10000 characters | Pydantic `Field(max_length=10000)` |
| `content` | 0-100000 characters | Pydantic `Field(max_length=100000)` |
| `space_id` | Non-empty string | Validated against `list_spaces()` |
| `task_id` / `entry_id` | Non-empty string | Backend validates existence |
| `tags` | Max 50 tags, each 1-100 chars | Pydantic list validation |
| `priority` | Enum value | Priority enum enforces valid values |
| `dates` | Valid date objects | Python `date` type enforcement |

```python
# Example validation in Task model
class Task(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=10000)
    tags: list[str] = Field(
        default_factory=list,
        max_length=50,  # Max 50 tags
    )

    @field_validator("tags")
    @classmethod
    def validate_tag_lengths(cls, v: list[str]) -> list[str]:
        for tag in v:
            if len(tag) > 100:
                raise ValueError(f"Tag '{tag[:20]}...' exceeds 100 characters")
        return v
```

---

## 7. Integration Architecture

### 7.1 AnyType Adapter

**Refactoring Strategy:** Extract adapter interface from existing `AnyTypeClient`.

```python
# src/jarvis/adapters/anytype/adapter.py
from datetime import date, datetime
from typing import Any
from ...models import Task, JournalEntry, Space, Tag, Priority
from ..base import KnowledgeBaseAdapter
from ..exceptions import ConnectionError, NotFoundError
from ..retry import with_retry
from ...config import JarvisConfig

class AnyTypeAdapter(KnowledgeBaseAdapter):
    """Adapter for AnyType knowledge base.

    Uses gRPC to communicate with local AnyType desktop app.
    """

    def __init__(self, config: JarvisConfig):
        self._config = config
        self._client: Any = None
        self._authenticated = False
        self._default_space_id: str | None = config.backends.anytype.default_space_id

    @property
    def capabilities(self) -> dict[str, bool]:
        return {
            "tasks": True,
            "journal": True,
            "tags": True,
            "search": True,
            "priorities": True,
            "due_dates": True,
            "daily_notes": True,  # Via Journal hierarchy
            "relations": True,
            "custom_properties": True,
        }

    @property
    def backend_name(self) -> str:
        return "anytype"

    @with_retry(max_attempts=3, base_delay=1.0)
    def connect(self) -> None:
        """Connect to local AnyType instance."""
        try:
            from anytype import Anytype
        except ImportError:
            raise ConnectionError(
                "anytype-client package not installed. "
                "Run: pip install anytype-client",
                backend=self.backend_name
            )

        try:
            self._client = Anytype()
            self._client.auth()
            self._authenticated = True
        except Exception as e:
            raise ConnectionError(
                f"Could not connect to AnyType. Is the desktop app running? "
                f"(localhost:31009)",
                backend=self.backend_name
            ) from e

    def disconnect(self) -> None:
        self._client = None
        self._authenticated = False

    def is_connected(self) -> bool:
        return self._authenticated and self._client is not None

    def list_spaces(self) -> list[Space]:
        """List all AnyType spaces."""
        if not self.is_connected():
            raise ConnectionError("Not connected", backend=self.backend_name)

        spaces = self._client.get_spaces()
        return [
            Space(id=s.id, name=s.name, backend=self.backend_name)
            for s in spaces
        ]

    def get_task(self, space_id: str, task_id: str) -> Task:
        """Get a single task by ID from AnyType."""
        if not self.is_connected():
            raise ConnectionError("Not connected", backend=self.backend_name)

        try:
            space = self._client.get_space(space_id)
            obj = space.get_object(task_id)
            return self._object_to_task(obj, space_id)
        except Exception as e:
            if "not found" in str(e).lower():
                raise NotFoundError(
                    f"Task {task_id} not found",
                    backend=self.backend_name,
                    resource_type="task",
                    resource_id=task_id
                )
            raise

    def _object_to_task(self, obj: Any, space_id: str) -> Task:
        """Convert AnyType object to Task model."""
        return Task(
            id=obj.id,
            space_id=space_id,
            title=obj.name,
            description=getattr(obj, 'description', None),
            due_date=getattr(obj, 'due_date', None),
            priority=Priority.from_string(getattr(obj, 'priority', None)),
            tags=[t.name for t in getattr(obj, 'tags', [])],
            is_done=getattr(obj, 'done', False),
            created_at=obj.created_date,
            updated_at=obj.last_modified_date,
        )

    # ... remaining CRUD methods follow same pattern
```

### 7.2 Notion Adapter

**Implementation using notion-sdk-py:**

```python
# src/jarvis/adapters/notion/adapter.py
from datetime import date, datetime
from notion_client import Client
from notion_client.errors import APIResponseError
from ...models import Task, JournalEntry, Space, Tag, Priority
from ..base import KnowledgeBaseAdapter
from ..exceptions import (
    ConnectionError, AuthError, RateLimitError,
    NotFoundError, NotSupportedError
)
from ..retry import with_retry
from ...config import JarvisConfig, get_backend_token
from .mappings import (
    notion_to_task, task_to_notion_properties,
    notion_to_journal_entry, journal_to_notion_properties
)

class NotionAdapter(KnowledgeBaseAdapter):
    """Adapter for Notion knowledge base.

    Uses Notion API via notion-sdk-py.
    Requires:
    - JARVIS_NOTION_TOKEN environment variable
    - Configured database IDs in config.yaml
    """

    def __init__(self, config: JarvisConfig):
        self._config = config
        self._client: Client | None = None
        self._connected = False

    @property
    def capabilities(self) -> dict[str, bool]:
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
        return "notion"

    # Pin Notion API version for stability
    NOTION_API_VERSION = "2022-06-28"

    def connect(self) -> None:
        """Connect to Notion API."""
        try:
            token = get_backend_token("notion")
        except Exception as e:
            raise AuthError(
                str(e),
                backend=self.backend_name
            )

        try:
            self._client = Client(
                auth=token,
                notion_version=self.NOTION_API_VERSION
            )
            # Verify connection by fetching user info
            self._client.users.me()
            self._connected = True
        except APIResponseError as e:
            if e.status == 401:
                raise AuthError(
                    "Invalid Notion token. Generate a new one at: "
                    "https://www.notion.so/my-integrations",
                    backend=self.backend_name
                )
            raise ConnectionError(
                f"Failed to connect to Notion: {e.message}",
                backend=self.backend_name
            ) from e

    def disconnect(self) -> None:
        self._client = None
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected and self._client is not None

    def list_spaces(self) -> list[Space]:
        """Notion doesn't have spaces - return workspace as single space."""
        if not self._connected or not self._config.backends.notion:
            raise ConnectionError("Not connected", backend=self.backend_name)

        return [Space(
            id=self._config.backends.notion.workspace_id,
            name="Notion Workspace",
            backend=self.backend_name
        )]

    def get_default_space(self) -> str:
        if not self._config.backends.notion:
            raise NotFoundError(
                "Notion not configured",
                backend=self.backend_name
            )
        return self._config.backends.notion.workspace_id

    def set_default_space(self, space_id: str) -> None:
        # Notion only has one workspace per integration
        pass

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
        """Create a task in Notion Tasks database."""
        if not self._client or not self._config.backends.notion:
            raise ConnectionError("Not connected", backend=self.backend_name)

        database_id = self._config.backends.notion.task_database_id
        properties = task_to_notion_properties(
            title=title,
            due_date=due_date,
            priority=priority,
            tags=tags,
            mappings=self._config.backends.notion.property_mappings
        )

        try:
            # Create page in database
            children = []
            if description:
                children.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": description}}]
                    }
                })

            response = self._client.pages.create(
                parent={"database_id": database_id},
                properties=properties,
                children=children if children else None
            )

            return notion_to_task(response, space_id)

        except APIResponseError as e:
            self._handle_api_error(e)

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
        """Query tasks from Notion database."""
        if not self._client or not self._config.backends.notion:
            raise ConnectionError("Not connected", backend=self.backend_name)

        database_id = self._config.backends.notion.task_database_id
        mappings = self._config.backends.notion.property_mappings

        # Build filter
        filters = []

        if not include_done:
            filters.append({
                "property": mappings.get("done", "Done"),
                "checkbox": {"equals": False}
            })

        if start_date:
            filters.append({
                "property": mappings.get("due_date", "Due Date"),
                "date": {"on_or_after": start_date.isoformat()}
            })

        if end_date:
            filters.append({
                "property": mappings.get("due_date", "Due Date"),
                "date": {"on_or_before": end_date.isoformat()}
            })

        filter_obj = None
        if filters:
            filter_obj = {"and": filters} if len(filters) > 1 else filters[0]

        try:
            tasks = []
            has_more = True
            start_cursor = None
            skipped = 0

            while has_more:
                response = self._client.databases.query(
                    database_id=database_id,
                    filter=filter_obj,
                    start_cursor=start_cursor,
                    page_size=min(100, (limit or 100) + offset - len(tasks))
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

    def _handle_api_error(self, error: APIResponseError) -> None:
        """Convert Notion API errors to typed exceptions."""
        if error.status == 401:
            raise AuthError(
                "Notion authentication failed",
                backend=self.backend_name
            )
        elif error.status == 404:
            raise NotFoundError(
                error.message,
                backend=self.backend_name
            )
        elif error.status == 429:
            retry_after = error.headers.get("Retry-After")
            raise RateLimitError(
                "Notion rate limit exceeded",
                backend=self.backend_name,
                retry_after=float(retry_after) if retry_after else None
            )
        else:
            raise ConnectionError(
                f"Notion API error: {error.message}",
                backend=self.backend_name
            )

    # ... remaining CRUD methods follow same pattern
```

### 7.3 Notion Property Mappings

```python
# src/jarvis/adapters/notion/mappings.py
from datetime import date, datetime
from ...models import Task, JournalEntry, Priority

def notion_to_task(page: dict, space_id: str) -> Task:
    """Convert Notion page to Task model."""
    props = page["properties"]

    # Extract title
    title_prop = props.get("Name", props.get("Title", {}))
    title = ""
    if title_prop.get("title"):
        title = "".join(t["plain_text"] for t in title_prop["title"])

    # Extract due date
    due_date = None
    due_prop = props.get("Due Date", props.get("Due", {}))
    if due_prop.get("date") and due_prop["date"].get("start"):
        due_date = date.fromisoformat(due_prop["date"]["start"][:10])

    # Extract priority
    priority = None
    priority_prop = props.get("Priority", {})
    if priority_prop.get("select"):
        priority = Priority.from_string(priority_prop["select"]["name"])

    # Extract tags
    tags = []
    tags_prop = props.get("Tags", {})
    if tags_prop.get("multi_select"):
        tags = [t["name"] for t in tags_prop["multi_select"]]

    # Extract done status
    is_done = False
    done_prop = props.get("Done", props.get("Status", {}))
    if done_prop.get("checkbox") is not None:
        is_done = done_prop["checkbox"]

    # Parse timestamps
    created_at = datetime.fromisoformat(
        page["created_time"].replace("Z", "+00:00")
    )
    updated_at = datetime.fromisoformat(
        page["last_edited_time"].replace("Z", "+00:00")
    )

    return Task(
        id=page["id"],
        space_id=space_id,
        title=title,
        due_date=due_date,
        priority=priority,
        tags=tags,
        is_done=is_done,
        created_at=created_at,
        updated_at=updated_at,
    )


def task_to_notion_properties(
    title: str,
    due_date: date | None = None,
    priority: Priority | None = None,
    tags: list[str] | None = None,
    mappings: dict[str, str] | None = None,
) -> dict:
    """Convert Task fields to Notion page properties."""
    mappings = mappings or {}

    properties = {
        "Name": {
            "title": [{"text": {"content": title}}]
        }
    }

    if due_date:
        properties[mappings.get("due_date", "Due Date")] = {
            "date": {"start": due_date.isoformat()}
        }

    if priority:
        properties[mappings.get("priority", "Priority")] = {
            "select": {"name": priority.value.capitalize()}
        }

    if tags:
        properties[mappings.get("tags", "Tags")] = {
            "multi_select": [{"name": tag} for tag in tags]
        }

    return properties
```

---

## 8. Performance & Scalability

### 8.1 Performance Requirements

| Operation | Local Backend (AnyType) | API Backend (Notion) |
|-----------|------------------------|----------------------|
| Single task CRUD | < 500ms | < 2s |
| List tasks (100) | < 1s | < 3s |
| Journal entry create | < 500ms | < 2s |
| Search (full-text) | < 1s | < 3s |
| Backend switch | < 100ms | < 100ms |

### 8.2 Optimization Strategies

**Connection Pooling:**
```python
# Notion adapter uses singleton client
# AnyType adapter maintains single gRPC connection
```

**Pagination:**
```python
# All list operations support limit/offset
# Default page size: 100 for Notion (API max)
# Cursor-based pagination used internally
```

**Lazy Loading:**
```python
# Adapters connect on first use, not on import
# Configuration loaded once and cached
```

### 8.3 Rate Limiting

| Backend | Rate Limit | Strategy |
|---------|------------|----------|
| AnyType | None (local) | N/A |
| Notion | Request-based (returns 429) | Exponential backoff with `Retry-After` header |

```python
# Notion rate limit handling
# The API returns 429 with optional Retry-After header
# Our retry decorator respects this header when present
@with_retry(max_attempts=5, base_delay=0.5, max_delay=60.0)
def _notion_request(self, method: str, **kwargs):
    # Retry decorator handles RateLimitError automatically
    ...
```

---

## 9. Reliability & Operations

### 9.1 Error Handling Strategy

```
User Action → CLI → Service → Adapter → Backend
                 ↑               ↑
                 │               └─ Typed exceptions (ConnectionError, etc.)
                 └─ User-friendly error messages
```

**Error Message Format:**
```
✗ [Error Type]

[Explanation of what went wrong]

Possible causes:
  • [Cause 1]
  • [Cause 2]

Try: [Actionable suggestion]
```

### 9.2 Health Check

```python
# src/jarvis/adapters/health.py
from dataclasses import dataclass
from .base import KnowledgeBaseAdapter

@dataclass
class HealthStatus:
    backend: str
    connected: bool
    latency_ms: float | None
    error: str | None
    capabilities: dict[str, bool]

def check_health(adapter: KnowledgeBaseAdapter) -> HealthStatus:
    """Perform health check on adapter."""
    import time

    try:
        start = time.monotonic()

        if not adapter.is_connected():
            adapter.connect()

        # Test basic operation
        adapter.list_spaces()

        latency = (time.monotonic() - start) * 1000

        return HealthStatus(
            backend=adapter.backend_name,
            connected=True,
            latency_ms=latency,
            error=None,
            capabilities=adapter.capabilities
        )

    except Exception as e:
        return HealthStatus(
            backend=adapter.backend_name,
            connected=False,
            latency_ms=None,
            error=str(e),
            capabilities=adapter.capabilities
        )
```

### 9.3 Logging

```python
# Structured logging with redacted secrets
import logging

logger = logging.getLogger("jarvis.adapters")

# Log successful operations at DEBUG
logger.debug("Created task", extra={
    "backend": "notion",
    "task_id": task.id,
    "space_id": space_id,
})

# Log errors at ERROR with context
logger.error("Failed to create task", extra={
    "backend": "notion",
    "error_type": type(e).__name__,
    # Never log tokens!
})
```

---

## 10. Development Standards

### 10.1 Code Style

- **Formatter:** ruff format
- **Linter:** ruff check
- **Type checker:** mypy (strict mode)
- **Line length:** 100 characters
- **Docstrings:** Google style

### 10.2 Testing Requirements

| Test Type | Location | Coverage Target |
|-----------|----------|-----------------|
| Unit tests | `tests/unit/adapters/` | 90% |
| Integration tests | `tests/integration/` | Key workflows |
| Mock tests | `tests/unit/` | Protocol compliance |

**Test Fixtures:**

```python
# tests/conftest.py
import pytest
from jarvis.adapters import AdapterRegistry
from jarvis.config import JarvisConfig

@pytest.fixture
def mock_config():
    """Provide test configuration."""
    return JarvisConfig(
        active_backend="anytype",
        backends=BackendsConfig()
    )

@pytest.fixture
def anytype_adapter(mock_config):
    """Provide AnyType adapter for testing."""
    from jarvis.adapters.anytype import AnyTypeAdapter
    adapter = AnyTypeAdapter(mock_config)
    yield adapter
    if adapter.is_connected():
        adapter.disconnect()

@pytest.fixture(autouse=True)
def clear_registry():
    """Clear adapter instances between tests."""
    yield
    AdapterRegistry.clear_instances()
```

### 10.3 Documentation Requirements

- All public classes and methods have docstrings
- Protocol methods include full parameter and return documentation
- Examples in README for common operations
- Architecture diagrams in technical spec

---

## 11. Implementation Roadmap

### 11.1 Work Items

| ID | Item | Priority | Dependencies | Estimate |
|----|------|----------|--------------|----------|
| WI-01 | Create `models/` package with domain models | P0 | None | 2h |
| WI-02 | Create `config/` package with Pydantic schemas | P0 | None | 3h |
| WI-03 | Create `adapters/base.py` with Protocol | P0 | WI-01 | 2h |
| WI-04 | Create `adapters/exceptions.py` | P0 | None | 1h |
| WI-05 | Create `adapters/retry.py` decorator | P0 | WI-04 | 1h |
| WI-06 | Create AdapterRegistry in `adapters/__init__.py` | P0 | WI-03, WI-02 | 2h |
| WI-07 | Refactor AnyTypeClient → AnyTypeAdapter | P0 | WI-03, WI-06 | 4h |
| WI-08 | Create NotionAdapter | P0 | WI-03, WI-06 | 6h |
| WI-09 | Create Notion property mappings | P0 | WI-08 | 2h |
| WI-10 | Update CLI to use adapters | P0 | WI-06, WI-07 | 3h |
| WI-11 | Add `jarvis config` commands | P1 | WI-02, WI-10 | 3h |
| WI-12 | Add `jarvis status` command | P1 | WI-06, WI-10 | 2h |
| WI-13 | Add capability-based command filtering | P1 | WI-10 | 2h |
| WI-14 | Unit tests for adapters | P0 | WI-07, WI-08 | 4h |
| WI-15 | Integration tests with real backends | P1 | WI-14 | 4h |
| WI-16 | Documentation updates | P2 | All | 2h |

### 11.2 Implementation Phases

```
Phase 1: Foundation (WI-01 to WI-06)
├── Domain models
├── Configuration system
├── Adapter protocol
├── Exception hierarchy
├── Retry logic
└── Registry

Phase 2: AnyType Migration (WI-07)
└── Refactor existing code into adapter

Phase 3: Notion Integration (WI-08, WI-09)
├── NotionAdapter implementation
└── Property mappings

Phase 4: CLI Integration (WI-10 to WI-13)
├── Update CLI commands
├── Config management commands
├── Status display
└── Capability filtering

Phase 5: Testing & Polish (WI-14 to WI-16)
├── Unit tests
├── Integration tests
└── Documentation
```

### 11.3 Milestone Checklist

**Milestone 1: Adapter Architecture ✓**
- [ ] Domain models defined and tested
- [ ] Configuration system working
- [ ] Protocol defined
- [ ] Registry functional
- [ ] Exceptions and retry implemented

**Milestone 2: AnyType Refactor ✓**
- [ ] AnyTypeAdapter implements full protocol
- [ ] All existing tests pass
- [ ] No user-facing changes

**Milestone 3: Notion Adapter ✓**
- [ ] NotionAdapter implements full protocol
- [ ] Task CRUD working
- [ ] Journal CRUD working
- [ ] Integration tests passing

**Milestone 4: CLI Integration ✓**
- [ ] All commands use adapter
- [ ] `jarvis config` commands working
- [ ] `jarvis status` shows backend info
- [ ] Capability-aware help text

---

## 12. Appendices

### Appendix A: Notion Setup Guide

#### A.1 Integration Token Setup

1. Go to [Notion Integrations](https://www.notion.so/my-integrations)
2. Click "New integration"
3. Name it "Jarvis" (or your preferred name)
4. Select the workspace to connect
5. **Required Capabilities:**
   - Read content
   - Update content
   - Insert content
6. Copy the "Internal Integration Token" (starts with `secret_`)
7. Set environment variable: `export JARVIS_NOTION_TOKEN=secret_...`

**Important:** After creating the integration, you must share each database with it:
1. Open your Tasks/Journal database
2. Click "..." menu → "Add connections"
3. Select your Jarvis integration

#### A.2 Database Schema

For Notion adapter to work, users need to create databases with specific properties:

**Tasks Database:**
| Property | Type | Required |
|----------|------|----------|
| Name | Title | Yes |
| Due Date | Date | No |
| Priority | Select (High/Medium/Low) | No |
| Tags | Multi-select | No |
| Done | Checkbox | No |

**Journal Database:**
| Property | Type | Required |
|----------|------|----------|
| Name | Title | Yes |
| Date | Date | No |
| Tags | Multi-select | No |

### Appendix B: Migration Guide from AnyTypeClient

**Before (direct client usage):**
```python
from jarvis.anytype_client import AnyTypeClient

client = AnyTypeClient()
client.connect()
space_id = client.get_default_space()
tasks = client.get_tasks_in_range(space_id, start, end)
```

**After (adapter pattern):**
```python
from jarvis.adapters import get_adapter

adapter = get_adapter()  # Uses configured backend
adapter.connect()
space_id = adapter.get_default_space()
tasks = adapter.get_tasks(space_id, start_date=start, end_date=end)
```

### Appendix C: Adding a New Adapter

1. Create package: `src/jarvis/adapters/<name>/`
2. Implement `KnowledgeBaseAdapter` protocol in `adapter.py`
3. Register in `adapters/__init__.py`
4. Add config schema in `config/schema.py`
5. Add tests in `tests/unit/adapters/test_<name>.py`
6. Update documentation

### Appendix D: Design Decisions

The following design decisions were made intentionally during specification:

| Decision | Rationale |
|----------|-----------|
| `delete_task` returns `bool` not `Task` | Deleted resources shouldn't be returned; bool indicates success |
| `update_journal_entry` cannot change `entry_date` | Journal dates are semantic (the day of the entry) and should be immutable |
| `Task.tags` uses names not IDs | Tag IDs are backend-specific; names provide cross-backend consistency |
| No caching layer | CLI tool with short-lived sessions; caching adds complexity without benefit |
| Singleton adapter instances | Prevents multiple connections; adapter lifecycle tied to registry |
| `JournalEntry.path` is optional | Only meaningful for hierarchical backends (AnyType); others return None |

### Appendix E: References

- [Notion API Documentation](https://developers.notion.com/)
- [notion-sdk-py GitHub](https://github.com/ramnes/notion-sdk-py)
- [AnyType Client](https://github.com/anytype/anytype-client)
- [Python Protocols (PEP 544)](https://peps.python.org/pep-0544/)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)

---

*Generated from product_spec.md on 2025-01-25*
*Reviewed: 2025-01-25 (6-perspective technical review)*
