# Technical Specification: Jarvis

**AnyType Intelligent Task Scheduler**

---

## 1. Overview

### Purpose

This document provides a complete technical blueprint for implementing Jarvis, an intelligent CLI-based task scheduler that integrates with AnyType via its API and uses Claude for AI-powered scheduling reasoning.

### Scope

- MVP implementation: analyze, suggest, apply commands
- AnyType API integration
- Context-aware AI reasoning
- Local execution with approval workflow

### Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Language | Python 3.11+ | Type hints, modern async, ecosystem maturity |
| Package Manager | uv | Fast dependency resolution, reproducible builds |
| CLI Framework | Click + Rich | Mature, composable, beautiful terminal output |
| AI Provider | Anthropic Claude | Strong reasoning, structured output, cost-effective |
| Data Validation | Pydantic v2 | Type safety, serialization, settings management |
| Local Storage | JSON files | Simple, human-readable, no external dependencies |

### References

- [AnyType Developer Portal](https://developers.anytype.io/)
- [anytype-client Python Library](https://pypi.org/project/anytype-client/)
- [Product Specification](./product_spec.md)

---

## 2. System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                           User's Machine                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐     ┌──────────────────────────────────────────┐ │
│  │   AnyType    │     │                 Jarvis                    │ │
│  │   Desktop    │◄───►│  ┌──────────┐  ┌──────────┐  ┌────────┐  │ │
│  │              │     │  │   CLI    │  │  Engine  │  │   AI   │  │ │
│  │  localhost:  │     │  │  Layer   │──│  Core    │──│ Client │  │ │
│  │    31009     │     │  └──────────┘  └──────────┘  └────────┘  │ │
│  └──────────────┘     │       │              │            │       │ │
│                       │       ▼              ▼            ▼       │ │
│  ┌──────────────┐     │  ┌──────────┐  ┌──────────┐  ┌────────┐  │ │
│  │   context/   │◄────│  │  State   │  │ AnyType  │  │Anthropic│ │ │
│  │   (prefs)    │     │  │ Manager  │  │  Client  │  │  API   │  │ │
│  └──────────────┘     │  └──────────┘  └──────────┘  └────────┘  │ │
│                       └──────────────────────────────────────────┘ │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Overview

| Component | Responsibility |
|-----------|---------------|
| **CLI Layer** | Command parsing, user interaction, output formatting |
| **Engine Core** | Scheduling logic, workload analysis, suggestion generation |
| **AI Client** | Claude API integration, prompt management, response parsing |
| **AnyType Client** | API communication, authentication, task CRUD |
| **State Manager** | Local persistence, suggestion storage, learnings |
| **Context Reader** | Parse and interpret user preference files |

### Module Structure

```
jarvis/
├── __init__.py
├── __main__.py              # Entry point: python -m jarvis
├── cli/
│   ├── __init__.py
│   ├── main.py              # Click application root
│   ├── commands/
│   │   ├── __init__.py
│   │   ├── analyze.py       # jarvis analyze
│   │   ├── suggest.py       # jarvis suggest
│   │   ├── apply.py         # jarvis apply
│   │   ├── status.py        # jarvis status
│   │   └── context.py       # jarvis context
│   └── formatters/
│       ├── __init__.py
│       ├── analysis.py      # Rich formatting for analysis output
│       └── suggestions.py   # Rich formatting for suggestions
├── core/
│   ├── __init__.py
│   ├── engine.py            # Main scheduling engine
│   ├── analyzer.py          # Workload analysis logic
│   ├── scheduler.py         # Suggestion generation algorithms
│   └── models.py            # Core domain models
├── anytype/
│   ├── __init__.py
│   ├── client.py            # AnyType API wrapper
│   ├── auth.py              # Authentication handling
│   ├── models.py            # AnyType-specific data models
│   └── exceptions.py        # AnyType-related errors
├── ai/
│   ├── __init__.py
│   ├── client.py            # Anthropic API wrapper
│   ├── prompts.py           # Prompt templates
│   └── parser.py            # Response parsing and validation
├── context/
│   ├── __init__.py
│   ├── reader.py            # Context file parser
│   └── models.py            # Context data structures
├── state/
│   ├── __init__.py
│   ├── manager.py           # State persistence
│   ├── suggestions.py       # Suggestion storage
│   └── learnings.py         # Learning system storage
├── config/
│   ├── __init__.py
│   └── settings.py          # Pydantic settings
└── utils/
    ├── __init__.py
    ├── dates.py             # Date manipulation utilities
    └── logging.py           # Logging configuration
```

---

## 3. Data Architecture

### Domain Models

#### Task (from AnyType)

```python
from datetime import date, datetime
from pydantic import BaseModel, Field
from typing import Optional

class Task(BaseModel):
    """Represents a task from AnyType."""

    id: str = Field(description="AnyType object ID")
    space_id: str = Field(description="AnyType space ID")
    name: str = Field(description="Task title")
    scheduled_date: Optional[date] = Field(default=None, description="When task is scheduled")
    due_date: Optional[date] = Field(default=None, description="Hard deadline")
    priority: Optional[str] = Field(default=None, description="Priority level if set")
    tags: list[str] = Field(default_factory=list, description="Tags including bar_movement")
    is_done: bool = Field(default=False, description="Completion status")
    created_at: datetime
    updated_at: datetime

    @property
    def is_moveable(self) -> bool:
        """Task can be rescheduled if not tagged bar_movement."""
        return "bar_movement" not in self.tags

    @property
    def has_deadline(self) -> bool:
        return self.due_date is not None
```

#### WorkloadAnalysis

```python
from datetime import date
from pydantic import BaseModel

class DayWorkload(BaseModel):
    """Workload for a single day."""

    date: date
    total_tasks: int
    moveable_tasks: int
    immovable_tasks: int
    task_ids: list[str]

    @property
    def status(self) -> str:
        if self.total_tasks > 6:
            return "overloaded"
        elif self.total_tasks < 3:
            return "light"
        return "balanced"

class WorkloadAnalysis(BaseModel):
    """Complete workload analysis for date range."""

    start_date: date
    end_date: date
    days: list[DayWorkload]
    total_moveable: int
    total_immovable: int

    @property
    def variance(self) -> float:
        """Standard deviation of daily task counts."""
        counts = [d.total_tasks for d in self.days]
        mean = sum(counts) / len(counts)
        return (sum((x - mean) ** 2 for x in counts) / len(counts)) ** 0.5
```

#### Suggestion

```python
from datetime import date, datetime
from enum import Enum
from pydantic import BaseModel

class SuggestionStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    APPLIED = "applied"
    FAILED = "failed"

class Suggestion(BaseModel):
    """A proposed task rescheduling."""

    id: str = Field(description="Unique suggestion ID")
    task_id: str
    task_name: str
    current_date: date
    proposed_date: date
    reasoning: str = Field(description="AI-generated explanation")
    confidence: float = Field(ge=0, le=1, description="Confidence score 0-1")
    status: SuggestionStatus = SuggestionStatus.PENDING
    created_at: datetime
    resolved_at: Optional[datetime] = None

    def accept(self) -> None:
        self.status = SuggestionStatus.ACCEPTED
        self.resolved_at = datetime.now()

    def reject(self) -> None:
        self.status = SuggestionStatus.REJECTED
        self.resolved_at = datetime.now()
```

#### Context Models

```python
from pydantic import BaseModel
from typing import Optional

class TimePreference(BaseModel):
    """When certain task types should be scheduled."""
    task_pattern: str  # e.g., "deep work", "admin", "meetings"
    preferred_time: str  # e.g., "morning", "afternoon", "end of day"
    preferred_days: Optional[list[str]] = None  # e.g., ["friday"]

class Constraint(BaseModel):
    """Hard scheduling constraint."""
    description: str
    rule_type: str  # "no_tasks", "max_tasks", "blocked_time"
    parameters: dict

class UserContext(BaseModel):
    """Aggregated user context from all files."""

    preferences: list[TimePreference]
    patterns: list[str]  # Raw pattern descriptions
    constraints: list[Constraint]
    priorities: list[str]  # Priority hierarchy
    learnings: list[str]  # Historical learnings

    def to_prompt_context(self) -> str:
        """Format context for AI prompt."""
        sections = []

        if self.preferences:
            sections.append("## Preferences\n" + "\n".join(
                f"- {p.task_pattern}: {p.preferred_time}" +
                (f" on {', '.join(p.preferred_days)}" if p.preferred_days else "")
                for p in self.preferences
            ))

        if self.constraints:
            sections.append("## Constraints\n" + "\n".join(
                f"- {c.description}" for c in self.constraints
            ))

        if self.priorities:
            sections.append("## Priorities (high to low)\n" + "\n".join(
                f"{i+1}. {p}" for i, p in enumerate(self.priorities)
            ))

        if self.learnings:
            sections.append("## Learned Preferences\n" + "\n".join(
                f"- {l}" for l in self.learnings[-10:]  # Last 10 learnings
            ))

        return "\n\n".join(sections)
```

### State Storage Schema

**Location:** `~/.jarvis/` (XDG_DATA_HOME compliant)

```
~/.jarvis/
├── config.json              # User configuration
├── suggestions/
│   └── pending.json         # Current pending suggestions
├── history/
│   └── YYYY-MM-DD.json      # Historical suggestion records
└── cache/
    └── tasks.json           # Cached task data (TTL: 5 min)
```

#### pending.json Schema

```json
{
  "generated_at": "2025-01-23T07:00:00Z",
  "space_id": "bafyrei...",
  "suggestions": [
    {
      "id": "sug_001",
      "task_id": "obj_abc123",
      "task_name": "Write API docs",
      "current_date": "2025-01-27",
      "proposed_date": "2025-01-29",
      "reasoning": "Balances workload; Monday is overloaded",
      "confidence": 0.85,
      "status": "pending",
      "created_at": "2025-01-23T07:00:00Z"
    }
  ]
}
```

---

## 4. API Specification

### AnyType API Integration

**Base URL:** `http://localhost:31009`
**API Version:** `2025-11-08`

#### Authentication Flow

```python
# Authentication is handled by anytype-client library
# First-time use requires 4-digit code confirmation in AnyType app

from anytype import Anytype

async def authenticate() -> Anytype:
    """Initialize and authenticate AnyType client."""
    client = Anytype()
    await client.auth()  # Triggers code popup on first use
    return client
```

#### Key Endpoints Used

| Operation | Method | Endpoint |
|-----------|--------|----------|
| List spaces | GET | `/v1/spaces` |
| Search tasks | POST | `/v1/spaces/{space_id}/search` |
| Get task | GET | `/v1/spaces/{space_id}/objects/{id}` |
| Update task | PATCH | `/v1/spaces/{space_id}/objects/{id}` |

#### Search Request Schema

```python
class TaskSearchRequest(BaseModel):
    """Request body for searching tasks."""
    query: str = ""
    types: list[str] = ["task"]
    sort: dict = Field(default_factory=lambda: {
        "direction": "asc",
        "property": "scheduled_date"
    })

# Example: Find all tasks in date range
search_payload = {
    "query": "",
    "types": ["task"],
    "sort": {"direction": "asc", "property": "scheduled_date"}
}
```

#### Update Task Request

```python
class TaskUpdateRequest(BaseModel):
    """Request body for updating task scheduled date."""
    properties: dict

# Example: Reschedule task
update_payload = {
    "properties": {
        "scheduled_date": "2025-01-29"  # ISO format date
    }
}
```

### Internal API (CLI Commands)

#### jarvis analyze

```
Usage: jarvis analyze [OPTIONS]

Options:
  --days INTEGER  Number of days to analyze (default: 14)
  --space TEXT    AnyType space name (default: first space)
  --json          Output as JSON instead of formatted
  --help          Show this message and exit.

Output: WorkloadAnalysis rendered with Rich
```

#### jarvis suggest

```
Usage: jarvis suggest [OPTIONS]

Options:
  --days INTEGER      Number of days to consider (default: 14)
  --space TEXT        AnyType space name
  --max INTEGER       Maximum suggestions to generate (default: 10)
  --min-confidence FLOAT  Minimum confidence threshold (default: 0.5)
  --no-ai             Use algorithmic balancing only
  --json              Output as JSON
  --help              Show this message and exit.

Output: List[Suggestion] rendered with Rich, saved to pending.json
```

#### jarvis apply

```
Usage: jarvis apply [OPTIONS]

Options:
  --all           Accept all pending suggestions
  --interactive   Review each suggestion (default)
  --dry-run       Show what would be applied without making changes
  --help          Show this message and exit.

Output: Application results, updates pending.json and history
```

---

## 5. Infrastructure & Deployment

### Development Environment

```toml
# pyproject.toml
[project]
name = "jarvis-scheduler"
version = "0.1.0"
description = "Intelligent task scheduler for AnyType"
requires-python = ">=3.11"
dependencies = [
    "anytype-client>=0.2.0",
    "anthropic>=0.40.0",
    "click>=8.1.0",
    "rich>=13.0.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "httpx>=0.27.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.0.0",
    "ruff>=0.4.0",
    "mypy>=1.10.0",
]

[project.scripts]
jarvis = "jarvis.cli.main:cli"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.mypy]
python_version = "3.11"
strict = true
```

### Installation

```bash
# From PyPI (future)
uv pip install jarvis-scheduler

# From source
git clone https://github.com/user/jarvis-scheduler
cd jarvis-scheduler
uv pip install -e ".[dev]"
```

### Configuration

**Environment Variables:**

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude API key for AI reasoning |
| `JARVIS_CONTEXT_PATH` | No | Override default context folder (default: `./context`) |
| `JARVIS_DATA_PATH` | No | Override default data folder (default: `~/.jarvis`) |
| `JARVIS_LOG_LEVEL` | No | Logging level (default: `INFO`) |

**Settings Model:**

```python
from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    """Jarvis configuration settings."""

    anthropic_api_key: str
    context_path: Path = Path("./context")
    data_path: Path = Path.home() / ".jarvis"

    # Analysis defaults
    default_days: int = 14
    overload_threshold: int = 6
    underload_threshold: int = 3

    # AI settings
    ai_model: str = "claude-sonnet-4-20250514"
    ai_max_tokens: int = 2000
    ai_temperature: float = 0.3

    # Suggestion settings
    max_suggestions: int = 10
    min_confidence: float = 0.5

    class Config:
        env_prefix = "JARVIS_"
        env_file = ".env"
```

---

## 6. Security Architecture

### API Key Management

```python
import keyring
from pathlib import Path

class SecretManager:
    """Secure storage for API keys."""

    SERVICE_NAME = "jarvis-scheduler"

    @classmethod
    def store_api_key(cls, key_name: str, value: str) -> None:
        """Store API key in system keychain."""
        keyring.set_password(cls.SERVICE_NAME, key_name, value)

    @classmethod
    def get_api_key(cls, key_name: str) -> str | None:
        """Retrieve API key from keychain or environment."""
        # Try environment first
        import os
        env_value = os.environ.get(f"JARVIS_{key_name.upper()}")
        if env_value:
            return env_value

        # Fall back to keychain
        return keyring.get_password(cls.SERVICE_NAME, key_name)
```

### Data Privacy

| Data Type | Storage | Sent Externally |
|-----------|---------|-----------------|
| Task names & dates | Local only | Yes (to Claude for reasoning) |
| Task content/body | Never read | No |
| User context | Local only | Yes (to Claude for reasoning) |
| API keys | Keychain/env | Respective API only |
| Suggestions | Local JSON | No |

### Security Considerations

1. **Minimal data exposure**: Only task names, dates, and tags sent to Claude
2. **No cloud backend**: All processing local except AI reasoning
3. **No persistent tokens**: AnyType auth is session-based
4. **Audit trail**: All suggestions logged with timestamps

---

## 7. Integration Architecture

### AnyType Client Wrapper

```python
from anytype import Anytype
from typing import AsyncIterator
from .models import Task

class AnyTypeClient:
    """Wrapper for AnyType API operations."""

    def __init__(self):
        self._client: Anytype | None = None
        self._authenticated = False

    async def connect(self) -> None:
        """Initialize and authenticate."""
        self._client = Anytype()
        await self._client.auth()
        self._authenticated = True

    async def get_spaces(self) -> list[dict]:
        """List all accessible spaces."""
        if not self._authenticated:
            raise RuntimeError("Not authenticated")
        return await self._client.get_spaces()

    async def get_tasks(
        self,
        space_id: str,
        start_date: date,
        end_date: date
    ) -> AsyncIterator[Task]:
        """Fetch tasks within date range."""
        space = await self._client.get_space(space_id)

        # Search for tasks with scheduled dates
        results = await space.search(
            query="",
            types=["task"],
            sort={"direction": "asc", "property": "scheduled_date"}
        )

        for obj in results:
            task = self._map_to_task(obj, space_id)
            if task.scheduled_date:
                if start_date <= task.scheduled_date <= end_date:
                    yield task

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
            logger.error(f"Failed to update task {task_id}: {e}")
            return False

    def _map_to_task(self, obj: Any, space_id: str) -> Task:
        """Map AnyType object to Task model."""
        return Task(
            id=obj.id,
            space_id=space_id,
            name=obj.name,
            scheduled_date=self._parse_date(obj.scheduled_date),
            due_date=self._parse_date(obj.due_date),
            priority=getattr(obj, "priority", None),
            tags=getattr(obj, "tags", []) or [],
            is_done=getattr(obj, "done", False),
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )
```

### Claude AI Integration

```python
from anthropic import Anthropic
from .prompts import SCHEDULING_SYSTEM_PROMPT, SUGGESTION_PROMPT

class AIClient:
    """Claude API wrapper for scheduling reasoning."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.client = Anthropic(api_key=api_key)
        self.model = model

    async def generate_suggestions(
        self,
        tasks: list[Task],
        analysis: WorkloadAnalysis,
        context: UserContext,
        max_suggestions: int = 10
    ) -> list[Suggestion]:
        """Generate rescheduling suggestions using AI reasoning."""

        # Build the prompt
        prompt = SUGGESTION_PROMPT.format(
            task_list=self._format_tasks(tasks),
            workload_analysis=self._format_analysis(analysis),
            user_context=context.to_prompt_context(),
            max_suggestions=max_suggestions,
            today=date.today().isoformat()
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            temperature=0.3,
            system=SCHEDULING_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )

        return self._parse_suggestions(response.content[0].text, tasks)

    def _format_tasks(self, tasks: list[Task]) -> str:
        """Format tasks for prompt."""
        lines = []
        for t in tasks:
            status = "🔒" if not t.is_moveable else "📦"
            deadline = f" (due: {t.due_date})" if t.due_date else ""
            lines.append(
                f"{status} [{t.scheduled_date}] {t.name}{deadline}"
            )
        return "\n".join(lines)
```

### Prompt Templates

```python
SCHEDULING_SYSTEM_PROMPT = """You are Jarvis, an intelligent task scheduling assistant.

Your role is to analyze task schedules and suggest optimizations that:
1. Balance workload across days (primary goal)
2. Respect task priorities and deadlines
3. Honor user preferences and patterns
4. Never suggest moving tasks tagged 'bar_movement'

When making suggestions:
- Provide clear, specific reasoning for each move
- Consider the user's context and preferences
- Assign confidence scores (0.0-1.0) based on certainty
- Prefer smaller moves over dramatic reorganization

Output your suggestions in this exact JSON format:
{
  "suggestions": [
    {
      "task_name": "Task name exactly as shown",
      "current_date": "YYYY-MM-DD",
      "proposed_date": "YYYY-MM-DD",
      "reasoning": "Brief explanation",
      "confidence": 0.85
    }
  ]
}"""

SUGGESTION_PROMPT = """## Current Date
{today}

## Tasks (next {days} days)
{task_list}

## Workload Analysis
{workload_analysis}

## User Context
{user_context}

## Request
Analyze this schedule and suggest up to {max_suggestions} task moves that would improve workload balance while respecting the user's preferences and constraints.

Remember:
- 🔒 tasks are immovable (bar_movement tag)
- 📦 tasks can be rescheduled
- Never move tasks past their due dates
- Prefer moving tasks to underutilized days
"""
```

---

## 8. Performance & Scalability

### Performance Targets

| Operation | Target | Measurement |
|-----------|--------|-------------|
| Analyze (100 tasks) | <2s | Wall clock time |
| Suggest (with AI) | <8s | Including API latency |
| Apply single task | <1s | AnyType API round-trip |

### Optimization Strategies

#### Caching

```python
from datetime import datetime, timedelta
from functools import lru_cache
import json

class TaskCache:
    """Cache task data to reduce API calls."""

    TTL = timedelta(minutes=5)

    def __init__(self, cache_path: Path):
        self.cache_path = cache_path
        self._data: dict | None = None
        self._loaded_at: datetime | None = None

    def get(self, space_id: str) -> list[Task] | None:
        """Get cached tasks if still valid."""
        if self._is_stale():
            return None

        if self._data and self._data.get("space_id") == space_id:
            return [Task(**t) for t in self._data["tasks"]]
        return None

    def set(self, space_id: str, tasks: list[Task]) -> None:
        """Cache tasks."""
        self._data = {
            "space_id": space_id,
            "tasks": [t.model_dump() for t in tasks],
            "cached_at": datetime.now().isoformat()
        }
        self._loaded_at = datetime.now()
        self._write_cache()

    def _is_stale(self) -> bool:
        if not self._loaded_at:
            return True
        return datetime.now() - self._loaded_at > self.TTL
```

#### Batch Operations

```python
async def apply_suggestions_batch(
    client: AnyTypeClient,
    suggestions: list[Suggestion]
) -> dict[str, bool]:
    """Apply multiple suggestions with batched API calls."""
    results = {}

    # Group by space to minimize context switches
    by_space = defaultdict(list)
    for s in suggestions:
        task = await get_task(s.task_id)  # From cache
        by_space[task.space_id].append(s)

    for space_id, space_suggestions in by_space.items():
        for suggestion in space_suggestions:
            success = await client.update_task_date(
                space_id,
                suggestion.task_id,
                suggestion.proposed_date
            )
            results[suggestion.id] = success

    return results
```

### Scalability Considerations

| Scenario | Limit | Handling |
|----------|-------|----------|
| Tasks per space | 1000+ | Pagination, date range filtering |
| Suggestions per run | 50 max | AI token limits, user cognitive load |
| Context file size | 100KB | Truncate oldest learnings |

---

## 9. Reliability & Operations

### Error Handling Strategy

```python
from enum import Enum
from typing import TypeVar, Generic

T = TypeVar("T")

class ErrorCode(str, Enum):
    ANYTYPE_NOT_RUNNING = "anytype_not_running"
    AUTH_FAILED = "auth_failed"
    API_ERROR = "api_error"
    AI_ERROR = "ai_error"
    NO_TASKS = "no_tasks"
    CONTEXT_ERROR = "context_error"

class JarvisError(Exception):
    """Base exception for Jarvis errors."""

    def __init__(self, code: ErrorCode, message: str, recoverable: bool = True):
        self.code = code
        self.message = message
        self.recoverable = recoverable
        super().__init__(message)

class Result(Generic[T]):
    """Result type for operations that can fail."""

    def __init__(
        self,
        value: T | None = None,
        error: JarvisError | None = None
    ):
        self._value = value
        self._error = error

    @property
    def is_ok(self) -> bool:
        return self._error is None

    def unwrap(self) -> T:
        if self._error:
            raise self._error
        return self._value  # type: ignore

    @classmethod
    def ok(cls, value: T) -> "Result[T]":
        return cls(value=value)

    @classmethod
    def err(cls, error: JarvisError) -> "Result[T]":
        return cls(error=error)
```

### Fallback Behavior

```python
async def generate_suggestions_with_fallback(
    tasks: list[Task],
    analysis: WorkloadAnalysis,
    context: UserContext,
    ai_client: AIClient | None
) -> list[Suggestion]:
    """Generate suggestions with AI, fall back to algorithmic."""

    if ai_client:
        try:
            return await ai_client.generate_suggestions(
                tasks, analysis, context
            )
        except Exception as e:
            logger.warning(f"AI suggestion failed, using fallback: {e}")

    # Algorithmic fallback: simple workload balancing
    return generate_algorithmic_suggestions(tasks, analysis)

def generate_algorithmic_suggestions(
    tasks: list[Task],
    analysis: WorkloadAnalysis
) -> list[Suggestion]:
    """Basic workload balancing without AI."""
    suggestions = []

    # Find overloaded and light days
    overloaded = [d for d in analysis.days if d.status == "overloaded"]
    light = [d for d in analysis.days if d.status == "light"]

    if not overloaded or not light:
        return []

    # Move tasks from overloaded to light days
    for over_day in overloaded:
        moveable_ids = [
            tid for tid in over_day.task_ids
            if get_task(tid).is_moveable
        ]

        for task_id in moveable_ids[:2]:  # Max 2 per day
            if not light:
                break

            target_day = light[0]
            task = get_task(task_id)

            suggestions.append(Suggestion(
                id=generate_id(),
                task_id=task_id,
                task_name=task.name,
                current_date=over_day.date,
                proposed_date=target_day.date,
                reasoning="Algorithmic balancing: moving from overloaded to light day",
                confidence=0.6,
                status=SuggestionStatus.PENDING,
                created_at=datetime.now()
            ))

            # Update light day count
            if target_day.total_tasks + 1 >= 3:
                light.pop(0)

    return suggestions
```

### Logging

```python
import logging
from rich.logging import RichHandler

def setup_logging(level: str = "INFO") -> None:
    """Configure logging with rich formatting."""

    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True)]
    )

    # Reduce noise from HTTP libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
```

---

## 10. Development Standards

### Code Style

- **Formatter:** Ruff (replaces Black + isort)
- **Linter:** Ruff
- **Type Checker:** mypy (strict mode)
- **Line Length:** 100 characters

### Testing Strategy

```python
# tests/conftest.py
import pytest
from datetime import date, datetime
from jarvis.core.models import Task, WorkloadAnalysis, DayWorkload

@pytest.fixture
def sample_tasks() -> list[Task]:
    """Generate sample tasks for testing."""
    return [
        Task(
            id="task_1",
            space_id="space_1",
            name="Write docs",
            scheduled_date=date(2025, 1, 27),
            due_date=None,
            tags=[],
            is_done=False,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        ),
        Task(
            id="task_2",
            space_id="space_1",
            name="Team meeting",
            scheduled_date=date(2025, 1, 27),
            tags=["bar_movement"],
            is_done=False,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        ),
    ]

@pytest.fixture
def mock_anytype_client(mocker):
    """Mock AnyType client for unit tests."""
    client = mocker.Mock()
    client.get_tasks = mocker.AsyncMock(return_value=[])
    client.update_task_date = mocker.AsyncMock(return_value=True)
    return client
```

### Test Coverage Targets

| Component | Target |
|-----------|--------|
| Core engine | 90% |
| CLI commands | 80% |
| AnyType client | 70% (integration) |
| AI client | 60% (mocked) |

### Git Workflow

```bash
# Branch naming
feature/add-confidence-scoring
fix/anytype-auth-timeout
refactor/extract-scheduler-module

# Commit format
feat(cli): add --json output option to analyze command
fix(anytype): handle connection timeout gracefully
docs(readme): add installation instructions
```

---

## 11. Implementation Roadmap

### Phase 1: Foundation (MVP Core)

**Duration:** [INFERRED: 1-2 weeks]

| Task | Priority | Dependencies |
|------|----------|--------------|
| Project scaffolding (uv, structure) | P0 | None |
| AnyType client wrapper | P0 | None |
| Core models (Task, Suggestion) | P0 | None |
| Basic CLI skeleton | P0 | Models |
| Context file reader | P0 | None |

**Deliverable:** Can read tasks from AnyType and parse context files

### Phase 2: Analysis & Display

**Duration:** [INFERRED: 1 week]

| Task | Priority | Dependencies |
|------|----------|--------------|
| Workload analyzer | P0 | AnyType client |
| `jarvis analyze` command | P0 | Analyzer |
| Rich formatting for analysis | P1 | CLI |
| `jarvis status` command | P1 | Config |

**Deliverable:** Working `jarvis analyze` command with formatted output

### Phase 3: Suggestions

**Duration:** [INFERRED: 1-2 weeks]

| Task | Priority | Dependencies |
|------|----------|--------------|
| Claude AI client | P0 | None |
| Prompt engineering | P0 | AI client |
| Algorithmic fallback | P1 | Analyzer |
| `jarvis suggest` command | P0 | AI client |
| Suggestion persistence | P0 | Models |

**Deliverable:** Working `jarvis suggest` with AI-powered recommendations

### Phase 4: Apply & Polish

**Duration:** [INFERRED: 1 week]

| Task | Priority | Dependencies |
|------|----------|--------------|
| `jarvis apply` command | P0 | Suggestions |
| Interactive approval flow | P0 | CLI |
| Error handling & recovery | P0 | All |
| `jarvis context` command | P1 | Context reader |
| Documentation | P1 | All |

**Deliverable:** Complete MVP ready for testing

### Phase 5: Testing & Refinement

**Duration:** [INFERRED: 1 week]

| Task | Priority | Dependencies |
|------|----------|--------------|
| Unit test suite | P0 | All modules |
| Integration tests | P1 | AnyType client |
| Prompt tuning | P1 | User feedback |
| Performance optimization | P2 | Benchmarks |

**Deliverable:** Production-ready MVP

---

## 12. Appendices

### A. File Structure (Complete)

```
jarvis-scheduler/
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── release.yml
├── src/
│   └── jarvis/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli/
│       ├── core/
│       ├── anytype/
│       ├── ai/
│       ├── context/
│       ├── state/
│       ├── config/
│       └── utils/
├── tests/
│   ├── conftest.py
│   ├── unit/
│   │   ├── test_analyzer.py
│   │   ├── test_scheduler.py
│   │   └── test_context.py
│   └── integration/
│       └── test_anytype_client.py
├── context/                    # User's context (not in package)
│   ├── preferences.md
│   ├── patterns.md
│   ├── constraints.md
│   ├── priorities.md
│   └── learnings.md
├── pyproject.toml
├── README.md
├── LICENSE
└── .env.example
```

### B. Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | - | Claude API key |
| `JARVIS_CONTEXT_PATH` | No | `./context` | Context files location |
| `JARVIS_DATA_PATH` | No | `~/.jarvis` | Local data storage |
| `JARVIS_LOG_LEVEL` | No | `INFO` | Logging verbosity |
| `JARVIS_AI_MODEL` | No | `claude-sonnet-4-20250514` | Claude model |
| `JARVIS_DEFAULT_DAYS` | No | `14` | Default analysis window |

### C. Error Codes Reference

| Code | Message | Recovery |
|------|---------|----------|
| `anytype_not_running` | AnyType desktop must be running | Start AnyType app |
| `auth_failed` | Authentication failed | Re-authenticate |
| `api_error` | AnyType API error | Retry or check AnyType |
| `ai_error` | Claude API error | Falls back to algorithmic |
| `no_tasks` | No moveable tasks found | Check filters |
| `context_error` | Failed to read context | Check file permissions |

### D. CLI Help Text

```
$ jarvis --help

Usage: jarvis [OPTIONS] COMMAND [ARGS]...

  Jarvis - Intelligent task scheduler for AnyType

  Analyzes your task schedule and suggests optimizations
  to balance workload while respecting your preferences.

Options:
  --version  Show version and exit.
  --help     Show this message and exit.

Commands:
  analyze  Analyze current schedule workload.
  apply    Apply pending suggestions to AnyType.
  context  Show loaded context summary.
  status   Show Jarvis configuration and status.
  suggest  Generate rescheduling suggestions.
```

---

*Technical Specification v1.0*
*Created: 2025-01-23*
*Status: Ready for implementation*
