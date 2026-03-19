# Brainstorm: Backend Abstraction Layer

> **Epic:** 04_backend-abstraction
> **Created:** 2025-01-25
> **Status:** Ready for PRD

---

## 1. Core Idea

**One-sentence summary:**
Transform Jarvis from an AnyType-specific CLI into a universal AI assistant that works with any knowledge base through a pluggable adapter architecture.

**Problem being solved:**
Jarvis is currently tightly coupled to AnyType, limiting its usefulness to AnyType users only and creating risk if AnyType changes or the user wants to switch tools.

**Opportunity:**
By abstracting the backend, Jarvis becomes:
- A personal tool that adapts to YOUR preferred knowledge base
- An open source project others can use with their tools
- Future-proof against changes in any single platform

---

## 2. Target Audience

| Audience | Needs |
|----------|-------|
| **Primary: Julian (creator)** | Flexibility to switch backends, test alternatives |
| **Secondary: Open source users** | Use Jarvis with Notion, Obsidian, Logseq, etc. |
| **Tertiary: Contributors** | Clear interface to implement new adapters |

---

## 3. Vision & Inspiration

**North Star:**
Like Iron Man's JARVIS - a personal AI assistant that integrates seamlessly with whatever systems you use, not locked to any single vendor.

**What this should feel like:**
- Switching backends is as easy as changing a config line
- The CLI experience is identical regardless of backend
- Adding a new backend is straightforward for contributors

**What this should NOT be:**
- A lowest-common-denominator tool that sacrifices features
- Complicated to configure or maintain
- A leaky abstraction where backend quirks bleed through

---

## 4. Core Concepts (Domain Model)

These abstractions must work across all backends:

| Concept | Description | Backend Mappings |
|---------|-------------|------------------|
| **Space** | Top-level container/workspace | AnyType Space, Notion Workspace, Obsidian Vault, Logseq Graph, Linear Team |
| **Task** | Actionable item with optional due date, priority, tags | AnyType Task, Notion DB row, Obsidian task checkbox, Linear Issue |
| **Journal Entry** | Timestamped freeform text | AnyType Page in Journal, Notion page, Obsidian daily note |
| **Tag** | Categorization label | Native tags across all systems |
| **Page/Note** | General content container | Native page/note in each system |

---

## 5. Architecture Decisions

### 5.1 Feature Parity Strategy

**Decision:** Capability Detection

Adapters declare what they support:
```python
class NotionAdapter(KnowledgeBaseAdapter):
    capabilities = {
        "tasks": True,
        "journal": True,
        "tags": True,
        "relations": True,
        "custom_properties": True,
        "daily_notes": False,  # Must be manually created
    }
```

Jarvis adapts behavior based on declared capabilities - disabling/hiding features that aren't supported by the active backend.

### 5.2 Configuration Strategy

**Decision:** Hybrid (env vars + config file)

**Secrets** via environment variables:
```bash
JARVIS_NOTION_TOKEN=secret_xxx
JARVIS_LINEAR_API_KEY=lin_api_xxx
```

**Settings** via config file (`~/.jarvis/config.yaml`):
```yaml
active_backend: notion

backends:
  notion:
    workspace_id: "abc123"
    task_database_id: "def456"
    journal_database_id: "ghi789"

  obsidian:
    vault_path: "~/Documents/MyVault"
    tasks_folder: "Tasks"
    journal_folder: "Journal"

  anytype:
    # Uses local gRPC, minimal config needed
```

### 5.3 Interface Design

**Decision:** Sync interface, async internals optional

- Adapter public methods are synchronous (simple CLI usage)
- Adapters can use async internally for HTTP-based backends
- Keeps CLI code simple: `jarvis t "task"` just works

### 5.4 Error Handling

**Decision:** Centralized retry with typed exceptions

```python
# Exception hierarchy
class JarvisBackendError(Exception): pass
class ConnectionError(JarvisBackendError): pass
class AuthError(JarvisBackendError): pass
class RateLimitError(JarvisBackendError): pass
class NotFoundError(JarvisBackendError): pass
class NotSupportedError(JarvisBackendError): pass
```

- Base class provides retry decorator (exponential backoff)
- Adapters map backend-specific errors to typed exceptions
- CLI gets consistent error messages

---

## 6. Adapter Interface (Draft)

```python
from typing import Protocol
from datetime import date

class KnowledgeBaseAdapter(Protocol):
    """Interface that all backend adapters must implement."""

    # Capability declaration
    capabilities: dict[str, bool]

    # Connection
    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def is_connected(self) -> bool: ...

    # Spaces
    def list_spaces(self) -> list[Space]: ...
    def get_default_space(self) -> str: ...
    def set_default_space(self, space_id: str) -> None: ...

    # Tasks
    def create_task(
        self,
        space_id: str,
        title: str,
        due_date: date | None = None,
        priority: str | None = None,
        tags: list[str] | None = None,
        description: str | None = None,
    ) -> str: ...

    def get_tasks(
        self,
        space_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
        include_done: bool = False,
    ) -> list[Task]: ...

    def update_task(self, space_id: str, task_id: str, **updates) -> bool: ...
    def delete_task(self, space_id: str, task_id: str) -> bool: ...

    # Journal
    def create_journal_entry(
        self,
        space_id: str,
        content: str,
        title: str | None = None,
        entry_date: date | None = None,
    ) -> str: ...

    def get_journal_entries(
        self,
        space_id: str,
        limit: int = 10,
        offset: int = 0,
    ) -> list[JournalEntry]: ...

    def search_journal(
        self,
        space_id: str,
        query: str,
    ) -> list[JournalEntry]: ...

    # Tags
    def list_tags(self, space_id: str) -> list[Tag]: ...
    def create_tag(self, space_id: str, name: str) -> str: ...
```

---

## 7. Target Backends

### Phase 1 (This Epic)
1. **AnyType** - Refactor existing `AnyTypeClient` into `AnyTypeAdapter`
2. **Notion** - First external adapter to validate architecture

### Phase 2+ (Future Epics)
3. Obsidian - Local markdown vault
4. Logseq - Outliner/graph
5. Linear - Issue tracking
6. Jira - Enterprise issue tracking
7. Todoist - Simple task management
8. Markdown - Plain files (universal fallback)

---

## 8. Success Criteria

| Criterion | Measurement |
|-----------|-------------|
| **Backend-agnostic CLI** | `jarvis t "task"` works with any configured backend |
| **Easy switching** | Change `active_backend` in config, everything works |
| **Clear adapter contract** | New adapter implementable from interface + docs |
| **No regression** | All existing AnyType functionality preserved |
| **Tested** | Adapter interface has integration tests with mocked backends |

---

## 9. Out of Scope (This Epic)

- Syncing between backends
- Migrating data from one backend to another
- Backend-specific features beyond core abstractions
- GUI/web interface for configuration
- Implementing all backends (only AnyType + Notion in Phase 1)

---

## 10. Open Questions

1. **Should adapters be plugins?** - Loadable at runtime vs. compiled in?
2. **How to handle backend-specific IDs?** - Notion uses UUIDs, AnyType has its own format
3. **Caching strategy?** - Should adapters cache to reduce API calls?
4. **Offline support?** - Queue operations when backend unavailable?

These can be resolved during technical specification.

---

## 11. References

- [Jarvis Roadmap](../../context/roadmap.md) - Phase 1 definition
- [Current AnyTypeClient](../../src/jarvis/anytype_client.py) - Code to refactor
- [Notion API Docs](https://developers.notion.com/) - Target integration

---

*Brainstormed with Claude on 2025-01-25*
