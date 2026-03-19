# Product Specification: Backend Abstraction Layer

> **Epic:** 04_backend-abstraction
> **Version:** 1.1
> **Created:** 2025-01-25
> **Status:** Reviewed

---

## 1. Executive Summary

### Product Name
Jarvis Backend Abstraction Layer

### Vision Statement
Transform Jarvis from an AnyType-specific CLI tool into a universal AI assistant that seamlessly integrates with any knowledge base, enabling users to work with their preferred tools while maintaining a consistent, powerful experience.

### One-Liner
A pluggable adapter architecture that lets Jarvis connect to AnyType, Notion, Obsidian, and beyond—same commands, any backend.

### Problem Statement
Jarvis is currently tightly coupled to AnyType, creating three critical limitations:
1. **User Lock-in:** Only AnyType users can benefit from Jarvis
2. **Adoption Barrier:** Potential users on Notion, Obsidian, etc. cannot use Jarvis
3. **Platform Risk:** Changes to AnyType could break Jarvis entirely

### Proposed Solution
Introduce a `KnowledgeBaseAdapter` protocol that abstracts all backend operations. The existing AnyType integration becomes one adapter among many, and new backends can be added by implementing the same interface.

### Target Release
Q1 2025 (Phase 1: AnyType refactor + Notion adapter)

---

## 2. Goals and Objectives

### Primary Goals

| Goal | Description | Success Metric |
|------|-------------|----------------|
| **Backend Independence** | CLI works identically regardless of configured backend | All existing commands work with both AnyType and Notion |
| **Easy Configuration** | Switching backends requires only a config change | Backend switch takes < 1 minute |
| **Extensibility** | New adapters can be added without core changes | Contributor can implement adapter from docs alone |
| **Zero Regression** | Existing AnyType users see no degradation | All existing tests pass |

### Secondary Goals

| Goal | Description |
|------|-------------|
| **Clean Architecture** | Clear separation between core logic and backend specifics |
| **Developer Experience** | Well-documented adapter interface with examples |
| **Graceful Degradation** | Features unavailable on a backend are clearly communicated |

### Non-Goals (Out of Scope)

- Cross-backend synchronization
- Data migration tools between backends
- Backend-specific features beyond core abstractions
- GUI/web configuration interface
- Implementing all planned backends (only AnyType + Notion in Phase 1)

---

## 3. User Personas

### Persona 1: Julian (Power User / Creator)

**Background:** Software engineer who uses Jarvis daily for task management and journaling.

**Goals:**
- Flexibility to experiment with different knowledge bases
- Confidence that switching tools won't lose Jarvis functionality
- Maintain current productivity workflows

**Pain Points:**
- Currently locked into AnyType for Jarvis features
- Cannot recommend Jarvis to colleagues using other tools

**Scenario:**
> "I've been curious about Notion for team collaboration. With backend abstraction, I can try Notion for a week without losing my Jarvis workflow. If I don't like it, I switch back with one config change."

---

### Persona 2: Alex (Open Source Adopter)

**Background:** Developer who discovered Jarvis on GitHub, uses Obsidian for personal knowledge management.

**Goals:**
- Use Jarvis's AI-powered scheduling with existing Obsidian vault
- Contribute improvements back to the project
- Avoid duplicating task data across tools

**Pain Points:**
- Current Jarvis requires AnyType which they don't use
- No clear path to add Obsidian support themselves

**Scenario:**
> "I found Jarvis and love the concept, but I'm not switching from Obsidian. With the adapter architecture, I can either wait for an Obsidian adapter or build one myself following the documented interface."

---

### Persona 3: Sam (Contributor)

**Background:** Developer interested in adding Linear support for work task management.

**Goals:**
- Implement a Linear adapter for their team
- Follow clear patterns and documentation
- Minimize learning curve

**Pain Points:**
- Unclear how to extend Jarvis
- No adapter examples to follow

**Scenario:**
> "My team uses Linear for issue tracking. I want to use Jarvis to manage my Linear tasks. The adapter documentation and Notion adapter example make it clear exactly what I need to implement."

---

## 4. User Stories and Requirements

### Epic: Backend Abstraction Layer

#### US-01: Configure Active Backend
**As a** user
**I want to** specify which backend Jarvis should use
**So that** I can work with my preferred knowledge base

**Acceptance Criteria:**
- [ ] Config file at `~/.jarvis/config.yaml` specifies `active_backend`
- [ ] Changing `active_backend` switches all operations to that backend
- [ ] Invalid backend name shows helpful error message listing valid options
- [ ] `jarvis config show` displays current backend configuration
- [ ] If config file missing, create with sensible defaults
- [ ] If config file malformed, show parse error with line number

**Priority:** P0 (Must Have)

---

#### US-02: AnyType Adapter (Refactor)
**As a** current AnyType user
**I want** existing functionality to work unchanged
**So that** the abstraction doesn't break my workflow

**Acceptance Criteria:**
- [ ] All existing CLI commands work with AnyType adapter
- [ ] No changes required to user's AnyType setup
- [ ] Performance is equivalent to current implementation (baseline: current test suite timing)
- [ ] All existing tests pass
- [ ] Connection failures show helpful message ("Is AnyType running?")
- [ ] Graceful handling if AnyType closes mid-operation

**Priority:** P0 (Must Have)

---

#### US-03: Notion Adapter
**As a** Notion user
**I want to** use Jarvis with my Notion workspace
**So that** I can benefit from AI-powered task management

**Acceptance Criteria:**
- [ ] Can connect to Notion via API token
- [ ] Tasks map to Notion database rows
- [ ] Journal entries create pages in designated database
- [ ] Tags map to Notion multi-select properties
- [ ] Space maps to Notion workspace
- [ ] Rate limit errors trigger automatic retry with backoff
- [ ] Invalid token shows clear message with regeneration instructions
- [ ] Network timeout (>30s) shows actionable error

**Priority:** P0 (Must Have)

---

#### US-04: Capability Detection
**As a** user
**I want** Jarvis to know what my backend supports
**So that** I get clear feedback when a feature isn't available

**Acceptance Criteria:**
- [ ] Each adapter declares its capabilities
- [ ] Unsupported commands show "Not supported by [backend]" message
- [ ] `jarvis config capabilities` lists what current backend supports
- [ ] Help text adapts to show only supported commands

**Priority:** P1 (Should Have)

---

#### US-05: Backend-Specific Configuration
**As a** user
**I want to** configure backend-specific settings
**So that** each backend works optimally

**Acceptance Criteria:**
- [ ] Notion: workspace_id, task_database_id, journal_database_id
- [ ] AnyType: (minimal, uses defaults)
- [ ] Secrets stored in environment variables, not config file
- [ ] Config validation on startup with clear error messages
- [ ] Missing required config fields show which fields are needed
- [ ] Environment variable priority: specific > general (e.g., `JARVIS_NOTION_TOKEN` > `NOTION_TOKEN`)

**Priority:** P1 (Should Have)

---

#### US-06: Connection Status
**As a** user
**I want to** see if Jarvis can connect to my backend
**So that** I can troubleshoot connection issues

**Acceptance Criteria:**
- [ ] `jarvis status` shows connection state
- [ ] Clear error messages for common failures (auth, network, not running)
- [ ] Retry logic for transient failures
- [ ] Timeout handling for unresponsive backends

**Priority:** P1 (Should Have)

---

#### US-07: Adapter Documentation
**As a** contributor
**I want** clear documentation for implementing adapters
**So that** I can add support for new backends

**Acceptance Criteria:**
- [ ] README section on adapter architecture
- [ ] KnowledgeBaseAdapter protocol fully documented
- [ ] Example adapter (Notion) to follow
- [ ] Testing guide for new adapters

**Priority:** P2 (Nice to Have)

---

## 5. Functional Requirements

### FR-01: Adapter Protocol

The system SHALL define a `KnowledgeBaseAdapter` protocol with the following method groups:

**Connection Management:**
| Method | Description |
|--------|-------------|
| `connect()` | Establish connection to backend |
| `disconnect()` | Close connection cleanly |
| `is_connected()` | Return connection status |

**Space Operations:**
| Method | Description |
|--------|-------------|
| `list_spaces()` | Return all available spaces/workspaces |
| `get_default_space()` | Return currently selected space ID |
| `set_default_space(space_id)` | Set the active space |

**Task Operations:**
| Method | Description |
|--------|-------------|
| `create_task(space_id, title, due_date?, priority?, tags?, description?)` | Create new task |
| `get_task(space_id, task_id)` | Get single task by ID |
| `get_tasks(space_id, start_date?, end_date?, include_done?, limit?, offset?)` | Query tasks with optional pagination |
| `update_task(space_id, task_id, title?, due_date?, priority?, tags?, description?, is_done?)` | Modify task fields (all optional) |
| `delete_task(space_id, task_id)` | Remove task |

**Journal Operations:**
| Method | Description |
|--------|-------------|
| `create_journal_entry(space_id, content, title?, entry_date?)` | Create entry |
| `get_journal_entry(space_id, entry_id)` | Get single entry by ID |
| `get_journal_entries(space_id, limit?, offset?)` | List entries with pagination |
| `update_journal_entry(space_id, entry_id, content?, title?)` | Modify entry |
| `delete_journal_entry(space_id, entry_id)` | Remove entry |
| `search_journal(space_id, query)` | Full-text search |

**Tag Operations:**
| Method | Description |
|--------|-------------|
| `list_tags(space_id)` | Get all tags |
| `create_tag(space_id, name)` | Create new tag |

---

### FR-02: Capability Declaration

Each adapter SHALL declare its capabilities via a dictionary:

```python
capabilities = {
    "tasks": bool,           # Task CRUD operations
    "journal": bool,         # Journal entry operations
    "tags": bool,            # Tag management
    "search": bool,          # Full-text search
    "priorities": bool,      # Task priority levels
    "due_dates": bool,       # Task due dates
    "daily_notes": bool,     # Automatic daily note creation
    "relations": bool,       # Links between items
    "custom_properties": bool,  # User-defined fields
}
```

The CLI SHALL check capabilities before invoking adapter methods and provide clear feedback when a capability is unavailable.

---

### FR-03: Configuration Management

**Config File Location:** `~/.jarvis/config.yaml`

**Required Fields:**
- `active_backend`: String identifying which adapter to use

**Backend-Specific Sections:**
- `backends.<name>`: Settings specific to each backend

**Environment Variables:**
- `JARVIS_<BACKEND>_<SECRET>`: Pattern for secrets (e.g., `JARVIS_NOTION_TOKEN`)

---

### FR-04: Error Handling

The system SHALL define typed exceptions:

| Exception | When Raised |
|-----------|-------------|
| `ConnectionError` | Cannot reach backend |
| `AuthError` | Invalid or expired credentials |
| `RateLimitError` | Too many requests |
| `NotFoundError` | Requested resource doesn't exist |
| `NotSupportedError` | Operation not supported by backend |

The base adapter class SHALL provide:
- Automatic retry with exponential backoff for `RateLimitError` and `ConnectionError`
- Immediate failure for `AuthError`
- Consistent error message formatting for CLI display

---

### FR-05: Domain Model Mapping

Each adapter SHALL map backend-specific concepts to Jarvis domain models:

**Priority Enum:**
```python
class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
```

**Task:**
```python
@dataclass
class Task:
    id: str
    space_id: str
    title: str
    due_date: date | None
    priority: Priority | None
    tags: list[str]
    is_done: bool
    created_at: datetime
    updated_at: datetime
```

**JournalEntry:**
```python
@dataclass
class JournalEntry:
    id: str
    space_id: str
    title: str
    content: str
    entry_date: date
    created_at: datetime
```

**Space:**
```python
@dataclass
class Space:
    id: str
    name: str
    backend: str  # "anytype", "notion", etc.
```

---

## 6. Non-Functional Requirements

### NFR-01: Performance

| Metric | Requirement |
|--------|-------------|
| Command latency | < 2 seconds for local backends (AnyType, Obsidian) |
| Command latency | < 5 seconds for API backends (Notion, Linear) |
| Connection time | < 3 seconds |
| Memory usage | No significant increase from current baseline |

### NFR-02: Reliability

| Metric | Requirement |
|--------|-------------|
| Retry attempts | 3 attempts for transient failures |
| Backoff strategy | Exponential: 1s, 2s, 4s |
| Timeout | 30 seconds per operation |
| Graceful degradation | Clear error messages, never crash |

### NFR-03: Security

| Requirement | Implementation |
|-------------|----------------|
| Secrets not in config files | Use environment variables |
| Token handling | Never log or display tokens |
| Credential validation | Verify on connect, clear error on failure |

### NFR-04: Maintainability

| Requirement | Implementation |
|-------------|----------------|
| Code coverage | ≥ 80% for adapter base classes |
| Documentation | All public methods documented |
| Type hints | Full type annotations |
| Linting | Pass ruff and mypy checks |

### NFR-05: Compatibility

| Requirement | Details |
|-------------|---------|
| Python version | 3.11+ |
| OS support | macOS, Linux (Windows best-effort) |
| Backward compatibility | All existing CLI commands unchanged |

---

## 7. User Experience

### UX-01: Configuration Flow

**First-time Setup (New Backend):**
```
$ jarvis config backend notion

Setting up Notion backend...

1. Create a Notion integration at https://www.notion.so/my-integrations
2. Copy your Internal Integration Token
3. Set environment variable: export JARVIS_NOTION_TOKEN=<your-token>

Enter your Notion workspace ID: abc123
Enter your Tasks database ID: def456
Enter your Journal database ID: ghi789

✓ Configuration saved to ~/.jarvis/config.yaml
✓ Testing connection... Success!
✓ Notion is now your active backend.
```

**Switching Backends:**
```
$ jarvis config backend anytype

Switching to AnyType backend...
✓ Connection verified
✓ AnyType is now your active backend.
```

### UX-02: Capability Feedback

**When Feature Unavailable:**
```
$ jarvis journal insights --days 30

✗ Journal insights not supported by Obsidian backend.

Obsidian stores journal entries as plain markdown files.
Consider using a backend with search capabilities (AnyType, Notion).
```

### UX-03: Status Display

```
$ jarvis status

Jarvis Status
─────────────────────────────────
Backend:     Notion
Connection:  ✓ Connected
Workspace:   Julian's Workspace
Capabilities:
  ✓ Tasks
  ✓ Journal
  ✓ Tags
  ✓ Search
  ✗ Relations (not available)
```

### UX-04: Error Messages

**Connection Error:**
```
$ jarvis t "Buy groceries"

✗ Cannot connect to Notion

Possible causes:
  • No internet connection
  • Notion API is down
  • Token expired or invalid

Try: jarvis status --diagnose
```

**Auth Error:**
```
$ jarvis t "Buy groceries"

✗ Authentication failed

Your Notion token appears to be invalid or expired.
Generate a new token at: https://www.notion.so/my-integrations
Then update: export JARVIS_NOTION_TOKEN=<new-token>
```

---

## 8. Technical Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Jarvis CLI                              │
│  (cli.py, task/cli.py, journal/cli.py)                         │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Adapter Registry                             │
│  - get_adapter() → returns configured adapter                   │
│  - list_adapters() → available backends                         │
│  - validate_config() → check configuration                      │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│              KnowledgeBaseAdapter (Protocol)                    │
│  - capabilities                                                 │
│  - connect/disconnect/is_connected                              │
│  - Task operations                                              │
│  - Journal operations                                           │
│  - Tag operations                                               │
└─────────────────────────┬───────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ AnyTypeAdapter  │ │  NotionAdapter  │ │ ObsidianAdapter │
│                 │ │                 │ │    (Future)     │
│ - gRPC client   │ │ - HTTP client   │ │ - File system   │
│ - Local only    │ │ - API token     │ │ - Markdown      │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

### File Structure

```
src/jarvis/
├── adapters/
│   ├── __init__.py          # Adapter registry
│   ├── base.py              # KnowledgeBaseAdapter protocol
│   ├── exceptions.py        # Typed exceptions
│   ├── anytype.py           # AnyType adapter
│   └── notion.py            # Notion adapter
├── config/
│   ├── __init__.py
│   ├── loader.py            # Config file handling
│   └── schema.py            # Config validation
├── models/
│   ├── __init__.py
│   ├── task.py              # Task domain model
│   ├── journal.py           # JournalEntry model
│   └── space.py             # Space model
└── ... (existing code)
```

---

## 9. Data Requirements

### Configuration Schema

```yaml
# ~/.jarvis/config.yaml
version: 1
active_backend: notion

backends:
  anytype:
    # No additional config required - uses local gRPC

  notion:
    workspace_id: string (required)
    task_database_id: string (required)
    journal_database_id: string (required)

  obsidian:
    vault_path: string (required)
    tasks_folder: string (default: "Tasks")
    journal_folder: string (default: "Journal")
```

### Environment Variables

| Variable | Backend | Purpose |
|----------|---------|---------|
| `JARVIS_NOTION_TOKEN` | Notion | API integration token |
| `JARVIS_LINEAR_API_KEY` | Linear | API key |
| `JARVIS_JIRA_TOKEN` | Jira | API token |

---

## 10. Integration Requirements

### Notion Integration

| Requirement | Details |
|-------------|---------|
| API Version | Notion API 2022-06-28 or later |
| Auth Method | Internal Integration Token |
| Rate Limits | 3 requests/second (handle with retry) |
| Required Scopes | Read/write content, read user info |

**Database Schema Requirements:**
- Tasks database: Title, Due Date, Priority (select), Tags (multi-select), Done (checkbox)
- Journal database: Title, Content, Date

### AnyType Integration

| Requirement | Details |
|-------------|---------|
| Protocol | gRPC over localhost:31009 |
| Auth | None (local only) |
| Dependency | AnyType desktop app must be running |

---

## 11. Analytics and Metrics

### Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Backend switch time | < 1 minute | User testing |
| Command success rate | ≥ 99% | Error logging |
| New adapter implementation | < 1 day for experienced Python developer | Contributor feedback |
| Test coverage | ≥ 80% | pytest-cov |

### Operational Metrics

| Metric | Purpose |
|--------|---------|
| Adapter usage distribution | Understand which backends are popular |
| Error rates by adapter | Identify problematic integrations |
| Command latency by backend | Performance comparison |

Analytics are opt-in and stored locally in `~/.jarvis/metrics.json`. No data is sent externally.

---

## 12. Security Considerations

### Threat Model

| Threat | Mitigation |
|--------|------------|
| Token exposure in logs | Never log secrets; redact in error messages |
| Token in config file | Enforce env vars for secrets; warn if token in config |
| Man-in-the-middle | Use HTTPS for all API calls |
| Credential stuffing | Rate limit connection attempts |

### Security Requirements

1. **Secrets Management:** All API tokens/keys MUST be stored in environment variables
2. **Transport Security:** All HTTP API calls MUST use HTTPS
3. **Error Sanitization:** Error messages MUST NOT include tokens or sensitive data
4. **Audit Logging:** Not required for personal CLI tool (out of scope for Phase 1)

---

## 13. Testing Strategy

### Unit Tests

| Component | Coverage Target |
|-----------|-----------------|
| Adapter base class | 90% |
| Config loader | 90% |
| Domain models | 80% |
| Error handling | 85% |

### Integration Tests

| Test | Description |
|------|-------------|
| AnyType adapter | Full CRUD operations against running AnyType |
| Notion adapter | Full CRUD operations against test workspace |
| Config switching | Verify backend switch works correctly |

### Mock Tests

| Test | Description |
|------|-------------|
| Adapter protocol compliance | Verify adapters implement all methods |
| Capability checking | Test behavior when capability missing |
| Error handling | Test retry and error message formatting |

---

## 14. Release Strategy

### Phase 1: Foundation (This Epic)

**Milestone 1: Adapter Architecture**
- [ ] Define KnowledgeBaseAdapter protocol
- [ ] Implement adapter registry
- [ ] Create configuration system
- [ ] Define typed exceptions

**Milestone 2: AnyType Refactor**
- [ ] Extract AnyTypeAdapter from AnyTypeClient
- [ ] Verify all existing tests pass
- [ ] No user-facing changes

**Milestone 3: Notion Adapter**
- [ ] Implement NotionAdapter
- [ ] Add Notion-specific configuration
- [ ] Integration tests with test workspace

**Milestone 4: Polish**
- [ ] `jarvis config` commands
- [ ] Status and capability display
- [ ] Documentation

### Rollout

1. **Alpha:** Internal testing with both backends
2. **Beta:** Release to early adopters, gather feedback
3. **GA:** Public release with documentation

---

## 15. Risks and Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Notion API changes | High | Low | Version-lock API client, monitor changelog |
| Abstraction too leaky | High | Medium | Thorough interface design, multiple adapter implementations |
| Performance regression | Medium | Low | Benchmark before/after, performance tests |
| AnyType users disrupted | High | Low | Comprehensive testing, gradual rollout |
| Adapter complexity | Medium | Medium | Clear documentation, example adapter |

### Contingency Plans

**If Notion adapter proves too complex:**
- Reduce scope to read-only operations
- Defer to Phase 2

**If abstraction doesn't fit AnyType well:**
- Keep AnyType-specific code paths
- Abstract only common operations

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| **Adapter** | Component that translates between Jarvis and a specific backend |
| **Backend** | External knowledge base system (AnyType, Notion, etc.) |
| **Capability** | Feature that may or may not be supported by a backend |
| **Space** | Top-level container (workspace, vault, team) in a backend |

---

## Appendix B: Open Questions

1. **Plugin architecture?** Should adapters be loadable at runtime, or compiled in?
   - *Recommendation:* Start compiled-in, evaluate plugin system later

2. **Backend-specific IDs?** How to handle different ID formats across backends?
   - *Recommendation:* Always use string IDs, backends handle their own format

3. **Caching?** Should adapters cache to reduce API calls?
   - *Recommendation:* Optional per-adapter, not in base class

4. **Offline support?** Queue operations when backend unavailable?
   - *Recommendation:* Out of scope for Phase 1

---

## Appendix C: References

- [Jarvis Roadmap](../../context/roadmap.md)
- [Current AnyTypeClient](../../src/jarvis/anytype_client.py)
- [Notion API Documentation](https://developers.notion.com/)
- [Repository Pattern](https://martinfowler.com/eaaCatalog/repository.html)

---

*Generated from brainstorm.md on 2025-01-25*
