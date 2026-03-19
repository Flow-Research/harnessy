"""Task CLI commands."""

from datetime import date

import click
from rich.console import Console

from jarvis.adapters import AdapterRegistry
from jarvis.adapters.base import KnowledgeBaseAdapter
from jarvis.adapters.exceptions import (
    AuthError,
    ConnectionError as AdapterConnectionError,
    NotSupportedError,
)
from jarvis.models import Priority
from jarvis.state import save_selected_space
from jarvis.task.date_parser import parse_due_date
from jarvis.task.editor import EditorCancelledError, open_editor_for_description

console = Console()


def get_adapter(backend: str | None = None) -> KnowledgeBaseAdapter:
    """Get the configured adapter instance."""
    return AdapterRegistry.get_adapter(backend)


def require_capability(
    adapter: KnowledgeBaseAdapter,
    capability: str,
    feature_name: str | None = None,
) -> None:
    """Require that an adapter supports a capability, exit with message if not.

    Args:
        adapter: The adapter to check
        capability: The capability key (e.g., 'tasks', 'journal', 'search')
        feature_name: Human-readable feature name for error messages

    Raises:
        SystemExit: If the capability is not supported
    """
    if not adapter.capabilities.get(capability, False):
        name = feature_name or capability.replace("_", " ").title()
        console.print()
        console.print(f"[red]✗ {name} not available[/red]")
        console.print()
        console.print(
            f"[dim]The {adapter.backend_name} backend does not support {name.lower()}.[/dim]"
        )
        console.print("[dim]Try: jarvis status to see available capabilities.[/dim]")
        raise SystemExit(1)


@click.group()
def task_cli() -> None:
    """Manage tasks."""
    pass


@task_cli.command(name="create")
@click.argument("title", required=True)
@click.option("--due", "-d", "due_str", default=None, help="Due date (natural language or ISO)")
@click.option(
    "--priority",
    "-p",
    type=click.Choice(["high", "medium", "low"], case_sensitive=False),
    default=None,
    help="Task priority",
)
@click.option("--tag", "-t", "tags", multiple=True, help="Tags (repeatable)")
@click.option("--editor", "-e", is_flag=True, help="Open editor for description")
@click.option("--space", default=None, help="Override space selection")
@click.option("--backend", default=None, help="Backend to use (anytype, notion)")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def create_task(
    title: str,
    due_str: str | None,
    priority: str | None,
    tags: tuple[str, ...],
    editor: bool,
    space: str | None,
    backend: str | None,
    verbose: bool,
) -> None:
    """Create a new task.

    Examples:
        jarvis task create "Buy groceries" --due tomorrow
        jarvis task create "Review PR" -d friday -p high -t work
        jarvis task create "Q1 Planning" --due "next friday" -e
    """
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

    # Connect to backend
    try:
        adapter = get_adapter(backend)
        adapter.connect()
    except AdapterConnectionError as e:
        console.print(f"[red]✗ Connection error: {e}[/red]")
        raise SystemExit(1)
    except AuthError as e:
        console.print(f"[red]✗ Authentication error: {e}[/red]")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]✗ {e}[/red]")
        raise SystemExit(1)

    # Check required capabilities
    require_capability(adapter, "tasks", "Task management")

    # Get space
    space_id, space_name = _get_space(adapter, space)

    # Convert priority string to enum
    priority_enum = None
    if priority:
        priority_enum = Priority.from_string(priority)

    # Create task
    try:
        task = adapter.create_task(
            space_id=space_id,
            title=title,
            due_date=due_date,
            priority=priority_enum,
            tags=tag_list if tag_list else None,
            description=description,
        )

        _display_success(title, due_date, priority, tag_list, space_name, task.id, verbose)

    except NotSupportedError as e:
        console.print(f"[red]✗ Not supported: {e}[/red]")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]✗ Failed to create task: {e}[/red]")
        raise SystemExit(1)


def _get_space(adapter: KnowledgeBaseAdapter, space_arg: str | None) -> tuple[str, str]:
    """Get space ID from argument or saved selection."""
    from jarvis.cli import select_space

    spaces = adapter.list_spaces()

    if space_arg:
        for space in spaces:
            if space_arg.lower() in space.name.lower() or space_arg == space.id:
                save_selected_space(space.id)
                return space.id, space.name
        console.print(f"[yellow]Space '{space_arg}' not found.[/yellow]")
        console.print("[dim]Available spaces:[/dim]")
        for space in spaces:
            console.print(f"  • {space.name}")
        raise SystemExit(1)

    return select_space(adapter)


def _display_success(
    title: str,
    due_date: date | None,
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
