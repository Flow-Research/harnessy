# MVP Technical Specification: Jarvis

**Minimum Viable Product — AnyType Task Scheduler**

---

## 1. MVP Overview

### Goal

Deliver a working CLI tool that can:
1. **Analyze** your AnyType task schedule
2. **Suggest** rescheduling to balance workload
3. **Apply** approved changes back to AnyType

### Hypothesis to Validate

> "An AI-assisted scheduler that respects user preferences will reduce cognitive load and improve workload distribution for AnyType power users."

### MVP Success Criteria

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Core workflow works | 100% | analyze → suggest → apply completes without error |
| `bar_movement` respected | 100% | Zero suggestions for immovable tasks |
| Workload improves | Visible | Variance reduction shown in analysis |
| User stays in control | 100% | No changes without approval |

---

## 2. MVP Scope Boundaries

### IN Scope (MVP)

| Feature | Justification |
|---------|---------------|
| `jarvis analyze` | Core value: see your schedule |
| `jarvis suggest` | Core value: get AI recommendations |
| `jarvis apply` | Core value: apply approved changes |
| AnyType API read/write | Foundation for everything |
| Context file reading | Personalization from day one |
| AI-powered suggestions | Primary differentiator |
| Basic CLI formatting | Usable output |
| `bar_movement` filtering | Hard requirement |

### OUT of Scope (Post-MVP)

| Feature | Why Deferred | Migration Path |
|---------|--------------|----------------|
| `jarvis status` command | Nice-to-have | Add later with no changes |
| `jarvis context` command | Nice-to-have | Add later with no changes |
| Scheduled daily runs | Convenience, not core | Add cron/launchd later |
| Learning system | Enhancement | Schema supports it already |
| Task caching | Optimization | Add transparent layer |
| History tracking | Analytics | Schema supports it already |
| Confidence filtering | Refinement | Add `--min-confidence` later |
| Algorithmic fallback | Edge case | AI failure = clear error for MVP |

### Simplifications for MVP

| Full Spec | MVP Approach | Technical Debt |
|-----------|--------------|----------------|
| Full error handling with Result type | Simple try/except with clear messages | Low — refactor later |
| Task caching (5 min TTL) | Fresh fetch every time | Low — add caching layer |
| History storage | No history, just pending.json | None — schema ready |
| SecretManager with keyring | Environment variables only | Low — add keychain later |
| Comprehensive logging | Basic print + Rich console | Low — add logging later |

---

## 3. MVP Architecture

### Simplified Module Structure

```
jarvis/
├── __init__.py
├── __main__.py                 # Entry point
├── cli.py                      # All CLI commands (single file for MVP)
├── models.py                   # All Pydantic models
├── anytype_client.py           # AnyType API wrapper
├── ai_client.py                # Claude API wrapper
├── analyzer.py                 # Workload analysis
├── context_reader.py           # Parse context/*.md files
├── state.py                    # Suggestion persistence
└── prompts.py                  # AI prompt templates
```

**Rationale:** Fewer files = faster iteration. Can split into submodules post-MVP without breaking imports.

### Data Flow (MVP)

```
┌─────────────┐
│   AnyType   │
│   Desktop   │
└──────┬──────┘
       │ API
       ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  anytype_   │────▶│  analyzer   │────▶│ ai_client   │
│  client     │     │             │     │             │
└─────────────┘     └─────────────┘     └──────┬──────┘
                           │                   │
                           ▼                   │
                    ┌─────────────┐            │
                    │  context/   │◀───────────┘
                    │  (files)    │
                    └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │    CLI      │
                    │  (output)   │
                    └─────────────┘
```

---

## 4. MVP Data Models

All models from full spec are preserved — **no schema changes needed post-MVP**.

### Task (unchanged from full spec)

```python
class Task(BaseModel):
    id: str
    space_id: str
    name: str
    scheduled_date: date | None
    due_date: date | None
    priority: str | None = None
    tags: list[str] = []
    is_done: bool = False
    created_at: datetime
    updated_at: datetime

    @property
    def is_moveable(self) -> bool:
        return "bar_movement" not in self.tags
```

### Suggestion (unchanged from full spec)

```python
class Suggestion(BaseModel):
    id: str
    task_id: str
    task_name: str
    current_date: date
    proposed_date: date
    reasoning: str
    confidence: float  # 0.0-1.0
    status: Literal["pending", "accepted", "rejected", "applied", "failed"]
    created_at: datetime
```

### WorkloadAnalysis (unchanged from full spec)

```python
class DayWorkload(BaseModel):
    date: date
    total_tasks: int
    moveable_tasks: int
    immovable_tasks: int
    task_ids: list[str]

class WorkloadAnalysis(BaseModel):
    start_date: date
    end_date: date
    days: list[DayWorkload]
    total_moveable: int
    total_immovable: int
```

### UserContext (simplified for MVP)

```python
class UserContext(BaseModel):
    """MVP: Just raw markdown content, let AI interpret."""
    preferences_raw: str = ""
    patterns_raw: str = ""
    constraints_raw: str = ""
    priorities_raw: str = ""

    def to_prompt_context(self) -> str:
        """Concatenate all context for AI prompt."""
        sections = []
        if self.preferences_raw:
            sections.append(f"## Preferences\n{self.preferences_raw}")
        if self.patterns_raw:
            sections.append(f"## Patterns\n{self.patterns_raw}")
        if self.constraints_raw:
            sections.append(f"## Constraints\n{self.constraints_raw}")
        if self.priorities_raw:
            sections.append(f"## Priorities\n{self.priorities_raw}")
        return "\n\n".join(sections) or "No user context provided."
```

**Simplification:** No structured parsing of context files in MVP. Just pass raw markdown to Claude and let it interpret. Full spec's structured `TimePreference` and `Constraint` models can be added later.

---

## 5. MVP CLI Specification

### Commands

```bash
jarvis analyze [--days N]     # Analyze workload (default: 14 days)
jarvis suggest [--days N]     # Generate AI suggestions
jarvis apply                  # Interactive approval and apply
```

### CLI Implementation (Click + Rich)

```python
# jarvis/cli.py
import click
from rich.console import Console
from rich.table import Table

console = Console()

@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Jarvis - Intelligent task scheduler for AnyType"""
    pass

@cli.command()
@click.option("--days", default=14, help="Days to analyze")
def analyze(days: int):
    """Analyze current schedule workload."""
    # Implementation...

@cli.command()
@click.option("--days", default=14, help="Days to consider")
def suggest(days: int):
    """Generate rescheduling suggestions."""
    # Implementation...

@cli.command()
def apply():
    """Apply pending suggestions to AnyType."""
    # Implementation...
```

### Output Format (MVP)

**analyze:**
```
📊 Schedule Analysis (Next 14 Days)

  Mon 27  ████████  8 tasks  ⚠️ Overloaded
  Tue 28  ████      4 tasks  ✓
  Wed 29  ██        2 tasks  ○ Light
  ...

🔒 Immovable: 3 tasks
📦 Moveable: 19 tasks
📈 Variance: 2.4 (lower is better)
```

**suggest:**
```
💡 3 Suggestions Generated

1. "Write API docs"
   Mon 27 → Wed 29
   Reason: Balances workload, no deadline pressure

2. "Review PRs"
   Mon 27 → Fri 31
   Reason: Admin task fits Friday pattern

Run `jarvis apply` to review and apply.
```

**apply:**
```
📋 Review Suggestions

[1/3] Move "Write API docs" Mon 27 → Wed 29? [y/n]: y
✓ Applied

[2/3] Move "Review PRs" Mon 27 → Fri 31? [y/n]: n
✗ Skipped

[3/3] Move "Update deps" Mon 27 → Wed 29? [y/n]: y
✓ Applied

Done! Applied: 2 | Skipped: 1
```

---

## 6. MVP Implementation Details

### AnyType Client (MVP)

```python
# jarvis/anytype_client.py
from anytype import Anytype

class AnyTypeClient:
    def __init__(self):
        self._client: Anytype | None = None

    async def connect(self) -> None:
        """Connect and authenticate with AnyType."""
        self._client = Anytype()
        await self._client.auth()

    async def get_default_space(self) -> str:
        """Get first available space ID."""
        spaces = await self._client.get_spaces()
        if not spaces:
            raise RuntimeError("No AnyType spaces found")
        return spaces[0].id

    async def get_tasks_in_range(
        self,
        space_id: str,
        start: date,
        end: date
    ) -> list[Task]:
        """Fetch all tasks within date range."""
        space = await self._client.get_space(space_id)
        results = await space.search(query="", types=["task"])

        tasks = []
        for obj in results:
            task = self._to_task(obj, space_id)
            if task.scheduled_date and start <= task.scheduled_date <= end:
                tasks.append(task)
        return tasks

    async def update_task_date(
        self,
        space_id: str,
        task_id: str,
        new_date: date
    ) -> bool:
        """Update a task's scheduled date."""
        try:
            space = await self._client.get_space(space_id)
            obj = await space.get_object(task_id)
            obj.scheduled_date = new_date.isoformat()
            await obj.save()
            return True
        except Exception as e:
            console.print(f"[red]Error updating task: {e}[/red]")
            return False
```

### AI Client (MVP)

```python
# jarvis/ai_client.py
from anthropic import Anthropic
import json

class AIClient:
    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)

    def generate_suggestions(
        self,
        tasks: list[Task],
        analysis: WorkloadAnalysis,
        context: UserContext,
    ) -> list[Suggestion]:
        """Generate suggestions using Claude."""

        prompt = self._build_prompt(tasks, analysis, context)

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            temperature=0.3,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )

        return self._parse_response(response.content[0].text, tasks)

    def _parse_response(self, text: str, tasks: list[Task]) -> list[Suggestion]:
        """Parse JSON suggestions from Claude's response."""
        # Extract JSON from response
        try:
            # Find JSON block in response
            start = text.find("{")
            end = text.rfind("}") + 1
            data = json.loads(text[start:end])

            suggestions = []
            for s in data.get("suggestions", []):
                # Find matching task
                task = next((t for t in tasks if t.name == s["task_name"]), None)
                if task:
                    suggestions.append(Suggestion(
                        id=f"sug_{uuid4().hex[:8]}",
                        task_id=task.id,
                        task_name=s["task_name"],
                        current_date=date.fromisoformat(s["current_date"]),
                        proposed_date=date.fromisoformat(s["proposed_date"]),
                        reasoning=s["reasoning"],
                        confidence=s.get("confidence", 0.7),
                        status="pending",
                        created_at=datetime.now(),
                    ))
            return suggestions
        except (json.JSONDecodeError, KeyError) as e:
            console.print(f"[yellow]Warning: Could not parse AI response: {e}[/yellow]")
            return []
```

### State Management (MVP)

```python
# jarvis/state.py
from pathlib import Path
import json

DATA_DIR = Path.home() / ".jarvis"
PENDING_FILE = DATA_DIR / "pending.json"

def save_suggestions(suggestions: list[Suggestion], space_id: str) -> None:
    """Save suggestions to pending.json."""
    DATA_DIR.mkdir(exist_ok=True)

    data = {
        "generated_at": datetime.now().isoformat(),
        "space_id": space_id,
        "suggestions": [s.model_dump(mode="json") for s in suggestions]
    }

    PENDING_FILE.write_text(json.dumps(data, indent=2, default=str))

def load_suggestions() -> tuple[list[Suggestion], str]:
    """Load pending suggestions. Returns (suggestions, space_id)."""
    if not PENDING_FILE.exists():
        return [], ""

    data = json.loads(PENDING_FILE.read_text())
    suggestions = [Suggestion(**s) for s in data.get("suggestions", [])]
    return suggestions, data.get("space_id", "")

def clear_suggestions() -> None:
    """Clear pending suggestions after apply."""
    if PENDING_FILE.exists():
        PENDING_FILE.unlink()
```

### Context Reader (MVP)

```python
# jarvis/context_reader.py
from pathlib import Path

def load_context(context_path: Path = Path("./context")) -> UserContext:
    """Load all context files as raw markdown."""

    def read_if_exists(filename: str) -> str:
        path = context_path / filename
        return path.read_text() if path.exists() else ""

    return UserContext(
        preferences_raw=read_if_exists("preferences.md"),
        patterns_raw=read_if_exists("patterns.md"),
        constraints_raw=read_if_exists("constraints.md"),
        priorities_raw=read_if_exists("priorities.md"),
    )
```

---

## 7. MVP Work Items

### Priority Definitions

| Priority | Meaning | Rule |
|----------|---------|------|
| **P0** | MVP Blocker | Cannot ship without this |
| **P1** | MVP Important | Significantly degrades experience if missing |
| **P2** | MVP Nice-to-have | First to cut if time-constrained |

---

### Work Item Breakdown

#### Phase 1: Project Setup (P0)

| ID | Work Item | Acceptance Criteria | Dependencies |
|----|-----------|---------------------|--------------|
| **WI-001** | Initialize project with uv | `uv init` creates pyproject.toml, src layout works | None |
| **WI-002** | Configure dependencies | All deps in pyproject.toml, `uv sync` works | WI-001 |
| **WI-003** | Create module structure | All MVP files created with stubs | WI-001 |
| **WI-004** | Create models.py | All Pydantic models with tests | WI-003 |

#### Phase 2: AnyType Integration (P0)

| ID | Work Item | Acceptance Criteria | Dependencies |
|----|-----------|---------------------|--------------|
| **WI-005** | Implement AnyTypeClient.connect() | Auth flow works, error on AnyType not running | WI-004 |
| **WI-006** | Implement get_default_space() | Returns first space ID | WI-005 |
| **WI-007** | Implement get_tasks_in_range() | Returns Task models, filters by date | WI-005 |
| **WI-008** | Implement update_task_date() | Updates task in AnyType, returns success bool | WI-005 |

#### Phase 3: Core Analysis (P0)

| ID | Work Item | Acceptance Criteria | Dependencies |
|----|-----------|---------------------|--------------|
| **WI-009** | Implement workload analyzer | Generates WorkloadAnalysis from tasks | WI-004 |
| **WI-010** | Add bar_movement filtering | `is_moveable` property works correctly | WI-009 |
| **WI-011** | Calculate day status | Overloaded/balanced/light computed | WI-009 |

#### Phase 4: Context System (P0)

| ID | Work Item | Acceptance Criteria | Dependencies |
|----|-----------|---------------------|--------------|
| **WI-012** | Implement context_reader | Loads all context/*.md files | WI-003 |
| **WI-013** | Implement to_prompt_context() | Formats context for AI prompt | WI-012 |

#### Phase 5: AI Integration (P0)

| ID | Work Item | Acceptance Criteria | Dependencies |
|----|-----------|---------------------|--------------|
| **WI-014** | Implement AIClient | Connects to Anthropic API | WI-002 |
| **WI-015** | Create prompt templates | System prompt + suggestion prompt | WI-014 |
| **WI-016** | Implement generate_suggestions() | Returns parsed Suggestion list | WI-015 |
| **WI-017** | Handle AI response parsing | Extracts JSON, handles malformed responses | WI-016 |

#### Phase 6: State Management (P0)

| ID | Work Item | Acceptance Criteria | Dependencies |
|----|-----------|---------------------|--------------|
| **WI-018** | Implement save_suggestions() | Writes to ~/.jarvis/pending.json | WI-004 |
| **WI-019** | Implement load_suggestions() | Reads and parses pending.json | WI-018 |
| **WI-020** | Implement clear_suggestions() | Removes pending.json after apply | WI-018 |

#### Phase 7: CLI Commands (P0)

| ID | Work Item | Acceptance Criteria | Dependencies |
|----|-----------|---------------------|--------------|
| **WI-021** | Create CLI skeleton with Click | `jarvis --help` works | WI-003 |
| **WI-022** | Implement `jarvis analyze` | Shows formatted workload analysis | WI-009, WI-021 |
| **WI-023** | Implement `jarvis suggest` | Generates and saves suggestions | WI-016, WI-018, WI-021 |
| **WI-024** | Implement `jarvis apply` | Interactive approval, updates AnyType | WI-008, WI-019, WI-021 |

#### Phase 8: Polish (P1)

| ID | Work Item | Acceptance Criteria | Dependencies |
|----|-----------|---------------------|--------------|
| **WI-025** | Rich formatting for analyze | Visual bars, colors, status indicators | WI-022 |
| **WI-026** | Rich formatting for suggest | Numbered list with reasoning | WI-023 |
| **WI-027** | Rich formatting for apply | Interactive prompts, success/fail indicators | WI-024 |
| **WI-028** | Error messages | Clear, actionable messages for all errors | All |

#### Phase 9: Testing (P1)

| ID | Work Item | Acceptance Criteria | Dependencies |
|----|-----------|---------------------|--------------|
| **WI-029** | Unit tests for models | All model behaviors tested | WI-004 |
| **WI-030** | Unit tests for analyzer | Workload calculation tested | WI-009 |
| **WI-031** | Integration test with AnyType | End-to-end test with real AnyType | WI-024 |

#### Phase 10: Documentation (P2)

| ID | Work Item | Acceptance Criteria | Dependencies |
|----|-----------|---------------------|--------------|
| **WI-032** | README with installation | Quick start guide works | All |
| **WI-033** | .env.example | Documents required env vars | WI-014 |

---

### Work Item Dependency Graph

```
WI-001 (init)
   │
   ├── WI-002 (deps)
   │      └── WI-014 (AI client)
   │             └── WI-015 (prompts)
   │                    └── WI-016 (suggestions)
   │                           └── WI-017 (parsing)
   │
   └── WI-003 (structure)
          │
          ├── WI-004 (models)
          │      │
          │      ├── WI-009 (analyzer)
          │      │      ├── WI-010 (bar_movement)
          │      │      └── WI-011 (day status)
          │      │
          │      ├── WI-018 (save state)
          │      │      ├── WI-019 (load state)
          │      │      └── WI-020 (clear state)
          │      │
          │      └── WI-005 (AT connect)
          │             ├── WI-006 (get space)
          │             ├── WI-007 (get tasks)
          │             └── WI-008 (update task)
          │
          ├── WI-012 (context reader)
          │      └── WI-013 (prompt context)
          │
          └── WI-021 (CLI skeleton)
                 ├── WI-022 (analyze) ← WI-009
                 ├── WI-023 (suggest) ← WI-016, WI-018
                 └── WI-024 (apply) ← WI-008, WI-019
```

---

## 8. MVP Build Sequence

### Recommended Order

```
Week 1: Foundation
├── Day 1-2: WI-001 → WI-004 (Project + Models)
├── Day 3-4: WI-005 → WI-008 (AnyType Client)
└── Day 5: WI-009 → WI-011 (Analyzer)

Week 2: Intelligence
├── Day 1: WI-012 → WI-013 (Context)
├── Day 2-3: WI-014 → WI-017 (AI Client)
└── Day 4-5: WI-018 → WI-020 (State)

Week 3: CLI + Polish
├── Day 1-2: WI-021 → WI-024 (CLI Commands)
├── Day 3-4: WI-025 → WI-028 (Formatting + Errors)
└── Day 5: WI-029 → WI-031 (Testing)

Week 4: Ship
├── Day 1-2: WI-032 → WI-033 (Docs)
└── Day 3-5: Buffer for bugs and refinement
```

---

## 9. MVP Technical Debt Register

| Debt Item | Impact | Remediation | When |
|-----------|--------|-------------|------|
| No caching | Extra API calls | Add TaskCache class | Post-MVP |
| Raw context parsing | Less structured rules | Add TimePreference models | Post-MVP |
| Simple error handling | Less graceful failures | Add Result type | Post-MVP |
| No logging | Harder debugging | Add structured logging | Post-MVP |
| Env vars only for secrets | Less secure | Add keyring support | Post-MVP |
| No algorithmic fallback | AI failure = total failure | Add fallback scheduler | Post-MVP |
| No history | Can't track patterns | Add history storage | Post-MVP |

---

## 10. MVP Validation Checklist

Before shipping MVP:

**Functional:**
- [ ] `jarvis analyze` shows workload for 14 days
- [ ] `jarvis suggest` generates AI suggestions
- [ ] `jarvis apply` updates tasks in AnyType
- [ ] `bar_movement` tasks never suggested for move
- [ ] Context files influence suggestions
- [ ] No changes without user approval

**Technical:**
- [ ] Works with Python 3.11+
- [ ] Installs via `uv pip install -e .`
- [ ] Clear error when AnyType not running
- [ ] Clear error when ANTHROPIC_API_KEY missing

**Quality:**
- [ ] Core models have unit tests
- [ ] At least one end-to-end test passes
- [ ] README explains installation and usage

---

*MVP Technical Specification v1.0*
*Created: 2025-01-23*
*Status: Ready for implementation*
