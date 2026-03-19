# Technical Specification: Weekly Planning Command

## 1. Overview

### 1.1 Purpose

This document specifies the technical architecture and implementation details for the `jarvis plan` command — a proactive weekly planning feature that synthesizes context files and scheduled tasks to generate actionable weekly plans with gap analysis.

### 1.2 Scope

**In Scope:**
- CLI command implementation (`jarvis plan`, alias `jarvis p`)
- Context aggregation and structured extraction
- Task retrieval via adapter layer
- Alignment scoring algorithm
- Gap detection engine
- AI-powered plan generation
- Rich terminal output formatting
- Interactive Q&A mode
- Plan file persistence

**Out of Scope:**
- Plan history tracking
- Calendar integration beyond context files
- Automated task creation
- `--json` output (future release)

### 1.3 Document Conventions

| Tag | Meaning |
|-----|---------|
| `[EXISTING]` | Uses existing codebase component |
| `[NEW]` | New component to implement |
| `[INFERRED]` | Reasonable default, can be overridden |

---

## 2. System Architecture

### 2.1 Architecture Style

**Monolithic CLI Extension** — The plan command follows the existing Jarvis architecture: a Click-based CLI command that orchestrates services and outputs via Rich.

### 2.2 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              CLI Layer                                   │
│                         src/jarvis/plan/cli.py                          │
│                                                                         │
│  ┌───────────┐   ┌───────────┐   ┌───────────┐   ┌───────────────────┐ │
│  │ --days N  │   │--interact │   │  --save   │   │ jarvis plan / p   │ │
│  └───────────┘   └───────────┘   └───────────┘   └───────────────────┘ │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          Service Layer                                   │
│                    src/jarvis/plan/service.py                           │
│                                                                         │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────────────────┐   │
│  │ PlanService   │──│ orchestrates  │──│ context + tasks + AI     │   │
│  └───────────────┘  └───────────────┘  └───────────────────────────┘   │
└───────────┬────────────────┬────────────────────┬───────────────────────┘
            │                │                    │
            ▼                ▼                    ▼
┌───────────────────┐ ┌───────────────────┐ ┌──────────────────────────────┐
│  Context Layer    │ │   Task Layer      │ │      AI Layer                │
│  [EXISTING]       │ │   [EXISTING]      │ │   [EXISTING + NEW]           │
│                   │ │                   │ │                              │
│ context_reader.py │ │ TaskService       │ │ AIClient + plan prompts     │
│ UserContext model │ │ Adapter layer     │ │ PlanGenerator               │
└───────────────────┘ └───────────────────┘ └──────────────────────────────┘
```

### 2.3 Component Architecture

```
src/jarvis/
├── plan/                      [NEW]
│   ├── __init__.py            Package exports
│   ├── cli.py                 Click command definition
│   ├── service.py             PlanService orchestrator
│   ├── context_parser.py      Structured context extraction
│   ├── alignment.py           Alignment scoring algorithm
│   ├── gaps.py                Gap detection engine
│   ├── generator.py           AI plan generation
│   ├── formatter.py           Rich output formatting
│   ├── interactive.py         Q&A session handling
│   └── prompts.py             AI prompt templates
├── models/
│   └── plan.py                [NEW] Plan domain models
└── cli.py                     [MODIFIED] Add plan command group
```

### 2.4 Data Flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│                            DATA FLOW                                      │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────────────────────┐ │
│  │  Context    │     │  Knowledge  │     │  CLI Arguments              │ │
│  │  Files      │     │  Base       │     │  --days, --interactive      │ │
│  └──────┬──────┘     └──────┬──────┘     └──────────────┬──────────────┘ │
│         │                   │                           │                │
│         ▼                   ▼                           │                │
│  ┌─────────────┐     ┌─────────────┐                    │                │
│  │ context_    │     │ TaskService │                    │                │
│  │ reader.py   │     │ .get_tasks()│                    │                │
│  └──────┬──────┘     └──────┬──────┘                    │                │
│         │                   │                           │                │
│         ▼                   ▼                           │                │
│  ┌─────────────┐     ┌─────────────┐                    │                │
│  │ context_    │     │ Task list   │                    │                │
│  │ parser.py   │     │ [Task, ...] │                    │                │
│  │ (extract    │     └──────┬──────┘                    │                │
│  │  structure) │            │                           │                │
│  └──────┬──────┘            │                           │                │
│         │                   │                           │                │
│         ▼                   ▼                           ▼                │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │                         PlanService                                  │ │
│  │                                                                     │ │
│  │  1. Aggregate context (PlanContext)                                 │ │
│  │  2. Retrieve tasks in window                                        │ │
│  │  3. Calculate alignment (alignment.py)                              │ │
│  │  4. Detect gaps (gaps.py)                                           │ │
│  │  5. Generate plan via AI (generator.py)                             │ │
│  │  6. Format output (formatter.py)                                    │ │
│  └──────────────────────────────┬──────────────────────────────────────┘ │
│                                 │                                        │
│                                 ▼                                        │
│                          ┌─────────────┐                                 │
│                          │ WeeklyPlan  │                                 │
│                          │ (complete   │                                 │
│                          │  output)    │                                 │
│                          └──────┬──────┘                                 │
│                                 │                                        │
│              ┌──────────────────┼──────────────────┐                     │
│              ▼                  ▼                  ▼                     │
│       ┌───────────┐      ┌───────────┐      ┌───────────┐               │
│       │ Terminal  │      │ --inter-  │      │  --save   │               │
│       │ Output    │      │  active   │      │  to file  │               │
│       └───────────┘      └───────────┘      └───────────┘               │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Data Architecture

### 3.1 Domain Models

Located in `src/jarvis/models/plan.py`:

```python
"""Domain models for weekly planning."""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Literal


class FocusMode(str, Enum):
    """User's current operational mode."""
    SHIPPING = "shipping"
    LEARNING = "learning"
    EXPLORING = "exploring"
    RECOVERY = "recovery"
    UNKNOWN = "unknown"


@dataclass
class FocusSummary:
    """Synthesized focus from context files."""
    mode: FocusMode
    mode_emoji: str  # 🚀, 📚, 🔍, 🌿, ❓
    primary_goal: str | None
    decision_rule: str | None
    until_date: date | None

    @classmethod
    def empty(cls) -> "FocusSummary":
        """Create empty focus summary for graceful degradation."""
        return cls(
            mode=FocusMode.UNKNOWN,
            mode_emoji="❓",
            primary_goal=None,
            decision_rule=None,
            until_date=None,
        )


@dataclass
class ExtractedGoal:
    """A goal extracted from context files."""
    text: str
    timeframe: Literal["this_week", "this_month", "this_quarter", "ongoing"]
    source_file: str  # e.g., "goals.md"
    has_tasks: bool = False  # Set during gap analysis
    matching_task_ids: list[str] = field(default_factory=list)


@dataclass
class TaskCategory:
    """A category of tasks with alignment info."""
    name: str
    emoji: str
    task_ids: list[str]
    task_count: int
    is_aligned: bool  # Aligned with current focus


@dataclass
class TaskReality:
    """Current state of scheduled tasks."""
    total_tasks: int
    tasks_by_day: dict[date, list[str]]  # date -> task_ids
    tasks_by_category: list[TaskCategory]
    alignment_score: float  # 0.0 - 1.0
    overloaded_days: list[date]  # days with >6 tasks
    empty_days: list[date]  # days with 0 tasks in window

    @property
    def alignment_percent(self) -> int:
        """Alignment score as percentage."""
        return int(self.alignment_score * 100)


@dataclass
class GapAnalysis:
    """Gaps between goals and scheduled work."""
    goals_without_tasks: list[ExtractedGoal]
    focus_conflicts: list[str]  # Human-readable conflict descriptions
    schedule_issues: list[str]  # Overload, no buffer, etc.
    has_critical_gaps: bool  # True if >2 goals without tasks or focus conflicts

    @property
    def total_gaps(self) -> int:
        return (
            len(self.goals_without_tasks)
            + len(self.focus_conflicts)
            + len(self.schedule_issues)
        )


@dataclass
class DailyPlan:
    """Recommended plan for a single day."""
    plan_date: date
    day_name: str  # "Monday", "Tuesday", etc.
    theme: str  # "Deep work day", "Light day", etc.
    existing_tasks: list[str]  # Task titles
    suggestions: list[str]  # Suggested new tasks
    actions: list[str]  # Actions to take (e.g., "Defer X tasks")
    warnings: list[str]  # Issues to be aware of


@dataclass
class QuickAction:
    """Ready-to-run command suggestion."""
    label: str  # "[1]", "[2]", etc.
    command: str  # Full jarvis command
    description: str  # What it does


@dataclass
class WeeklyPlan:
    """Complete weekly plan output."""
    focus_summary: FocusSummary
    task_reality: TaskReality
    gap_analysis: GapAnalysis
    daily_plans: list[DailyPlan]
    quick_actions: list[QuickAction]
    generated_at: datetime
    planning_horizon: int  # days
    context_quality: Literal["full", "partial", "minimal", "none"]

    @property
    def has_gaps(self) -> bool:
        return self.gap_analysis.total_gaps > 0


@dataclass
class PlanContext:
    """Aggregated and parsed context for planning."""
    # Extracted structured data
    focus: FocusSummary
    goals: list[ExtractedGoal]
    priority_rules: list[str]
    constraints: list[str]
    active_projects: list[str]
    blockers: list[str]

    # Raw context for AI prompt
    raw_context: str  # From UserContext.to_prompt_context()

    # Metadata
    context_quality: Literal["full", "partial", "minimal", "none"]
    missing_files: list[str]

    @classmethod
    def empty(cls) -> "PlanContext":
        """Create empty context for graceful degradation."""
        return cls(
            focus=FocusSummary.empty(),
            goals=[],
            priority_rules=[],
            constraints=[],
            active_projects=[],
            blockers=[],
            raw_context="No user context provided.",
            context_quality="none",
            missing_files=[],
        )
```

### 3.2 Model Registration

Add to `src/jarvis/models/__init__.py`:

```python
from .plan import (
    FocusMode,
    FocusSummary,
    ExtractedGoal,
    TaskCategory,
    TaskReality,
    GapAnalysis,
    DailyPlan,
    QuickAction,
    WeeklyPlan,
    PlanContext,
)

__all__ = [
    # ... existing exports ...
    "FocusMode",
    "FocusSummary",
    "ExtractedGoal",
    "TaskCategory",
    "TaskReality",
    "GapAnalysis",
    "DailyPlan",
    "QuickAction",
    "WeeklyPlan",
    "PlanContext",
]
```

---

## 4. API Specification

### 4.1 CLI Interface

**Command:** `jarvis plan [OPTIONS]`
**Alias:** `jarvis p [OPTIONS]`

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--days`, `-d` | int | 7 | Planning horizon (1-30 days) |
| `--interactive`, `-i` | flag | False | Enable Q&A mode after plan |
| `--save`, `-s` | flag | False | Save plan to `~/.jarvis/plans/` |

**Exit Codes:**
| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Connection error (KB unreachable) |
| 2 | Authentication error |
| 3 | Invalid arguments |

### 4.2 Internal APIs

#### PlanService

```python
# src/jarvis/plan/service.py

class PlanService:
    """Orchestrates weekly plan generation."""

    def __init__(self, backend: str | None = None) -> None:
        """Initialize plan service.

        Args:
            backend: Optional backend name override
        """

    def generate_plan(
        self,
        days: int = 7,
    ) -> WeeklyPlan:
        """Generate a complete weekly plan.

        Args:
            days: Planning horizon (1-30)

        Returns:
            WeeklyPlan with all sections populated

        Raises:
            ConnectionError: KB connection failed
            AuthError: Authentication failed
        """

    def generate_interactive_questions(
        self,
        plan: WeeklyPlan,
    ) -> list[str]:
        """Generate follow-up questions based on gaps.

        Args:
            plan: Initial generated plan

        Returns:
            List of 2-5 contextual questions
        """

    def refine_plan(
        self,
        plan: WeeklyPlan,
        answers: dict[str, str],
    ) -> WeeklyPlan:
        """Refine plan based on Q&A answers.

        Args:
            plan: Original plan
            answers: User's answers to questions

        Returns:
            Updated WeeklyPlan
        """
```

#### Context Parser

```python
# src/jarvis/plan/context_parser.py

def parse_context(user_context: UserContext) -> PlanContext:
    """Parse raw context into structured planning data.

    Args:
        user_context: Raw context from context_reader

    Returns:
        PlanContext with extracted structure
    """

def extract_focus(focus_raw: str) -> FocusSummary:
    """Extract focus mode from focus.md content.

    Strategy:
    1. Look for mode keywords (Shipping, Learning, etc.)
    2. Parse "until" date if present
    3. Extract decision rules
    4. Fall back to AI extraction if unstructured
    """

def extract_goals(goals_raw: str) -> list[ExtractedGoal]:
    """Extract goals from goals.md content.

    Strategy:
    1. Look for ## This Week, ## This Month headers
    2. Extract bullet points under headers
    3. Parse frontmatter if present
    4. Fall back to AI extraction if unstructured
    """
```

#### Alignment Calculator

```python
# src/jarvis/plan/alignment.py

def calculate_alignment(
    tasks: list[Task],
    context: PlanContext,
    ai_client: AIClient | None = None,
) -> tuple[float, list[TaskCategory]]:
    """Calculate alignment score and categorize tasks.

    Algorithm (FR-03.A):
    1. Tag match: task tags match focus/goal keywords
    2. Project match: task project in active projects
    3. Title match: task title contains goal keywords (fuzzy)
    4. AI fallback: batch unclear tasks for classification

    Args:
        tasks: Tasks in planning window
        context: Parsed planning context
        ai_client: Optional AI client for fallback classification

    Returns:
        Tuple of (alignment_score, task_categories)
    """

def categorize_tasks(
    tasks: list[Task],
    context: PlanContext,
) -> list[TaskCategory]:
    """Group tasks by project/type with alignment flags."""
```

#### Gap Detector

```python
# src/jarvis/plan/gaps.py

def detect_gaps(
    tasks: list[Task],
    context: PlanContext,
    planning_window: tuple[date, date],
) -> GapAnalysis:
    """Detect gaps between goals and tasks.

    Checks:
    1. Goals without corresponding tasks
    2. Focus mode vs task category conflicts
    3. Schedule issues (overload, no buffer)

    Args:
        tasks: Tasks in planning window
        context: Parsed planning context
        planning_window: (start_date, end_date)

    Returns:
        GapAnalysis with categorized gaps
    """

def match_goals_to_tasks(
    goals: list[ExtractedGoal],
    tasks: list[Task],
) -> list[ExtractedGoal]:
    """Match each goal to its supporting tasks.

    Returns goals with has_tasks and matching_task_ids populated.
    """
```

#### Plan Generator

```python
# src/jarvis/plan/generator.py

class PlanGenerator:
    """AI-powered plan generation."""

    def __init__(self, ai_client: AIClient) -> None:
        """Initialize with AI client."""

    def generate(
        self,
        context: PlanContext,
        tasks: list[Task],
        gap_analysis: GapAnalysis,
        start_date: date,
        days: int,
    ) -> tuple[list[DailyPlan], list[QuickAction]]:
        """Generate daily plans and quick actions.

        Args:
            context: Parsed planning context
            tasks: Tasks in planning window
            gap_analysis: Detected gaps
            start_date: First day of plan
            days: Planning horizon

        Returns:
            Tuple of (daily_plans, quick_actions)
        """
```

#### Output Formatter

```python
# src/jarvis/plan/formatter.py

def format_plan(plan: WeeklyPlan, console: Console) -> None:
    """Display plan with Rich formatting.

    Sections:
    1. Focus Summary (cyan box)
    2. Current Reality (white box)
    3. Gap Analysis (yellow box if gaps, green if none)
    4. Recommended Plan (per-day breakdown)
    5. Quick Actions (numbered commands)
    """

def format_focus_summary(focus: FocusSummary, console: Console) -> None:
    """Format focus summary section."""

def format_task_reality(reality: TaskReality, console: Console) -> None:
    """Format current reality section."""

def format_gap_analysis(gaps: GapAnalysis, console: Console) -> None:
    """Format gap analysis section."""

def format_daily_plans(plans: list[DailyPlan], console: Console) -> None:
    """Format recommended weekly plan section."""

def format_quick_actions(actions: list[QuickAction], console: Console) -> None:
    """Format quick actions section."""
```

---

## 5. Infrastructure & Deployment

### 5.1 Package Structure

No new dependencies required. The plan module uses existing dependencies:

| Dependency | Version | Usage |
|------------|---------|-------|
| click | ^8.1.0 | CLI framework [EXISTING] |
| rich | ^13.0 | Terminal formatting [EXISTING] |
| pydantic | ^2.0 | Data models [EXISTING] |
| anthropic | ^0.30 | AI client [EXISTING] |

### 5.2 File Persistence

**Plan files location:** `~/.jarvis/plans/`

```
~/.jarvis/
├── context/           [EXISTING]
├── config.yaml        [EXISTING]
└── plans/             [NEW]
    ├── 2026-01-26.md
    ├── 2026-01-19.md
    └── ...
```

**Plan file format:**

```markdown
# Weekly Plan - January 26, 2026

Generated at: 2026-01-26 09:15:00

## Focus Summary

**Mode:** 🚀 Shipping (until Jan 28)
**Primary Goal:** Submit GND paper to ICML 2026
**Decision Rule:** If it doesn't contribute to submission, defer it.

## Current Reality

24 tasks scheduled across 7 days

| Category | Tasks | Alignment |
|----------|-------|-----------|
| 🔬 Research/GND | 8 (33%) | ✓ Aligned |
| 💼 Business | 9 (38%) | ⚠️ Potential conflict |

**Alignment Score:** 45%

## Gap Analysis

⚠️ MISALIGNMENT DETECTED

**Goals without tasks:**
- Write paper abstract
- Generate figures from B1 results

**Focus conflicts:**
- Focus mode is "Shipping" but 38% business tasks

## Daily Plans

### Monday (Jan 26)
**Theme:** Deep work day
- ⚠️ 9 tasks (overloaded)
- → Defer 5 business research tasks
- → Protect 4-hour block for paper writing

[... continues ...]

## Quick Actions

1. `jarvis t "Write paper abstract" -d tuesday -p high -t gnd`
2. `jarvis t "Generate B1 figures" -d tuesday -t gnd`
```

---

## 6. Security Architecture

### 6.1 Data Handling

| Data Type | Storage | Transmission |
|-----------|---------|--------------|
| Context files | Local filesystem, user permissions | Not transmitted |
| Task data | Via adapter (encrypted) | HTTPS to KB backend |
| AI prompts | In-memory only | HTTPS to Anthropic API |
| Plan files | Local filesystem | Not transmitted |

### 6.2 API Key Management

[EXISTING] — Uses `ANTHROPIC_API_KEY` environment variable, same as other AI features.

### 6.3 No New Credentials

The plan command reuses existing authentication:
- AnyType: Local connection with approval code
- Notion: `JARVIS_NOTION_TOKEN` env var
- Anthropic: `ANTHROPIC_API_KEY` env var

---

## 7. Integration Architecture

### 7.1 Existing Component Integration

| Component | Integration Point | Usage |
|-----------|------------------|-------|
| `context_reader.py` | `load_context()` | Load raw context |
| `models/context.py` | `UserContext` | Raw context container |
| `services/task_service.py` | `TaskService.get_tasks()` | Retrieve tasks |
| `ai_client.py` | `AIClient` | Plan generation |
| `cli.py` | `cli.add_command()` | Register command |

### 7.2 Integration Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        jarvis plan CLI                               │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│ context_      │     │ TaskService   │     │ AIClient      │
│ reader.py     │     │ [EXISTING]    │     │ [EXISTING]    │
│ [EXISTING]    │     │               │     │               │
└───────┬───────┘     └───────┬───────┘     └───────┬───────┘
        │                     │                     │
        ▼                     ▼                     │
┌───────────────┐     ┌───────────────┐             │
│ UserContext   │     │ Adapter Layer │             │
│ [EXISTING]    │     │ [EXISTING]    │             │
└───────────────┘     └───────────────┘             │
                                                    │
                      ┌─────────────────────────────┘
                      │
                      ▼
              ┌───────────────┐
              │ Anthropic API │
              │ [EXTERNAL]    │
              └───────────────┘
```

---

## 8. Performance & Scalability

### 8.1 Performance Requirements

| Metric | Target | Implementation |
|--------|--------|----------------|
| Plan generation | < 5s | Parallel loading, efficient prompts |
| Context loading | < 500ms | Cached after first load |
| Task query | < 2s | Single adapter query |
| Memory usage | < 100MB | Streaming output, no large buffers |

### 8.2 Optimization Strategies

1. **Parallel Loading:**
   ```python
   # Load context and tasks concurrently
   async def _load_data(self):
       context, tasks = await asyncio.gather(
           self._load_context(),
           self._load_tasks(),
       )
       return context, tasks
   ```

   [INFERRED] MVP will use sequential loading for simplicity; async optimization deferred.

2. **AI Prompt Efficiency:**
   - Batch unclear tasks for single AI classification call
   - Use structured JSON output for reliable parsing
   - Limit daily plan generation to planning horizon

3. **Context Caching:**
   - Context parsed once per command invocation
   - No disk caching (context files may change)

### 8.3 Scalability Considerations

| Scenario | Limit | Handling |
|----------|-------|----------|
| Many tasks (100+) | Summarize categories | Group by project, show counts |
| Long horizon (30 days) | Limit detail | Only show per-week summaries beyond 7 days |
| Large context files | Truncate in prompt | Use first 2000 tokens per file |

---

## 9. Reliability & Operations

### 9.1 Error Handling

| Error | Response | User Message |
|-------|----------|--------------|
| KB connection failed | Graceful exit | "Cannot connect to [backend]. Is it running?" |
| Auth failed | Graceful exit | "Authentication failed. Check your credentials." |
| AI API error | Fallback to basic plan | "AI unavailable. Showing task summary only." |
| No context files | Degraded mode | "No context files found. Run `jarvis init` for full planning." |
| No tasks | Valid output | "No tasks scheduled in the next N days." |

### 9.2 Graceful Degradation

**Context Quality Levels:**

| Level | Condition | Behavior |
|-------|-----------|----------|
| `full` | 3+ context files with content | Full analysis, alignment, gaps |
| `partial` | 1-2 context files | Limited analysis, note missing |
| `minimal` | Context files exist but empty | Task-only analysis |
| `none` | No context files | Basic workload analysis |

### 9.3 Logging

[EXISTING] — Uses standard Python logging via `logging` module.

```python
import logging

logger = logging.getLogger(__name__)

# In service methods:
logger.debug("Loading context from %s", context_path)
logger.info("Generated plan with %d gaps", plan.gap_analysis.total_gaps)
logger.warning("AI fallback failed, using heuristic alignment")
```

---

## 10. Development Standards

### 10.1 Code Style

[EXISTING] — Follow existing Jarvis conventions:

- Python 3.11+ type hints
- Pydantic v2 models with dataclasses for simple data
- Click for CLI commands
- Rich for terminal output
- ruff for linting
- mypy for type checking

### 10.2 Testing Strategy

| Test Type | Coverage Target | Focus |
|-----------|-----------------|-------|
| Unit | 90% | Context parsing, alignment, gaps |
| Integration | 80% | Full plan generation with mocks |
| E2E | Key paths | CLI invocation, file save |

**Test File Structure:**

```
tests/
├── plan/
│   ├── __init__.py
│   ├── test_context_parser.py
│   ├── test_alignment.py
│   ├── test_gaps.py
│   ├── test_generator.py
│   ├── test_formatter.py
│   ├── test_service.py
│   └── test_cli.py
└── integration/
    └── test_plan_integration.py
```

### 10.3 Documentation

- Docstrings: Google style
- README: Update with plan command documentation
- `jarvis docs`: Auto-includes plan command

---

## 11. Implementation Roadmap

### 11.1 Work Items

| ID | Title | Priority | Dependencies | Est. Size |
|----|-------|----------|--------------|-----------|
| WORK-001 | Create plan module structure | P0 | None | S |
| WORK-002 | Implement domain models (plan.py) | P0 | WORK-001 | S |
| WORK-003 | Implement context_parser.py | P0 | WORK-002 | M |
| WORK-004 | Implement alignment.py | P0 | WORK-003 | M |
| WORK-005 | Implement gaps.py | P0 | WORK-004 | M |
| WORK-006 | Implement generator.py + prompts.py | P0 | WORK-005 | L |
| WORK-007 | Implement formatter.py | P0 | WORK-002 | M |
| WORK-008 | Implement service.py orchestration | P0 | WORK-003-007 | M |
| WORK-009 | Implement cli.py + command registration | P0 | WORK-008 | S |
| WORK-010 | Unit tests for context_parser | P0 | WORK-003 | M |
| WORK-011 | Unit tests for alignment | P0 | WORK-004 | M |
| WORK-012 | Unit tests for gaps | P0 | WORK-005 | M |
| WORK-013 | Unit tests for generator | P0 | WORK-006 | M |
| WORK-014 | Unit tests for formatter | P0 | WORK-007 | S |
| WORK-015 | Integration tests | P0 | WORK-010-014 | L |
| WORK-016 | Implement interactive.py (--interactive) | P1 | WORK-008 | M |
| WORK-017 | Implement --save flag | P1 | WORK-007 | S |
| WORK-018 | Add jarvis p alias | P1 | WORK-009 | S |
| WORK-019 | Tests for interactive mode | P1 | WORK-016 | M |
| WORK-020 | Tests for --save | P1 | WORK-017 | S |

### 11.2 Implementation Phases

**Phase 1: Core MVP (WORK-001 to WORK-015)**
- Basic `jarvis plan` command
- Context parsing, alignment, gap detection
- AI plan generation
- Rich output formatting
- Comprehensive unit tests

**Phase 2: Enhancements (WORK-016 to WORK-020)**
- Interactive Q&A mode
- Plan file persistence
- Command alias

### 11.3 Dependency Graph

```
WORK-001 (structure)
    │
    ▼
WORK-002 (models)
    │
    ├───────────────────────────────┐
    ▼                               ▼
WORK-003 (context_parser)     WORK-007 (formatter)
    │                               │
    ▼                               │
WORK-004 (alignment)                │
    │                               │
    ▼                               │
WORK-005 (gaps)                     │
    │                               │
    ▼                               │
WORK-006 (generator + prompts)      │
    │                               │
    └───────────┬───────────────────┘
                │
                ▼
        WORK-008 (service)
                │
                ▼
        WORK-009 (cli)
                │
    ┌───────────┴───────────┐
    │                       │
    ▼                       ▼
WORK-016 (interactive) WORK-017 (--save)
    │                       │
    ▼                       ▼
WORK-018 (alias)      WORK-020 (tests)
```

---

## 12. Appendices

### Appendix A: AI Prompt Templates

Located in `src/jarvis/plan/prompts.py`:

```python
PLAN_SYSTEM_PROMPT = """You are Jarvis, a proactive planning assistant.
Your job is to help users align their weekly schedule with their stated goals and priorities.

You will receive:
1. User context (goals, focus mode, constraints)
2. Scheduled tasks for the planning period
3. Gap analysis (goals without tasks, conflicts)

Generate a personalized weekly plan that:
- Respects the user's stated focus mode
- Suggests tasks for unaddressed goals
- Identifies days that need rebalancing
- Provides ready-to-run jarvis commands

Be concise and actionable. Do not lecture or over-explain."""

PLAN_USER_PROMPT_TEMPLATE = """
# Planning Request

## User Context
{user_context}

## Scheduled Tasks ({start_date} to {end_date})
{task_list}

## Gap Analysis
{gap_summary}

## Instructions

Generate a weekly plan with the following JSON structure:

```json
{{
  "daily_plans": [
    {{
      "date": "YYYY-MM-DD",
      "day_name": "Monday",
      "theme": "Deep work day",
      "suggestions": ["Task suggestion 1", "Task suggestion 2"],
      "actions": ["Defer X to next week", "Protect morning for Y"],
      "warnings": ["Day is overloaded with N tasks"]
    }}
  ],
  "quick_actions": [
    {{
      "command": "jarvis t \"Task title\" -d monday -p high -t tag",
      "description": "Add missing task for goal X"
    }}
  ]
}}
```

Provide 2-3 quick_actions for the most impactful missing tasks.
"""

ALIGNMENT_CLASSIFICATION_PROMPT = """Classify whether each task aligns with the user's current focus.

Current Focus: {focus_mode}
Primary Goal: {primary_goal}

Tasks to classify:
{task_list}

Respond with JSON:
```json
{{
  "classifications": [
    {{"task_id": "...", "aligned": true, "reason": "..."}}
  ]
}}
```
"""
```

### Appendix B: Context File Extraction Patterns

**goals.md patterns:**

```python
# Pattern 1: Header + bullets
## This Week
- Goal 1
- Goal 2

# Pattern 2: YAML frontmatter
---
this_week:
  - Goal 1
  - Goal 2
---

# Pattern 3: Numbered list
1. Goal 1
2. Goal 2
```

**focus.md patterns:**

```python
# Pattern 1: Bold keyword
**Current:** 🚀 Shipping

# Pattern 2: Header
## Mode: Shipping

# Pattern 3: Until date
Until: January 28, 2026
```

### Appendix C: Example Plan Output

```
╭──────────────────────────────────────────────╮
│ 🎯 Weekly Focus: ICML Deadline Crunch        │
╰──────────────────────────────────────────────╯

Mode: 🚀 Shipping (until Jan 28)
Primary Goal: Submit GND paper to ICML 2026
Decision Rule: If it doesn't contribute to submission, defer it.

╭──────────────────────────────────────────────╮
│ 📋 Scheduled Tasks (Jan 26 - Feb 1)          │
╰──────────────────────────────────────────────╯

24 tasks scheduled across 7 days

By Category:
  🔬 Research/GND:     8 tasks (33%) ✓ Aligned
  💼 Business:         9 tasks (38%) ⚠️ Potential conflict
  🔧 Maintenance:      4 tasks (17%)
  📝 Admin:            3 tasks (12%)

Alignment Score: 45%

╭──────────────────────────────────────────────╮
│ 🔍 Gap Analysis                              │
╰──────────────────────────────────────────────╯

⚠️  MISALIGNMENT DETECTED

Goals without tasks:
  • "Write paper abstract" — No task found
  • "Generate figures from B1 results" — No task found

Focus conflicts:
  • Focus mode is "Shipping" but 38% business tasks scheduled
  • Monday is overloaded (9 tasks)

╭──────────────────────────────────────────────╮
│ 📅 Recommended Weekly Plan                   │
╰──────────────────────────────────────────────╯

MONDAY (Jan 26) — Deep work day
  ⚠️ 9 tasks (overloaded)
  → Defer 5 business research tasks to next week
  → Protect 4-hour block for paper writing

TUESDAY (Jan 27) — Execution
  ✓ 3 tasks scheduled
  + Suggested: Write abstract
  + Suggested: Generate B1 figures

WEDNESDAY (Jan 28) — Deadline day
  ✓ 2 tasks scheduled
  → Final review and submit

... (continues for remaining days)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Quick Actions:
  [1] jarvis t "Write paper abstract" -d tuesday -p high -t gnd
  [2] jarvis t "Generate B1 figures" -d tuesday -t gnd
  [3] jarvis suggest --days 7  (to rebalance Monday)
```

---

## 13. Validation Checklist

### Completeness

- [x] Every feature in product_spec.md has an implementation path
- [x] All data entities defined with schemas
- [x] All APIs specified with request/response formats
- [x] All integrations have error handling defined
- [x] Security model covers auth, authorization, data protection
- [x] Deployment and infrastructure specified
- [x] Monitoring/logging defined
- [x] Development standards documented

### Quality

- [x] An unfamiliar engineer could implement from this doc
- [x] No ambiguous requirements
- [x] All `[INFERRED]` tags documented
- [x] Technology choices justified (reuse existing stack)
- [x] Diagrams included where helpful
- [x] Consistent terminology

### Pragmatism

- [x] Architecture matches scale (CLI extension, not microservice)
- [x] Work items realistic for scope
- [x] Tech choices align with existing codebase
- [x] MVP path clearly distinguished
