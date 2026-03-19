# Technical Specification: Jarvis Task Creation

**CLI-First Task Capture for AnyType**

---

## 1. Overview

### Purpose

This document provides a complete technical blueprint for implementing the `jarvis task` command, which enables users to create tasks directly in AnyType from the command line.

### Scope

- `jarvis task create` command with all options
- `jarvis t` alias for quick capture
- Natural language date parsing
- Editor integration for descriptions
- AnyType API integration for task creation
- Documentation updates

### Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Date parsing | `dateparser` library | Well-maintained (10k+ stars), handles natural language |
| Editor integration | `$EDITOR` / tempfile | Standard Unix pattern, already used in journal |
| Command structure | Click command group + alias | Matches existing `journal`/`j` pattern |
| Validation | Eager validation in CLI | Fail fast with helpful messages |
| AnyType integration | Extend `AnyTypeClient` | Consistent with existing patterns |

### References

- [Product Specification](./product_spec.md)
- [Brainstorm](./brainstorm.md)
- [Task Scheduler Technical Spec](../01_task-scheduler/technical_spec.md)

---

## 2. System Architecture

### Component Interaction

```
┌─────────────────────────────────────────────────────────────────┐
│                         jarvis task create                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  User Input                                                      │
│  jarvis t "Title" --due tomorrow -p high -t work                │
│       │                                                          │
│       ▼                                                          │
│  ┌──────────────────┐                                           │
│  │   CLI Layer      │  Parse args, validate inputs              │
│  │   (cli.py)       │                                           │
│  └────────┬─────────┘                                           │
│           │                                                      │
│           ▼                                                      │
│  ┌──────────────────┐     ┌──────────────────┐                  │
│  │   Date Parser    │     │   Editor         │                  │
│  │   (dateparser)   │     │   (tempfile)     │                  │
│  └────────┬─────────┘     └────────┬─────────┘                  │
│           │                        │                             │
│           └───────────┬────────────┘                             │
│                       ▼                                          │
│  ┌──────────────────────────────────────────┐                   │
│  │   Task Creation Service                   │                   │
│  │   (task/service.py)                       │                   │
│  │   - Validate inputs                       │                   │
│  │   - Build task data                       │                   │
│  │   - Call AnyType client                   │                   │
│  └────────────────────┬─────────────────────┘                   │
│                       │                                          │
│                       ▼                                          │
│  ┌──────────────────────────────────────────┐                   │
│  │   AnyType Client                          │                   │
│  │   (anytype_client.py)                     │                   │
│  │   - create_task() method                  │                   │
│  │   - API communication                     │                   │
│  └────────────────────┬─────────────────────┘                   │
│                       │                                          │
│                       ▼                                          │
│  ┌──────────────────────────────────────────┐                   │
│  │   AnyType Desktop (localhost:31009)       │                   │
│  └──────────────────────────────────────────┘                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### New Module Structure

```
jarvis/
├── task/                        # NEW: Task command module
│   ├── __init__.py
│   ├── cli.py                   # Click commands for task
│   ├── service.py               # Task creation business logic
│   ├── date_parser.py           # Date parsing utilities
│   └── editor.py                # Editor integration
├── cli.py                       # Updated: Register task commands
├── anytype_client.py            # Updated: Add create_task()
└── ...
```

### Integration Points

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `cli.py` | Modify | Register `task` command group and `t` alias |
| `anytype_client.py` | Modify | Add `create_task()` method |
| `task/` | New | New module for task creation |
| `_generate_docs()` | Modify | Add task commands to documentation |
| `CLAUDE.md` | Modify | Add task command examples |

---

## 3. Data Architecture

### Input Data Model

```python
from dataclasses import dataclass
from datetime import date


@dataclass
class TaskCreateInput:
    """Validated input for task creation."""

    title: str                      # Required, max 500 chars
    due_date: date | None = None    # Parsed from natural language
    priority: str | None = None     # high, medium, low
    tags: list[str] | None = None   # Deduplicated, max 20
    description: str | None = None  # From editor
    space_id: str | None = None     # Override or use saved
```

### AnyType Task Properties

| Property | AnyType Field | Format | Notes |
|----------|---------------|--------|-------|
| Title | `name` | string | Object name |
| Due Date | `due_date` | ISO 8601 date | `2025-01-25T00:00:00Z` |
| Priority | `priority` | select | Options: high, medium, low |
| Tags | `tag` | multi-select | Array of tag names |
| Description | body/content | markdown | Text blocks |

### Property Payload Structure

```python
# Example properties array for AnyType API
properties = [
    {
        "object": "property",
        "key": "due_date",
        "name": "Due date",
        "format": "date",
        "date": "2025-01-25T00:00:00Z"
    },
    {
        "object": "property",
        "key": "priority",
        "name": "Priority",
        "format": "select",
        "select": {"name": "high"}
    },
    {
        "object": "property",
        "key": "tag",
        "name": "Tag",
        "format": "multi_select",
        "multi_select": [
            {"name": "work"},
            {"name": "urgent"}
        ]
    }
]
```

---

## 4. API Specification

### CLI Interface

#### `jarvis task create`

```
Usage: jarvis task create [OPTIONS] TITLE

  Create a new task in AnyType.

Arguments:
  TITLE  Task title (required, max 500 characters)

Options:
  -d, --due TEXT        Due date (natural language or ISO format)
  -p, --priority TEXT   Priority: high, medium, low
  -t, --tag TEXT        Tag (repeatable for multiple tags)
  -e, --editor          Open editor for description
  --space TEXT          Override space selection
  -v, --verbose         Show detailed output
  --help                Show this message and exit

Examples:
  jarvis task create "Buy groceries" --due tomorrow
  jarvis task create "Review PR" -d friday -p high -t work
  jarvis task create "Q1 Planning" --due "next friday" -e
```

#### `jarvis t` (Alias)

```
Usage: jarvis t [OPTIONS] TITLE

  Quick task creation (alias for 'task create').

  Same options as 'jarvis task create'.
```

### Internal API

#### `AnyTypeClient.create_task()`

```python
def create_task(
    self,
    space_id: str,
    title: str,
    due_date: date | None = None,
    priority: str | None = None,
    tags: list[str] | None = None,
    description: str | None = None,
) -> str:
    """Create a task in AnyType.

    Args:
        space_id: AnyType space ID
        title: Task title (required)
        due_date: Optional due date
        priority: Optional priority (high/medium/low)
        tags: Optional list of tag names
        description: Optional task description (markdown)

    Returns:
        Created task object ID

    Raises:
        RuntimeError: If not authenticated or creation fails
        ValueError: If Task type not found in space
    """
```

#### `parse_due_date()`

```python
def parse_due_date(input_str: str) -> date | None:
    """Parse natural language date string.

    Args:
        input_str: Date string like "tomorrow", "next friday", "2025-02-15"

    Returns:
        Parsed date or None if parsing fails

    Examples:
        >>> parse_due_date("tomorrow")
        date(2025, 1, 25)
        >>> parse_due_date("next friday")
        date(2025, 1, 31)
        >>> parse_due_date("invalid")
        None
    """
```

#### `open_editor_for_description()`

```python
def open_editor_for_description(title: str) -> str | None:
    """Open editor for task description.

    Args:
        title: Task title (shown in template)

    Returns:
        Description text (stripped of comment lines) or None if cancelled

    Raises:
        EditorCancelledError: If user cancels (non-zero exit)
    """
```

---

## 5. Implementation Details

### 5.1 CLI Commands (`task/cli.py`)

```python
"""Task CLI commands."""

import click
from rich.console import Console

from datetime import date

from jarvis.anytype_client import AnyTypeClient
from jarvis.state import get_selected_space, save_selected_space
from jarvis.task.service import TaskService
from jarvis.task.date_parser import parse_due_date
from jarvis.task.editor import open_editor_for_description, EditorCancelledError

console = Console()


@click.group()
def task_cli():
    """Manage tasks in AnyType."""
    pass


@task_cli.command(name="create")
@click.argument("title", required=True)
@click.option("--due", "-d", "due_str", default=None, help="Due date")
@click.option(
    "--priority", "-p",
    type=click.Choice(["high", "medium", "low"], case_sensitive=False),
    default=None,
    help="Task priority"
)
@click.option("--tag", "-t", "tags", multiple=True, help="Tags (repeatable)")
@click.option("--editor", "-e", is_flag=True, help="Open editor for description")
@click.option("--space", default=None, help="Override space selection")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def create_task(
    title: str,
    due_str: str | None,
    priority: str | None,
    tags: tuple[str, ...],
    editor: bool,
    space: str | None,
    verbose: bool,
) -> None:
    """Create a new task in AnyType."""

    # Validate title
    if len(title) > 500:
        console.print("[red]✗ Title too long (max 500 chars)[/red]")
        raise SystemExit(1)

    # Parse due date
    due_date = None
    if due_str:
        due_date = parse_due_date(due_str)
        if due_date is None:
            console.print(f"[red]✗ Could not parse date: '{due_str}'[/red]")
            console.print("[dim]  Try: tomorrow, next friday, 2025-02-15[/dim]")
            raise SystemExit(1)

        # Warn if past date
        if due_date < date.today():
            console.print("[yellow]Note: Due date is in the past[/yellow]")

    # Process tags
    tag_list = list(set(tags))  # Deduplicate
    if len(tag_list) > 20:
        console.print("[red]✗ Too many tags (max 20)[/red]")
        raise SystemExit(1)

    # Get description from editor
    description = None
    if editor:
        try:
            description = open_editor_for_description(title)
        except EditorCancelledError:
            console.print("[dim]Task creation cancelled.[/dim]")
            raise SystemExit(0)

    # Connect to AnyType
    try:
        client = AnyTypeClient()
        client.connect()
    except RuntimeError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise SystemExit(1)

    # Get space
    space_id, space_name = _get_space(client, space)

    # Create task
    try:
        service = TaskService(client)
        task_id = service.create_task(
            space_id=space_id,
            title=title,
            due_date=due_date,
            priority=priority,
            tags=tag_list if tag_list else None,
            description=description,
        )

        _display_success(title, due_date, priority, tag_list, space_name, task_id, verbose)

    except Exception as e:
        console.print(f"[red]✗ Failed to create task: {e}[/red]")
        raise SystemExit(1)


def _get_space(client: AnyTypeClient, space_arg: str | None) -> tuple[str, str]:
    """Get space ID from argument or saved selection."""
    from jarvis.cli import select_space

    spaces = client.get_spaces()

    if space_arg:
        for space_id, space_name in spaces:
            if space_arg.lower() in space_name.lower() or space_arg == space_id:
                save_selected_space(space_id)
                return space_id, space_name
        console.print(f"[yellow]Space '{space_arg}' not found.[/yellow]")
        console.print("[dim]Available spaces:[/dim]")
        for _, name in spaces:
            console.print(f"  • {name}")
        raise SystemExit(1)

    return select_space(client)


def _display_success(
    title: str,
    due_date,
    priority: str | None,
    tags: list[str],
    space_name: str,
    task_id: str,
    verbose: bool,
) -> None:
    """Display success message."""
    if verbose:
        console.print("[green]✓ Task Created[/green]")
        console.print(f"  Title:    {title}")
        if due_date:
            console.print(f"  Due:      {due_date.strftime('%A, %B %d, %Y')}")
        if priority:
            console.print(f"  Priority: {priority.title()}")
        if tags:
            console.print(f"  Tags:     {', '.join(tags)}")
        console.print(f"  Space:    {space_name}")
        console.print(f"  ID:       {task_id[:12]}...")
    else:
        parts = [f'[green]✓ Created:[/green] "{title}"']
        extras = []
        if due_date:
            extras.append(f"due: {due_date.strftime('%b %d')}")
        if priority:
            extras.append(f"priority: {priority}")
        if tags:
            extras.append(f"tags: {', '.join(tags)}")
        if extras:
            parts.append(f"({', '.join(extras)})")
        console.print(" ".join(parts))
```

### 5.2 Date Parser (`task/date_parser.py`)

```python
"""Natural language date parsing."""

from datetime import date
from typing import Optional

import dateparser


def parse_due_date(input_str: str) -> Optional[date]:
    """Parse natural language date string to date object.

    Args:
        input_str: Date string like "tomorrow", "next friday", "2025-02-15"

    Returns:
        Parsed date or None if parsing fails
    """
    if not input_str or not input_str.strip():
        return None

    # Configure dateparser settings
    settings = {
        "PREFER_DATES_FROM": "future",  # "next friday" = upcoming friday
        "RETURN_AS_TIMEZONE_AWARE": False,
        "RELATIVE_BASE": date.today(),
    }

    try:
        result = dateparser.parse(input_str.strip(), settings=settings)
        if result:
            return result.date()
        return None
    except Exception:
        return None


def is_past_date(d: date) -> bool:
    """Check if date is in the past."""
    return d < date.today()
```

### 5.3 Editor Integration (`task/editor.py`)

```python
"""Editor integration for task descriptions."""

import os
import shlex
import subprocess
import tempfile
from pathlib import Path


class EditorCancelledError(Exception):
    """Raised when user cancels editor."""
    pass


def open_editor_for_description(title: str) -> str | None:
    """Open editor for task description.

    Args:
        title: Task title (shown in template)

    Returns:
        Description text (stripped of comment lines) or None if empty

    Raises:
        EditorCancelledError: If user cancels (non-zero exit or file deleted)
    """
    editor_env = os.environ.get("EDITOR", "vim")
    # Handle editors with arguments (e.g., "code --wait")
    editor_parts = shlex.split(editor_env)

    # Create template
    template = f"""# Task: {title}
# Add your description below. Lines starting with # are ignored.
# Save and close to create the task. Exit without saving to cancel.

"""

    # Write to temp file
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".md",
        delete=False,
        prefix="jarvis_task_",
    ) as f:
        f.write(template)
        temp_path = Path(f.name)

    try:
        # Open editor (handle editors with args like "code --wait")
        result = subprocess.run([*editor_parts, str(temp_path)])

        # Check for cancellation (non-zero exit)
        if result.returncode != 0:
            raise EditorCancelledError("Editor exited with non-zero status")

        # Check if file still exists
        if not temp_path.exists():
            raise EditorCancelledError("Temp file was deleted")

        # Read content
        content = temp_path.read_text()

        # Strip comment lines
        lines = [
            line for line in content.split("\n")
            if not line.strip().startswith("#")
        ]
        description = "\n".join(lines).strip()

        return description if description else None

    finally:
        # Clean up temp file
        if temp_path.exists():
            temp_path.unlink()
```

### 5.4 Task Service (`task/service.py`)

```python
"""Task creation service."""

from datetime import date
from typing import Optional

from jarvis.anytype_client import AnyTypeClient


class TaskService:
    """Service for task operations."""

    def __init__(self, client: AnyTypeClient):
        self._client = client

    def create_task(
        self,
        space_id: str,
        title: str,
        due_date: Optional[date] = None,
        priority: Optional[str] = None,
        tags: Optional[list[str]] = None,
        description: Optional[str] = None,
    ) -> str:
        """Create a task in AnyType.

        Returns:
            Task object ID
        """
        return self._client.create_task(
            space_id=space_id,
            title=title,
            due_date=due_date,
            priority=priority,
            tags=tags,
            description=description,
        )
```

### 5.5 AnyType Client Extension (`anytype_client.py`)

```python
# Add to AnyTypeClient class

def create_task(
    self,
    space_id: str,
    title: str,
    due_date: date | None = None,
    priority: str | None = None,
    tags: list[str] | None = None,
    description: str | None = None,
) -> str:
    """Create a task in AnyType.

    Args:
        space_id: AnyType space ID
        title: Task title
        due_date: Optional due date
        priority: Optional priority (high/medium/low)
        tags: Optional list of tags
        description: Optional description (markdown)

    Returns:
        Created task object ID

    Raises:
        RuntimeError: If not authenticated or creation fails
    """
    if not self._authenticated:
        raise RuntimeError("Not authenticated. Call connect() first.")

    try:
        from anytype.object import Object

        space = self._client.get_space(space_id)

        # Get Task type
        try:
            task_type = space.get_type_byname("Task")
        except ValueError:
            try:
                task_type = space.get_type_byname("task")
            except ValueError:
                raise RuntimeError("Task type not found in this space")

        # Create task object
        obj = Object(name=title, type=task_type)

        # Add description as text content
        if description:
            obj.add_text(description)

        # Create the object first
        created = space.create_object(obj)

        # Build properties for update
        properties = []

        # Add due_date property
        if due_date:
            date_iso = due_date.isoformat() + "T00:00:00Z"
            properties.append({
                "object": "property",
                "key": "due_date",
                "name": "Due date",
                "format": "date",
                "date": date_iso,
            })

        # Add priority property
        if priority:
            properties.append({
                "object": "property",
                "key": "priority",
                "name": "Priority",
                "format": "select",
                "select": {"name": priority.lower()},
            })

        # Add tags property
        if tags:
            properties.append({
                "object": "property",
                "key": "tag",
                "name": "Tag",
                "format": "multi_select",
                "multi_select": [{"name": t} for t in tags],
            })

        # Update with properties if any
        if properties:
            update_data = {
                "name": title,
                "properties": properties,
            }
            self._client._apiEndpoints.updateObject(space_id, created.id, update_data)

        return created.id

    except Exception as e:
        raise RuntimeError(f"Failed to create task: {e}")
```

### 5.6 CLI Registration (`cli.py`)

```python
# Add to cli.py

# Import task commands
from jarvis.task.cli import task_cli, create_task as task_create_cmd

# Register task command group
cli.add_command(task_cli, name="task")

# Register 't' as alias for 'task create'
cli.add_command(task_create_cmd, name="t")
```

### 5.7 Documentation Updates

#### `_generate_docs()` Addition

```python
# Add to the commands dictionary in _generate_docs()

"task": {
    "description": "Manage tasks in AnyType",
    "subcommands": {
        "create": {
            "description": "Create a new task",
            "options": {
                "TITLE": "Task title (required)",
                "--due, -d": "Due date (natural language or ISO)",
                "--priority, -p": "Priority: high, medium, low",
                "--tag, -t": "Tag (repeatable)",
                "--editor, -e": "Open editor for description",
                "--space": "Override space selection",
                "--verbose, -v": "Show detailed output",
            },
            "examples": [
                'jarvis task create "Buy groceries" --due tomorrow',
                'jarvis task create "Review PR" -d friday -p high -t work',
            ],
        },
    },
},
"t": {
    "description": "Quick task creation (alias for 'task create')",
    "options": {
        "TITLE": "Task title",
        "--due, -d": "Due date",
        "--priority, -p": "Priority",
        "--tag, -t": "Tags",
        "--editor, -e": "Open editor",
    },
    "examples": [
        'jarvis t "Quick note" --due tomorrow',
        'jarvis t "Urgent task" -p high -t urgent',
    ],
},
```

---

## 6. Dependencies

### New Dependency

```toml
# Add to pyproject.toml or requirements

[project.dependencies]
dateparser = "^1.2.0"
```

### dateparser Library

| Aspect | Details |
|--------|---------|
| Package | `dateparser` |
| Version | 1.2.0+ |
| Purpose | Natural language date parsing |
| Size | ~2MB (with dependencies) |
| License | BSD-3-Clause |
| Maintenance | Active (10k+ GitHub stars) |

---

## 7. Testing Strategy

### Unit Tests

#### Date Parser Tests (`tests/task/test_date_parser.py`)

```python
import pytest
from datetime import date, timedelta
from jarvis.task.date_parser import parse_due_date, is_past_date


class TestParseDueDate:
    def test_parse_tomorrow(self):
        result = parse_due_date("tomorrow")
        assert result == date.today() + timedelta(days=1)

    def test_parse_today(self):
        result = parse_due_date("today")
        assert result == date.today()

    def test_parse_iso_date(self):
        result = parse_due_date("2025-02-15")
        assert result == date(2025, 2, 15)

    def test_parse_natural_date(self):
        result = parse_due_date("feb 15")
        assert result is not None
        assert result.month == 2
        assert result.day == 15

    def test_parse_invalid_returns_none(self):
        assert parse_due_date("not a date") is None
        assert parse_due_date("") is None
        assert parse_due_date("   ") is None

    def test_parse_next_friday(self):
        result = parse_due_date("next friday")
        assert result is not None
        assert result.weekday() == 4  # Friday
        assert result > date.today()


class TestIsPastDate:
    def test_past_date(self):
        yesterday = date.today() - timedelta(days=1)
        assert is_past_date(yesterday) is True

    def test_today_not_past(self):
        assert is_past_date(date.today()) is False

    def test_future_not_past(self):
        tomorrow = date.today() + timedelta(days=1)
        assert is_past_date(tomorrow) is False
```

#### CLI Tests (`tests/task/test_cli.py`)

```python
import pytest
from click.testing import CliRunner
from jarvis.cli import cli


class TestTaskCreateCommand:
    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_create_requires_title(self, runner):
        result = runner.invoke(cli, ["task", "create"])
        assert result.exit_code != 0
        assert "Missing argument" in result.output

    def test_title_too_long(self, runner):
        long_title = "x" * 501
        result = runner.invoke(cli, ["task", "create", long_title])
        assert "Title too long" in result.output

    def test_invalid_priority(self, runner):
        result = runner.invoke(cli, ["task", "create", "Test", "-p", "invalid"])
        assert result.exit_code != 0

    def test_invalid_date(self, runner, mocker):
        # Mock AnyType connection
        mocker.patch("jarvis.task.cli.AnyTypeClient")
        result = runner.invoke(cli, ["task", "create", "Test", "-d", "notadate"])
        assert "Could not parse date" in result.output

    def test_t_alias_works(self, runner):
        result = runner.invoke(cli, ["t", "--help"])
        assert result.exit_code == 0
        assert "Quick task creation" in result.output or "TITLE" in result.output
```

#### Integration Tests (`tests/task/test_integration.py`)

```python
import pytest
from datetime import date, timedelta
from jarvis.anytype_client import AnyTypeClient


@pytest.mark.integration
class TestTaskCreationIntegration:
    """Integration tests requiring running AnyType."""

    @pytest.fixture
    def client(self):
        client = AnyTypeClient()
        client.connect()
        return client

    @pytest.fixture
    def space_id(self, client):
        return client.get_default_space()

    def test_create_simple_task(self, client, space_id):
        task_id = client.create_task(
            space_id=space_id,
            title="Test Task - Simple",
        )
        assert task_id is not None
        assert len(task_id) > 0

    def test_create_task_with_due_date(self, client, space_id):
        tomorrow = date.today() + timedelta(days=1)
        task_id = client.create_task(
            space_id=space_id,
            title="Test Task - With Due Date",
            due_date=tomorrow,
        )
        assert task_id is not None

    def test_create_task_with_all_fields(self, client, space_id):
        task_id = client.create_task(
            space_id=space_id,
            title="Test Task - Full",
            due_date=date.today() + timedelta(days=7),
            priority="high",
            tags=["test", "integration"],
            description="This is a test task description.",
        )
        assert task_id is not None

    def test_created_task_appears_in_search(self, client, space_id):
        """Verify created tasks are found by existing task search."""
        title = f"Unique Test Task {date.today().isoformat()}"
        client.create_task(
            space_id=space_id,
            title=title,
            due_date=date.today(),
        )

        # Search for tasks
        tasks = client.get_tasks_in_range(
            space_id=space_id,
            start=date.today(),
            end=date.today(),
        )

        task_names = [t.name for t in tasks]
        assert title in task_names
```

### Test Coverage Targets

| Component | Target Coverage |
|-----------|-----------------|
| `task/date_parser.py` | 100% |
| `task/editor.py` | 90% |
| `task/cli.py` | 85% |
| `task/service.py` | 100% |
| `anytype_client.create_task()` | 90% |

---

## 8. Error Handling

### Error Types

| Error | Cause | User Message | Exit Code |
|-------|-------|--------------|-----------|
| `TitleRequiredError` | Empty title | "Task title is required" | 1 |
| `TitleTooLongError` | Title > 500 chars | "Title too long (max 500 chars)" | 1 |
| `DateParseError` | Invalid date string | "Could not parse date: '{input}'" | 1 |
| `InvalidPriorityError` | Unknown priority | "Invalid priority. Use: high, medium, low" | 1 |
| `TooManyTagsError` | Tags > 20 | "Too many tags (max 20)" | 1 |
| `EditorCancelledError` | User cancelled editor | "Task creation cancelled." | 0 |
| `ConnectionError` | AnyType not running | "Cannot connect to AnyType..." | 1 |
| `SpaceNotFoundError` | Invalid space | "Space '{name}' not found..." | 1 |
| `TaskTypeNotFoundError` | No Task type in space | "Task type not found in this space" | 1 |

### Error Handling Flow

```python
try:
    # Validation
    if not title:
        raise TitleRequiredError()
    if len(title) > 500:
        raise TitleTooLongError()

    # Date parsing
    if due_str:
        due_date = parse_due_date(due_str)
        if not due_date:
            raise DateParseError(due_str)

    # Create task
    task_id = service.create_task(...)

except (TitleRequiredError, TitleTooLongError, DateParseError) as e:
    console.print(f"[red]✗ {e.message}[/red]")
    raise SystemExit(1)
except EditorCancelledError:
    console.print("[dim]Task creation cancelled.[/dim]")
    raise SystemExit(0)
except RuntimeError as e:
    console.print(f"[red]✗ {e}[/red]")
    raise SystemExit(1)
```

---

## 9. Implementation Roadmap

### Work Items

| ID | Task | Priority | Dependencies | Estimate |
|----|------|----------|--------------|----------|
| WI-01 | Add `dateparser` dependency | P0 | None | 0.5h |
| WI-02 | Implement `date_parser.py` | P0 | WI-01 | 1h |
| WI-03 | Implement `editor.py` | P0 | None | 1h |
| WI-04 | Add `create_task()` to AnyTypeClient | P0 | None | 2h |
| WI-05 | Implement `task/service.py` | P0 | WI-04 | 0.5h |
| WI-06 | Implement `task/cli.py` | P0 | WI-02, WI-03, WI-05 | 2h |
| WI-07 | Register commands in `cli.py` | P0 | WI-06 | 0.5h |
| WI-08 | Unit tests for date parser | P0 | WI-02 | 1h |
| WI-09 | Unit tests for CLI | P0 | WI-06 | 1.5h |
| WI-10 | Integration tests | P1 | WI-04 | 1h |
| WI-11 | Update `_generate_docs()` | P1 | WI-07 | 0.5h |
| WI-12 | Update `CLAUDE.md` | P1 | WI-07 | 0.5h |

### Dependency Graph

```
WI-01 ─► WI-02 ─┐
                ├─► WI-06 ─► WI-07 ─► WI-11
WI-03 ──────────┤               │
                │               └─► WI-12
WI-04 ─► WI-05 ─┘
    │
    └─► WI-10

WI-02 ─► WI-08
WI-06 ─► WI-09
```

### Build Sequence

**Phase 1: Core Infrastructure**
1. WI-01: Add dateparser dependency
2. WI-02: Date parser implementation
3. WI-03: Editor integration
4. WI-04: AnyType client create_task()

**Phase 2: Service Layer**
5. WI-05: Task service

**Phase 3: CLI**
6. WI-06: CLI commands
7. WI-07: Register commands

**Phase 4: Testing**
8. WI-08: Date parser tests
9. WI-09: CLI tests
10. WI-10: Integration tests

**Phase 5: Documentation**
11. WI-11: Update docs generator
12. WI-12: Update CLAUDE.md

---

## 10. Appendices

### A. Full CLI Help Output

```
$ jarvis task --help
Usage: jarvis task [OPTIONS] COMMAND [ARGS]...

  Manage tasks in AnyType.

Options:
  --help  Show this message and exit.

Commands:
  create  Create a new task in AnyType.

$ jarvis task create --help
Usage: jarvis task create [OPTIONS] TITLE

  Create a new task in AnyType.

Options:
  -d, --due TEXT              Due date (natural language or ISO format)
  -p, --priority [high|medium|low]
                              Task priority
  -t, --tag TEXT              Tag (repeatable for multiple tags)
  -e, --editor                Open editor for description
  --space TEXT                Override space selection
  -v, --verbose               Show detailed output
  --help                      Show this message and exit.

$ jarvis t --help
Usage: jarvis t [OPTIONS] TITLE

  Quick task creation (alias for 'task create').

Options:
  -d, --due TEXT              Due date
  -p, --priority [high|medium|low]
                              Priority
  -t, --tag TEXT              Tags
  -e, --editor                Open editor
  --space TEXT                Space
  -v, --verbose               Verbose
  --help                      Show this message and exit.
```

### B. Example Sessions

**Quick capture:**
```bash
$ jarvis t "Buy groceries" --due tomorrow
✓ Created: "Buy groceries" (due: Jan 25)

$ jarvis t "Review PR #234" -d friday -p high -t work
✓ Created: "Review PR #234" (due: Jan 31, priority: high, tags: work)
```

**Full creation with editor:**
```bash
$ jarvis task create "Q1 Planning Document" --due "jan 31" -p high -t planning -e
# [Editor opens with template]
# [User writes description, saves, closes]
✓ Created: "Q1 Planning Document" (due: Jan 31, priority: high, tags: planning)
```

**Verbose output:**
```bash
$ jarvis t "Important task" --due tomorrow -p high -v
✓ Task Created
  Title:    Important task
  Due:      Saturday, January 25, 2025
  Priority: High
  Space:    Personal
  ID:       bafyreib...
```

---

## 11. Review Notes

### Technical Review Summary

**Review Date:** 2025-01-24
**Perspectives:** 6 (Backend, Security, DevOps, Data, Integration, Engineering Manager)

### Issues Found & Resolved

| Issue | Resolution |
|-------|------------|
| Editor command with spaces in `$EDITOR` | Added `shlex.split()` for robust parsing |
| Import inside function body | Moved `date` import to module top |

### Minor Items Deferred to Implementation

| Item | Rationale |
|------|-----------|
| TaskService as thin wrapper | Enables future testing/mocking; acceptable |
| Task type case sensitivity | Documented behavior; handles common cases |
| Two API calls for object creation | AnyType API constraint; optimization for future |

### Approval

- ✅ Principal Backend Engineer: Approved
- ✅ Security Architect: Approved
- ✅ DevOps/SRE Lead: Approved
- ✅ Database/Data Engineer: Approved
- ✅ Integration Specialist: Approved
- ✅ Engineering Manager: Approved

---

*Technical Specification v1.1*
*Created: 2025-01-24*
*Reviewed: 2025-01-24 (6-perspective review complete)*
*Status: Ready for Implementation*
