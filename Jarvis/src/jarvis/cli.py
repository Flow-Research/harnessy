"""CLI interface for Jarvis task scheduler."""

from datetime import date, datetime, timedelta, timezone

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from jarvis.adapters import AdapterRegistry
from jarvis.adapters.base import KnowledgeBaseAdapter
from jarvis.adapters.exceptions import (
    AuthError,
    ConnectionError as AdapterConnectionError,
    NotFoundError,
    NotSupportedError,
)
from jarvis.analyzer import analyze_workload
from jarvis.calendar.providers import GWSProvider
from jarvis.config import load_config, validate_config
from jarvis.context_reader import load_context
from jarvis.models import AppliedBlockResult, PlanApplyResult, Suggestion, WorkloadAnalysis
from jarvis.plans import list_plan_ids, load_plan, load_plan_apply, save_plan, save_plan_apply
from jarvis.services import (
    build_calendar_plan,
    build_reorganize_suggestions,
    parse_work_hours_from_context,
)
from jarvis.state import (
    clear_suggestions,
    get_selected_space,
    load_suggestions,
    save_selected_space,
    save_suggestions,
)

console = Console()


def get_adapter(backend: str | None = None) -> KnowledgeBaseAdapter:
    """Get the configured adapter instance.

    Args:
        backend: Optional backend name override

    Returns:
        Configured adapter instance

    Raises:
        AdapterNotFoundError: If the requested backend is not available
    """
    return AdapterRegistry.get_adapter(backend)


def check_capability(
    adapter: KnowledgeBaseAdapter,
    capability: str,
    feature_name: str | None = None,
) -> bool:
    """Check if adapter supports a capability.

    Args:
        adapter: The adapter to check
        capability: The capability key (e.g., 'tasks', 'journal', 'search')
        feature_name: Human-readable feature name for error messages

    Returns:
        True if capability is supported, False otherwise
    """
    return adapter.capabilities.get(capability, False)


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
    if not check_capability(adapter, capability):
        name = feature_name or capability.replace("_", " ").title()
        console.print()
        console.print(f"[red]✗ {name} not available[/red]")
        console.print()
        console.print(
            f"[dim]The {adapter.backend_name} backend does not support {name.lower()}.[/dim]"
        )
        console.print()

        # Suggest alternative backends that might have this capability
        _suggest_alternatives(capability)
        raise SystemExit(1)


def _suggest_alternatives(capability: str) -> None:
    """Suggest alternative backends that support a capability."""
    from jarvis.config import VALID_BACKENDS

    alternatives = []

    # Known capability support by backend
    capability_by_backend = {
        "anytype": {"tasks", "journal", "tags", "search", "relations", "priorities", "due_dates"},
        "notion": {"tasks", "journal", "tags", "priorities", "due_dates"},
    }

    for backend, caps in capability_by_backend.items():
        if capability in caps:
            alternatives.append(backend)

    if alternatives:
        console.print(f"[dim]Backends that support this feature: {', '.join(alternatives)}[/dim]")
        console.print("[dim]Switch with: jarvis config backend <name>[/dim]")


def select_space(adapter: KnowledgeBaseAdapter) -> tuple[str, str]:
    """Prompt user to select a space or use saved selection.

    Args:
        adapter: Connected adapter instance

    Returns:
        Tuple of (space_id, space_name)
    """
    spaces = adapter.list_spaces()

    # Check if we have a saved space selection
    saved_space_id = get_selected_space()
    if saved_space_id:
        # Verify the saved space still exists
        for space in spaces:
            if space.id == saved_space_id:
                return space.id, space.name

    # If only one space, use it automatically
    if len(spaces) == 1:
        space = spaces[0]
        save_selected_space(space.id)
        return space.id, space.name

    # Prompt user to select a space
    console.print()
    console.print("[bold]Select a space to work with:[/bold]")
    console.print()

    for i, space in enumerate(spaces, 1):
        console.print(f"  [cyan]{i}[/cyan]. {space.name}")

    console.print()
    choice = Prompt.ask(
        "Enter number",
        choices=[str(i) for i in range(1, len(spaces) + 1)],
        default="1",
    )

    selected_idx = int(choice) - 1
    space = spaces[selected_idx]

    # Save selection for future use
    save_selected_space(space.id)
    console.print(f"[dim]Using space: {space.name}[/dim]")
    console.print()

    return space.id, space.name


@click.group()
@click.version_option(version="0.1.0", prog_name="jarvis")
def cli() -> None:
    """Jarvis - AI-powered personal assistant for AnyType.

    Features:
    - Task scheduling: Analyze and optimize your schedule
    - Journaling: AI-powered freeform journaling

    Use 'jarvis <command> --help' for more information.
    """
    pass


# Register journal commands
from jarvis.journal.cli import journal_cli, write_entry  # noqa: E402

cli.add_command(journal_cli)

# Create 'j' as an alias for 'journal write'
cli.add_command(write_entry, name="j")

# Register task commands
from jarvis.task.cli import create_task, task_cli  # noqa: E402

cli.add_command(task_cli, name="task")

# Create 't' as an alias for 'task create'
cli.add_command(create_task, name="t")

# Register plan commands
from jarvis.plan.cli import plan_command, plan_alias  # noqa: E402

cli.add_command(plan_command, name="plan")

# Create 'p' as an alias for 'plan'
cli.add_command(plan_alias, name="p")

# Register note command
from jarvis.note import note_command  # noqa: E402

cli.add_command(note_command, name="note")

# Create 'n' as alias for 'note'
cli.add_command(note_command, name="n")

# Register object commands
from jarvis.object.cli import object_cli, quick_object  # noqa: E402

cli.add_command(object_cli, name="object")

# Create 'o' as a quick alias for object lookup/edit
cli.add_command(quick_object, name="o")

# Register reading list commands
from jarvis.reading_list.cli import quick_reading_list, reading_list_cli  # noqa: E402

cli.add_command(reading_list_cli, name="reading-list")

# Create 'rl' as a quick alias for reading-list organize
cli.add_command(quick_reading_list, name="rl")

# Register Android APK commands
from jarvis.android.cli import android_cli, quick_apk  # noqa: E402

cli.add_command(android_cli, name="android")

# Create 'apk' as a quick alias for 'android run'
cli.add_command(quick_apk, name="apk")

# Register content pipeline commands
from jarvis.content.cli import content_cli  # noqa: E402

cli.add_command(content_cli, name="content")

# ============================================================================
# Init and Context Commands
# ============================================================================


@cli.command()
@click.option("--global", "global_", is_flag=True, help="Initialize global context only")
@click.option("--folder", is_flag=True, help="Initialize folder context only")
def init(global_: bool, folder: bool) -> None:
    """Initialize Jarvis in current directory or globally.

    Creates the .jarvis/ directory structure with context files.

    Examples:
        jarvis init           # Initialize both global and folder
        jarvis init --global  # Initialize global ~/.jarvis/context/
        jarvis init --folder  # Initialize folder ./.jarvis/context/
    """
    from jarvis.context_reader import (
        CONTEXT_FILES,
        ensure_folder_context_dir,
        ensure_global_context_dir,
    )

    # Default: init both if no flags specified
    if not global_ and not folder:
        global_ = True
        folder = True

    created_files: list[str] = []

    if global_:
        global_dir = ensure_global_context_dir()
        console.print(f"[dim]Global context: {global_dir}[/dim]")

        for filename in CONTEXT_FILES:
            filepath = global_dir / filename
            if not filepath.exists():
                # Create with template content
                content = _get_context_template(filename, is_global=True)
                filepath.write_text(content, encoding="utf-8")
                created_files.append(f"~/.jarvis/context/{filename}")

    if folder:
        folder_dir = ensure_folder_context_dir()
        console.print(f"[dim]Folder context: {folder_dir}[/dim]")

        for filename in CONTEXT_FILES:
            filepath = folder_dir / filename
            if not filepath.exists():
                content = _get_context_template(filename, is_global=False)
                filepath.write_text(content, encoding="utf-8")
                created_files.append(f".jarvis/context/{filename}")

    if created_files:
        console.print()
        console.print("[green]Created context files:[/green]")
        for f in created_files:
            console.print(f"  • {f}")
    else:
        console.print("[yellow]All context files already exist.[/yellow]")

    console.print()
    console.print(
        Panel(
            "[bold]Jarvis initialized![/bold]\n\n"
            "Edit the context files to customize your preferences:\n"
            "• [cyan]~/.jarvis/context/[/cyan] - Global preferences (all projects)\n"
            "• [cyan].jarvis/context/[/cyan] - Project-specific overrides\n\n"
            "[dim]Tip: Use {{global}} in folder files to include global content[/dim]",
            title="✓ Setup Complete",
            border_style="green",
        )
    )


def _get_context_template(filename: str, is_global: bool) -> str:
    """Get template content for a context file.

    Args:
        filename: Name of the context file
        is_global: Whether this is for global context

    Returns:
        Template content string
    """
    templates = {
        "preferences.md": """# Preferences

<!-- Your scheduling and work preferences -->

## Work Hours
- Preferred working hours: 9 AM - 6 PM
- Break preferences:

## Task Preferences
- Maximum tasks per day:
- Preferred task duration:
""",
        "patterns.md": """# Work Patterns

<!-- Your typical work patterns and habits -->

## Weekly Patterns
- Monday:
- Friday:

## Energy Patterns
- High energy times:
- Low energy times:
""",
        "constraints.md": """# Constraints

<!-- Hard constraints that cannot be violated -->

## Time Constraints
- No meetings before:
- No work after:

## Other Constraints
-
""",
        "priorities.md": """# Priorities

<!-- Current priority order for tasks and projects -->

## High Priority
1.

## Medium Priority
1.

## Low Priority
1.
""",
        "goals.md": """# Goals

<!-- Short and long-term goals -->

## This Week
-

## This Month
-

## This Quarter
-
""",
        "projects.md": """# Projects

<!-- Active projects and their details -->

## Current Projects
-

## Upcoming Projects
-
""",
        "recurring.md": """# Recurring Tasks

<!-- Regular tasks that repeat -->

## Daily
-

## Weekly
-

## Monthly
-
""",
        "focus.md": """# Focus Areas

<!-- What you want to focus on right now -->

## Current Focus
-

## Avoid/Minimize
-
""",
        "blockers.md": """# Blockers

<!-- Current blockers and dependencies -->

## Active Blockers
-

## Waiting On
-
""",
        "calendar.md": """# Calendar

<!-- Important dates and events -->

## Upcoming Events
-

## Deadlines
-
""",
        "delegation.md": """# Delegation

<!-- Tasks that can be delegated -->

## Can Delegate
-

## Delegated (Waiting)
-
""",
        "decisions.md": """# Decisions

<!-- Pending decisions and considerations -->

## Need to Decide
-

## Recently Decided
-
""",
    }

    content = templates.get(filename, f"# {filename.replace('.md', '').title()}\n\n")

    if not is_global:
        # Add note about global inheritance for folder files
        header = f"""# {filename.replace(".md", "").title()} (Project-Specific)

<!-- This file overrides global settings for this project.
     Use {{{{global}}}} to include your global {filename} content.

     Example:
     {{{{global}}}}

     ## Project-Specific Additions
     - ...
-->

"""
        return header

    return content


@cli.group()
def context() -> None:
    """Manage Jarvis context files.

    Context files store your preferences, patterns, and constraints.
    They are loaded from two levels:
    - Global: ~/.jarvis/context/ (applies to all projects)
    - Folder: ./.jarvis/context/ (project-specific overrides)
    """
    pass


@context.command(name="status")
def context_status() -> None:
    """Show context loading status."""
    from jarvis.context_reader import (
        get_context_locations,
        get_context_summary,
        load_context,
    )

    locations = get_context_locations()
    ctx = load_context()
    summary = get_context_summary(ctx)

    console.print()
    console.print("[bold]Context Locations[/bold]")
    console.print(f"  Global: {locations['global'] or '[dim]not initialized[/dim]'}")
    console.print(f"  Folder: {locations['folder'] or '[dim]not initialized[/dim]'}")

    console.print()
    console.print("[bold]Loaded Context Files[/bold]")
    for filename, has_content in summary.items():
        status = "[green]✓[/green]" if has_content else "[dim]○[/dim]"
        console.print(f"  {status} {filename}")

    loaded_count = sum(1 for v in summary.values() if v)
    console.print()
    console.print(f"[dim]{loaded_count}/{len(summary)} files have content[/dim]")


@context.command(name="edit")
@click.argument("file", required=False)
@click.option("--global", "global_", is_flag=True, help="Edit global context file")
def context_edit(file: str | None, global_: bool) -> None:
    """Open a context file in your editor.

    FILE is the context file name (e.g., 'preferences', 'goals').
    """
    import os
    import subprocess

    from jarvis.context_reader import (
        CONTEXT_FILES,
        FOLDER_CONTEXT_DIR,
        GLOBAL_CONTEXT_DIR,
    )

    # Determine which directory to use
    if global_:
        base_dir = GLOBAL_CONTEXT_DIR
        location = "global"
    else:
        base_dir = FOLDER_CONTEXT_DIR
        location = "folder"

    if not base_dir.exists():
        console.print(f"[yellow]Context directory not initialized. Run 'jarvis init'.[/yellow]")
        return

    if file is None:
        # Show available files
        console.print(f"[bold]Available {location} context files:[/bold]")
        for f in CONTEXT_FILES:
            filepath = base_dir / f
            status = "[green]✓[/green]" if filepath.exists() else "[dim]○[/dim]"
            console.print(f"  {status} {f.replace('.md', '')}")
        console.print()
        console.print("[dim]Usage: jarvis context edit <filename>[/dim]")
        return

    # Normalize filename
    if not file.endswith(".md"):
        file = f"{file}.md"

    filepath = base_dir / file

    if not filepath.exists():
        # Create it first
        content = _get_context_template(file, is_global=global_)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content, encoding="utf-8")

    # Open in editor
    editor = os.environ.get("EDITOR", "vim")
    try:
        subprocess.run([editor, str(filepath)], check=True)
    except FileNotFoundError:
        console.print(f"[red]Editor '{editor}' not found. Set $EDITOR environment variable.[/red]")
    except subprocess.CalledProcessError:
        console.print("[red]Editor exited with error.[/red]")


# ============================================================================
# Configuration Commands
# ============================================================================


@cli.group()
def config() -> None:
    """Manage Jarvis configuration.

    Configuration is stored in ~/.jarvis/config.yaml and controls:
    - Which backend to use (anytype, notion)
    - Backend-specific settings
    - Analytics preferences
    """
    pass


@config.command(name="show")
def config_show() -> None:
    """Show current configuration."""
    from jarvis.config import (
        get_backend_token,
        get_config_path,
        load_config,
        redact_token,
        validate_config,
    )

    config_path = get_config_path()
    console.print()
    console.print(f"[bold]Configuration File[/bold]: {config_path}")
    console.print()

    if not config_path.exists():
        console.print("[yellow]No configuration file found.[/yellow]")
        console.print("[dim]Run 'jarvis config init' to create one.[/dim]")
        return

    try:
        cfg = load_config(reload=True)
    except Exception as e:
        console.print(f"[red]Failed to load config: {e}[/red]")
        return

    # Show active backend
    console.print("[bold]Active Backend[/bold]")
    console.print(f"  {cfg.active_backend}")
    console.print()

    # Show backend configurations
    console.print("[bold]Backend Configurations[/bold]")

    # AnyType
    console.print("  [cyan]anytype[/cyan]")
    if cfg.backends.anytype.default_space_id:
        console.print(f"    default_space_id: {cfg.backends.anytype.default_space_id}")
    else:
        console.print("    [dim](using defaults)[/dim]")

    # Notion
    console.print("  [cyan]notion[/cyan]")
    if cfg.backends.notion:
        console.print(f"    workspace_id: {cfg.backends.notion.workspace_id}")
        console.print(f"    task_database_id: {cfg.backends.notion.task_database_id}")
        console.print(f"    journal_database_id: {cfg.backends.notion.journal_database_id}")
        # Check for token
        try:
            token = get_backend_token("notion")
            console.print(f"    token: {redact_token(token)} [green]✓[/green]")
        except Exception:
            console.print("    token: [red]not set[/red]")
    else:
        console.print("    [dim](not configured)[/dim]")

    # Validation
    console.print()
    issues = validate_config()
    if issues:
        console.print("[bold yellow]Configuration Issues[/bold yellow]")
        for issue in issues:
            console.print(f"  [yellow]⚠[/yellow] {issue}")
    else:
        console.print("[green]✓ Configuration valid[/green]")


@config.command(name="init")
@click.option("--force", "-f", is_flag=True, help="Overwrite existing configuration")
def config_init(force: bool) -> None:
    """Initialize configuration file with defaults."""
    from jarvis.config import ConfigError, get_config_path, init_config

    config_path = get_config_path()

    if config_path.exists() and not force:
        console.print(f"[yellow]Configuration already exists: {config_path}[/yellow]")
        console.print("[dim]Use --force to overwrite.[/dim]")
        return

    try:
        path = init_config(force=force)
        console.print(f"[green]✓ Created configuration: {path}[/green]")
        console.print()
        console.print("[dim]Edit the file to configure your backends.[/dim]")
    except ConfigError as e:
        console.print(f"[red]✗ {e}[/red]")


@config.command(name="backend")
@click.argument("name", required=False)
def config_backend(name: str | None) -> None:
    """Show or set the active backend.

    Without arguments, shows the current backend.
    With NAME argument, switches to that backend.

    Examples:
        jarvis config backend           # Show current
        jarvis config backend anytype   # Switch to AnyType
        jarvis config backend notion    # Switch to Notion
    """
    from jarvis.config import (
        ConfigError,
        VALID_BACKENDS,
        load_config,
        set_active_backend,
        validate_config,
    )

    if name is None:
        # Show current backend
        cfg = load_config()
        console.print(f"Active backend: [cyan]{cfg.active_backend}[/cyan]")
        console.print()
        console.print("[dim]Available backends:[/dim]")
        for backend in sorted(VALID_BACKENDS):
            marker = "→" if backend == cfg.active_backend else " "
            console.print(f"  {marker} {backend}")
        return

    # Set new backend
    try:
        cfg = set_active_backend(name)
        console.print(f"[green]✓ Switched to {name} backend[/green]")

        # Validate the new configuration
        issues = validate_config()
        if issues:
            console.print()
            console.print("[yellow]Configuration warnings:[/yellow]")
            for issue in issues:
                console.print(f"  [yellow]⚠[/yellow] {issue}")
    except ConfigError as e:
        console.print(f"[red]✗ {e}[/red]")


@config.command(name="capabilities")
@click.option("--backend", "-b", default=None, help="Check specific backend (default: active)")
def config_capabilities(backend: str | None) -> None:
    """List capabilities of the current backend.

    Shows which features are supported by the active backend
    or a specified backend.

    Examples:
        jarvis config capabilities              # Show current backend
        jarvis config capabilities -b notion    # Show Notion capabilities
    """
    cfg = load_config()
    target_backend = backend or cfg.active_backend

    console.print(f"[bold]Capabilities for {target_backend}[/bold]")
    console.print()

    try:
        adapter = get_adapter(target_backend)
        adapter.connect()
        caps = adapter.capabilities

        # Group capabilities by category
        task_caps = [
            ("tasks", "Task management"),
            ("priorities", "Priority levels"),
            ("due_dates", "Due dates"),
        ]
        journal_caps = [
            ("journal", "Journal entries"),
            ("daily_notes", "Automatic daily notes"),
        ]
        other_caps = [
            ("tags", "Tag management"),
            ("search", "Full-text search"),
            ("relations", "Links between items"),
            ("custom_properties", "Custom properties"),
        ]

        def show_caps(title: str, cap_list: list[tuple[str, str]]) -> None:
            console.print(f"[cyan]{title}[/cyan]")
            for cap_key, desc in cap_list:
                if caps.get(cap_key, False):
                    console.print(f"  [green]✓[/green] {desc}")
                else:
                    console.print(f"  [red]✗[/red] {desc}")
            console.print()

        show_caps("Tasks", task_caps)
        show_caps("Journal", journal_caps)
        show_caps("Other", other_caps)

    except Exception as e:
        console.print(f"[red]Error checking capabilities: {e}[/red]")
        console.print()
        console.print(f"[dim]Make sure {target_backend} is properly configured.[/dim]")


@config.command(name="path")
def config_path_cmd() -> None:
    """Show the path to the configuration file."""
    from jarvis.config import get_config_path

    console.print(get_config_path())


# ============================================================================
# Status Command
# ============================================================================


@cli.command()
@click.option("--diagnose", is_flag=True, help="Run diagnostics for connection issues")
def status(diagnose: bool) -> None:
    """Show Jarvis status and connection information.

    Displays the current backend, connection status, workspace information,
    and supported capabilities.

    Examples:
        jarvis status              # Show basic status
        jarvis status --diagnose   # Run connection diagnostics
    """
    console.print()
    console.print("[bold]Jarvis Status[/bold]")
    console.print("─" * 35)
    console.print()

    # Load configuration
    try:
        cfg = load_config()
    except Exception as e:
        console.print(f"[red]✗ Configuration error: {e}[/red]")
        console.print()
        console.print("[dim]Run 'jarvis config init' to create configuration.[/dim]")
        return

    backend_name = cfg.active_backend
    console.print(f"[bold]Backend:[/bold]     {backend_name.title()}")

    # Try to connect
    try:
        adapter = get_adapter(backend_name)
        adapter.connect()
        console.print("[bold]Connection:[/bold]  [green]✓ Connected[/green]")

        # Get workspace/space info
        try:
            spaces = adapter.list_spaces()
            if spaces:
                # Check for saved space or use first
                saved_space_id = get_selected_space()
                current_space = None
                for space in spaces:
                    if saved_space_id and space.id == saved_space_id:
                        current_space = space
                        break
                if current_space is None and spaces:
                    current_space = spaces[0]

                if current_space:
                    console.print(f"[bold]Workspace:[/bold]   {current_space.name}")
                else:
                    console.print(f"[bold]Workspace:[/bold]   [dim]({len(spaces)} available)[/dim]")
        except Exception:
            console.print("[bold]Workspace:[/bold]   [dim](unable to list)[/dim]")

        # Show capabilities
        console.print()
        console.print("[bold]Capabilities:[/bold]")
        caps = adapter.capabilities

        capability_map = [
            ("tasks", "Tasks"),
            ("journal", "Journal"),
            ("tags", "Tags"),
            ("search", "Search"),
            ("relations", "Relations"),
            ("priorities", "Priorities"),
        ]

        for cap_key, cap_label in capability_map:
            if caps.get(cap_key, False):
                console.print(f"  [green]✓[/green] {cap_label}")
            else:
                console.print(f"  [red]✗[/red] {cap_label} [dim](not available)[/dim]")

    except AuthError as e:
        console.print("[bold]Connection:[/bold]  [red]✗ Authentication failed[/red]")
        console.print()
        console.print(f"[red]Error:[/red] {e}")
        console.print()

        if diagnose:
            _run_diagnostics(backend_name, cfg)
        else:
            console.print("[dim]Run 'jarvis status --diagnose' for troubleshooting.[/dim]")
        return

    except AdapterConnectionError as e:
        console.print("[bold]Connection:[/bold]  [red]✗ Cannot connect[/red]")
        console.print()
        console.print(f"[red]Error:[/red] {e}")
        console.print()

        if diagnose:
            _run_diagnostics(backend_name, cfg)
        else:
            console.print("[dim]Run 'jarvis status --diagnose' for troubleshooting.[/dim]")
        return

    except Exception as e:
        console.print(f"[bold]Connection:[/bold]  [red]✗ Error: {e}[/red]")
        console.print()

        if diagnose:
            _run_diagnostics(backend_name, cfg)
        else:
            console.print("[dim]Run 'jarvis status --diagnose' for troubleshooting.[/dim]")
        return

    # If diagnose flag is set, run diagnostics even on success
    if diagnose:
        console.print()
        _run_diagnostics(backend_name, cfg)

    console.print()


def _run_diagnostics(backend: str, cfg) -> None:
    """Run connection diagnostics for troubleshooting."""
    from jarvis.config import get_backend_token, get_config_path, redact_token

    console.print("[bold]Diagnostics[/bold]")
    console.print("─" * 35)
    console.print()

    # Check config file
    config_path = get_config_path()
    if config_path.exists():
        console.print(f"[green]✓[/green] Config file: {config_path}")
    else:
        console.print(f"[red]✗[/red] Config file not found: {config_path}")

    # Check backend-specific requirements
    if backend == "anytype":
        console.print()
        console.print("[cyan]AnyType Checks:[/cyan]")

        # Check if AnyType is running (localhost:31009)
        import socket

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(("127.0.0.1", 31009))
            sock.close()
            if result == 0:
                console.print("[green]✓[/green] AnyType desktop app running on localhost:31009")
            else:
                console.print("[red]✗[/red] AnyType not responding on localhost:31009")
                console.print("  [dim]Make sure the AnyType desktop app is running.[/dim]")
        except Exception as e:
            console.print(f"[red]✗[/red] Cannot check AnyType: {e}")

    elif backend == "notion":
        console.print()
        console.print("[cyan]Notion Checks:[/cyan]")

        # Check token
        try:
            token = get_backend_token("notion")
            console.print(f"[green]✓[/green] Token found: {redact_token(token)}")

            # Check if token starts with expected prefix
            if token.startswith("secret_"):
                console.print("[green]✓[/green] Token format valid (starts with 'secret_')")
            else:
                console.print(
                    "[yellow]⚠[/yellow] Token may be invalid (should start with 'secret_')"
                )
        except Exception:
            console.print("[red]✗[/red] No Notion token found")
            console.print(
                "  [dim]Set JARVIS_NOTION_TOKEN or NOTION_TOKEN environment variable.[/dim]"
            )

        # Check database IDs
        if cfg.backends.notion:
            if cfg.backends.notion.task_database_id:
                console.print(f"[green]✓[/green] Task database ID configured")
            else:
                console.print("[red]✗[/red] Task database ID not set")

            if cfg.backends.notion.journal_database_id:
                console.print(f"[green]✓[/green] Journal database ID configured")
            else:
                console.print("[yellow]⚠[/yellow] Journal database ID not set (optional)")
        else:
            console.print("[red]✗[/red] Notion backend not configured")
            console.print("  [dim]Add [backends.notion] section to config.[/dim]")

    console.print()
    console.print(
        "[dim]For more help, see: https://github.com/your-repo/jarvis#troubleshooting[/dim]"
    )


# ============================================================================
# Documentation Command (for AI agents)
# ============================================================================


@cli.command()
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def docs(as_json: bool) -> None:
    """Output comprehensive CLI documentation for AI agents.

    This command dumps full documentation of all Jarvis commands,
    options, and usage examples in a format optimized for AI consumption.

    Example:
        jarvis docs          # Human-readable markdown
        jarvis docs --json   # Machine-readable JSON
    """
    import json as json_lib

    documentation = _generate_docs()

    if as_json:
        click.echo(json_lib.dumps(documentation, indent=2))
    else:
        click.echo(_format_docs_markdown(documentation))


def _generate_docs() -> dict:
    """Generate comprehensive documentation dictionary."""
    return {
        "name": "jarvis",
        "version": "0.1.0",
        "description": "AI-powered personal assistant for AnyType",
        "commands": {
            "analyze": {
                "description": "Analyze task distribution over a date range",
                "options": {
                    "--days": "Number of days to analyze (default: 14)",
                    "--space": "Space name or ID to use",
                },
                "examples": [
                    "jarvis analyze",
                    "jarvis analyze --days 30",
                ],
            },
            "suggest": {
                "description": "Generate AI rescheduling suggestions based on workload analysis",
                "options": {
                    "--days": "Number of days to analyze (default: 14)",
                    "--space": "Space name or ID to use",
                },
                "examples": [
                    "jarvis suggest",
                    "jarvis suggest --days 7",
                ],
            },
            "apply": {
                "description": "Review and apply pending suggestions interactively",
                "options": {},
                "examples": ["jarvis apply"],
            },
            "rebalance": {
                "description": "Full schedule rebalance: reschedule overdue and future tasks",
                "options": {
                    "--space": "Space name or ID to use",
                },
                "examples": ["jarvis rebalance"],
            },
            "spaces": {
                "description": "List available AnyType spaces and select one",
                "options": {},
                "examples": ["jarvis spaces"],
            },
            "status": {
                "description": "Show Jarvis status and connection information",
                "options": {
                    "--diagnose": "Run diagnostics for connection issues",
                },
                "examples": [
                    "jarvis status",
                    "jarvis status --diagnose",
                ],
            },
            "config": {
                "description": "Manage Jarvis configuration",
                "subcommands": {
                    "show": {
                        "description": "Show current configuration",
                        "examples": ["jarvis config show"],
                    },
                    "init": {
                        "description": "Initialize configuration file with defaults",
                        "options": {
                            "--force, -f": "Overwrite existing configuration",
                        },
                        "examples": ["jarvis config init", "jarvis config init --force"],
                    },
                    "backend": {
                        "description": "Show or set the active backend",
                        "options": {
                            "NAME": "Backend name (anytype, notion)",
                        },
                        "examples": [
                            "jarvis config backend",
                            "jarvis config backend notion",
                        ],
                    },
                    "capabilities": {
                        "description": "List capabilities of the current backend",
                        "options": {
                            "--backend, -b": "Check specific backend",
                        },
                        "examples": [
                            "jarvis config capabilities",
                            "jarvis config capabilities -b notion",
                        ],
                    },
                    "path": {
                        "description": "Show path to configuration file",
                        "examples": ["jarvis config path"],
                    },
                },
            },
            "init": {
                "description": "Initialize Jarvis context directories",
                "options": {
                    "--global": "Initialize global context (~/.jarvis/context/)",
                    "--folder": "Initialize folder context (./.jarvis/context/)",
                },
                "examples": [
                    "jarvis init",
                    "jarvis init --global",
                    "jarvis init --folder",
                ],
            },
            "context": {
                "description": "Manage Jarvis context files",
                "subcommands": {
                    "status": {
                        "description": "Show which context files are loaded",
                        "examples": ["jarvis context status"],
                    },
                    "edit": {
                        "description": "Open a context file in editor",
                        "options": {
                            "FILE": "Context file name (e.g., preferences, goals)",
                            "--global": "Edit global context file",
                        },
                        "examples": [
                            "jarvis context edit preferences",
                            "jarvis context edit goals --global",
                        ],
                    },
                },
            },
            "journal": {
                "description": "AI-powered journaling for AnyType",
                "subcommands": {
                    "write": {
                        "description": "Write a new journal entry",
                        "options": {
                            "TEXT": "Entry text (optional, opens editor if not provided)",
                            "--editor, -e": "Open editor for entry",
                            "--interactive, -i": "Interactive multi-line input",
                            "--file, -f": "Read entry content from a file (prepends AI summary)",
                            "--title": "Custom title (skips AI generation)",
                            "--no-deep-dive": "Skip deep dive prompt",
                        },
                        "examples": [
                            'jarvis journal write "Had a great day"',
                            "jarvis journal write --editor",
                            "jarvis journal write -i",
                            'jarvis journal write --file ./notes.md --title "Meeting Notes"',
                        ],
                    },
                    "list": {
                        "description": "List recent journal entries",
                        "options": {
                            "--limit, -n": "Number of entries to show (default: 10)",
                        },
                        "examples": [
                            "jarvis journal list",
                            "jarvis journal list -n 20",
                        ],
                    },
                    "read": {
                        "description": "Read a journal entry by number",
                        "options": {
                            "NUMBER": "Entry number from list",
                        },
                        "examples": ["jarvis journal read 1"],
                    },
                    "search": {
                        "description": "Search journal entries",
                        "options": {
                            "QUERY": "Search query",
                        },
                        "examples": ['jarvis journal search "project idea"'],
                    },
                    "insights": {
                        "description": "Get AI-powered insights across journal entries",
                        "options": {
                            "--days": "Number of days to analyze (default: 30)",
                        },
                        "examples": [
                            "jarvis journal insights",
                            "jarvis journal insights --days 90",
                        ],
                    },
                },
            },
            "j": {
                "description": "Alias for 'journal write' - quick journal entry",
                "options": {
                    "TEXT": "Entry text",
                    "--file, -f": "Read content from file with AI summary",
                    "--title": "Custom title",
                },
                "examples": [
                    'jarvis j "Quick thought for today"',
                    'jarvis j "Meeting notes" --title "Team Sync"',
                    "jarvis j --file ./design.md",
                ],
            },
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
            "reading-list": {
                "description": "Organize and prioritize a reading list against current project context",
                "subcommands": {
                    "organize": {
                        "description": "Deep research and prioritize a reading list",
                        "options": {
                            "TARGET": "AnyType URL, Notion URL, file path, generic URL, or '-' for stdin",
                            "--resolver": "Override source resolution (anytype, notion, file, url, stdin)",
                            "--backend": "Backend override for object-based resolvers",
                            "--output": "Save markdown output to file",
                            "--format": "Output format: table, json, markdown",
                            "--tier": "Filter to a specific tier",
                            "--topic": "Filter to a specific topic",
                            "--journal": "Save prioritized output to journal",
                            "--no-fetch": "Skip deep URL fetching; prioritize from metadata only",
                            "--no-cache": "Ignore cached content and results",
                        },
                        "examples": [
                            'jarvis reading-list organize "https://object.any.coop/..."',
                            'jarvis reading-list organize ./reading-list.md --format markdown',
                            'cat reading-list.md | jarvis reading-list organize - --resolver stdin',
                        ],
                    },
                    "list": {
                        "description": "Extract and display links from a reading list source",
                        "options": {
                            "TARGET": "AnyType URL, Notion URL, file path, generic URL, or '-' for stdin",
                            "--resolver": "Override source resolution",
                            "--backend": "Backend override for object-based resolvers",
                        },
                        "examples": [
                            'jarvis reading-list list "https://object.any.coop/..."',
                            'jarvis reading-list list ./reading-list.md',
                        ],
                    },
                    "cache-clear": {
                        "description": "Clear reading list caches",
                        "options": {},
                        "examples": ['jarvis reading-list cache-clear'],
                    },
                },
            },
            "rl": {
                "description": "Quick alias for 'reading-list organize'",
                "options": {
                    "TARGET": "AnyType URL, Notion URL, file path, generic URL, or '-' for stdin",
                    "--resolver": "Override source resolution",
                    "--backend": "Backend override for object-based resolvers",
                    "--output": "Save markdown output to file",
                    "--format": "Output format: table, json, markdown",
                    "--tier": "Filter to a specific tier",
                    "--topic": "Filter to a specific topic",
                    "--journal": "Save prioritized output to journal",
                    "--no-fetch": "Skip deep URL fetching",
                    "--no-cache": "Ignore cached content and results",
                },
                "examples": [
                    'jarvis rl "https://object.any.coop/..."',
                    'jarvis rl ./reading-list.md --tier read_now',
                ],
            },
            "android": {
                "description": "Run Android emulator and APK workflows",
                "subcommands": {
                    "run": {
                        "description": "Install an APK on an Android emulator and optionally launch it",
                        "options": {
                            "APK_PATH": "Path to the .apk file",
                            "--avd": "AVD name to boot if no emulator is running",
                            "--reinstall": "Reinstall the app if it is already installed",
                            "--no-launch": "Install without launching the app",
                            "--timeout": "Seconds to wait for emulator boot (default: 180)",
                        },
                        "examples": [
                            "jarvis android run ~/Downloads/app.apk",
                            "jarvis android run ./builds/demo.apk --avd Medium_Phone_API_36.1",
                            "jarvis android run ./builds/demo.apk --reinstall --no-launch",
                        ],
                    },
                    "avds": {
                        "description": "List available Android Virtual Devices",
                        "options": {},
                        "examples": ["jarvis android avds"],
                    },
                },
            },
            "apk": {
                "description": "Quick alias for 'android run'",
                "options": {
                    "APK_PATH": "Path to the .apk file",
                    "--avd": "AVD name to boot if no emulator is running",
                    "--reinstall": "Reinstall the app if it is already installed",
                    "--no-launch": "Install without launching the app",
                    "--timeout": "Seconds to wait for emulator boot (default: 180)",
                },
                "examples": [
                    "jarvis apk ~/Downloads/app.apk",
                    "jarvis apk ./builds/demo.apk --avd Medium_Phone_API_36.1",
                ],
            },
        },
        "context_system": {
            "description": "Two-tier context for AI personalization",
            "global_path": "~/.jarvis/context/",
            "folder_path": "./.jarvis/context/",
            "files": [
                "preferences.md",
                "patterns.md",
                "constraints.md",
                "priorities.md",
                "goals.md",
                "projects.md",
                "recurring.md",
                "focus.md",
                "blockers.md",
                "calendar.md",
                "delegation.md",
                "decisions.md",
            ],
            "merge_behavior": "Folder overrides global. Use {{global}} placeholder to include global content.",
        },
        "environment": {
            "ANTHROPIC_API_KEY": "Required for AI features",
            "EDITOR": "Editor for context/journal editing (default: vim)",
        },
        "requirements": [
            "Python 3.11+",
            "AnyType desktop app running on localhost:31009",
        ],
    }


def _format_docs_markdown(docs: dict) -> str:
    """Format documentation as markdown."""
    lines = [
        f"# {docs['name']} v{docs['version']}",
        "",
        docs["description"],
        "",
        "## Commands",
        "",
    ]

    for cmd_name, cmd_info in docs["commands"].items():
        lines.append(f"### `jarvis {cmd_name}`")
        lines.append("")
        lines.append(cmd_info["description"])
        lines.append("")

        if "subcommands" in cmd_info:
            for sub_name, sub_info in cmd_info["subcommands"].items():
                lines.append(f"#### `jarvis {cmd_name} {sub_name}`")
                lines.append("")
                lines.append(sub_info["description"])
                if "options" in sub_info and sub_info["options"]:
                    lines.append("")
                    lines.append("Options:")
                    for opt, desc in sub_info["options"].items():
                        lines.append(f"  {opt}: {desc}")
                if "examples" in sub_info:
                    lines.append("")
                    lines.append("Examples:")
                    for ex in sub_info["examples"]:
                        lines.append(f"  {ex}")
                lines.append("")
        else:
            if "options" in cmd_info and cmd_info["options"]:
                lines.append("Options:")
                for opt, desc in cmd_info["options"].items():
                    lines.append(f"  {opt}: {desc}")
                lines.append("")
            if "examples" in cmd_info:
                lines.append("Examples:")
                for ex in cmd_info["examples"]:
                    lines.append(f"  {ex}")
                lines.append("")

    lines.extend(
        [
            "## Context System",
            "",
            docs["context_system"]["description"],
            "",
            f"- Global: {docs['context_system']['global_path']}",
            f"- Folder: {docs['context_system']['folder_path']}",
            "",
            "Context files: " + ", ".join(docs["context_system"]["files"]),
            "",
            f"Merge: {docs['context_system']['merge_behavior']}",
            "",
            "## Environment Variables",
            "",
        ]
    )

    for var, desc in docs["environment"].items():
        lines.append(f"- {var}: {desc}")

    return "\n".join(lines)


@cli.command()
@click.option("--days", default=14, help="Number of days to analyze (default: 14)")
@click.option("--space", default=None, help="Space name or ID to use")
@click.option("--backend", default=None, help="Backend to use (anytype, notion)")
def analyze(days: int, space: str | None, backend: str | None) -> None:
    """Analyze current schedule workload."""
    try:
        adapter = get_adapter(backend)
        adapter.connect()

        space_id, space_name = _get_space(adapter, space)
        console.print(f"[dim]Space: {space_name}[/dim]")
        console.print(f"[dim]Backend: {adapter.backend_name}[/dim]")

        start = date.today()
        end = start + timedelta(days=days)

        tasks = adapter.get_tasks(
            space_id=space_id,
            start_date=start,
            end_date=end,
            include_done=False,
        )
        analysis = analyze_workload(tasks, start, end)
        _display_analysis(analysis)
    except AdapterConnectionError as e:
        console.print(f"[red]Connection error: {e}[/red]")
        console.print("[dim]Make sure the backend service is running.[/dim]")
        raise SystemExit(1)
    except AuthError as e:
        console.print(f"[red]Authentication error: {e}[/red]")
        console.print("[dim]Check your API token configuration.[/dim]")
        raise SystemExit(1)
    except NotSupportedError as e:
        console.print(f"[red]Not supported: {e}[/red]")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)


def _get_space(adapter: KnowledgeBaseAdapter, space_arg: str | None) -> tuple[str, str]:
    """Get space ID from argument or prompt.

    Args:
        adapter: Connected adapter instance
        space_arg: Optional space name/ID from command line

    Returns:
        Tuple of (space_id, space_name)
    """
    spaces = adapter.list_spaces()

    # If space argument provided, try to match it
    if space_arg:
        for space in spaces:
            if space_arg.lower() in space.name.lower() or space_arg == space.id:
                save_selected_space(space.id)
                return space.id, space.name
        console.print(f"[yellow]Space '{space_arg}' not found. Please select:[/yellow]")

    return select_space(adapter)


def _display_analysis(analysis: WorkloadAnalysis) -> None:
    """Display workload analysis with Rich formatting."""
    console.print()
    console.print(
        Panel.fit(
            f"[bold]Schedule Analysis[/bold] ({analysis.start_date} to {analysis.end_date})",
            border_style="blue",
        )
    )
    console.print()

    # Create visual bars for each day
    for day in analysis.days:
        bar_length = min(day.total_tasks, 12)
        bar = "█" * bar_length
        day_name = day.day_date.strftime("%a %d")

        if day.status == "overloaded":
            status_icon = "[red]⚠️  Overloaded[/red]"
            bar_color = "red"
        elif day.status == "light":
            status_icon = "[dim]○  Light[/dim]"
            bar_color = "dim"
        else:
            status_icon = "[green]✓[/green]"
            bar_color = "green"

        console.print(
            f"  {day_name}  [{bar_color}]{bar:12}[/{bar_color}]  "
            f"{day.total_tasks} tasks  {status_icon}"
        )

    console.print()
    console.print(f"[dim]🔒 Immovable:[/dim] {analysis.total_immovable} tasks")
    console.print(f"[dim]📦 Moveable:[/dim] {analysis.total_moveable} tasks")
    console.print(f"[dim]📈 Variance:[/dim] {analysis.variance:.1f} (lower is better)")
    console.print()


@cli.command()
@click.option("--days", default=14, help="Number of days to consider (default: 14)")
@click.option("--space", default=None, help="Space name or ID to use")
@click.option("--backend", default=None, help="Backend to use (anytype, notion)")
def suggest(days: int, space: str | None, backend: str | None) -> None:
    """Generate rescheduling suggestions using AI."""
    import os

    from jarvis.ai_client import AIClient

    try:
        # Check for API key
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY environment variable not set.\n"
                "Get your API key from https://console.anthropic.com/"
            )

        adapter = get_adapter(backend)
        adapter.connect()

        space_id, space_name = _get_space(adapter, space)
        console.print(f"[dim]Space: {space_name}[/dim]")
        console.print(f"[dim]Backend: {adapter.backend_name}[/dim]")

        start = date.today()
        end = start + timedelta(days=days)

        tasks = adapter.get_tasks(
            space_id=space_id,
            start_date=start,
            end_date=end,
            include_done=False,
        )
        analysis = analyze_workload(tasks, start, end)
        context = load_context()

        ai_client = AIClient(api_key)
        suggestions = ai_client.generate_suggestions(tasks, analysis, context)

        if suggestions:
            save_suggestions(suggestions, space_id)
            _display_suggestions(suggestions)
        else:
            console.print(
                "[yellow]No suggestions generated. Your schedule looks balanced![/yellow]"
            )
    except AdapterConnectionError as e:
        console.print(f"[red]Connection error: {e}[/red]")
        raise SystemExit(1)
    except AuthError as e:
        console.print(f"[red]Authentication error: {e}[/red]")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)


def _display_suggestions(suggestions: list[Suggestion]) -> None:
    """Display suggestions with Rich formatting."""
    console.print()
    console.print(
        Panel.fit(
            f"[bold]💡 {len(suggestions)} Suggestion{'s' if len(suggestions) != 1 else ''} "
            f"Generated[/bold]",
            border_style="yellow",
        )
    )
    console.print()

    for i, s in enumerate(suggestions, 1):
        console.print(f'[bold]{i}.[/bold] [cyan]"{s.task_name}"[/cyan]')
        current = s.current_date.strftime("%a %b %d")
        proposed = s.proposed_date.strftime("%a %b %d")
        console.print(f"   {current} → {proposed}")
        console.print(f"   [dim]Reason: {s.reasoning}[/dim]")
        console.print()

    console.print("[dim]Run [bold]jarvis apply[/bold] to review and apply these suggestions.[/dim]")
    console.print()


@cli.command()
@click.option("--yes", "-y", is_flag=True, help="Apply all suggestions without prompting")
@click.option("--backend", default=None, help="Backend to use (anytype, notion)")
def apply(yes: bool, backend: str | None) -> None:
    """Apply pending suggestions to the backend."""
    suggestions, space_id = load_suggestions()

    if not suggestions:
        console.print("[yellow]No pending suggestions. Run 'jarvis suggest' first.[/yellow]")
        return

    pending = [s for s in suggestions if s.status == "pending"]
    if not pending:
        console.print("[yellow]No pending suggestions to apply.[/yellow]")
        return

    try:
        adapter = get_adapter(backend)
        adapter.connect()

        console.print()
        console.print(Panel.fit("[bold]📋 Review Suggestions[/bold]", border_style="blue"))
        console.print(f"[dim]Backend: {adapter.backend_name}[/dim]")
        console.print()

        applied = 0
        skipped = 0

        for i, s in enumerate(pending, 1):
            console.print(
                f'[bold][{i}/{len(pending)}][/bold] Move [cyan]"{s.task_name}"[/cyan] '
                f"{s.current_date.strftime('%a %b %d')} → {s.proposed_date.strftime('%a %b %d')}?"
            )

            if yes or Confirm.ask("   Apply this change?", default=True):
                try:
                    adapter.update_task(
                        space_id=space_id,
                        task_id=s.task_id,
                        due_date=s.proposed_date,
                    )
                    s.mark_applied()
                    console.print("   [green]✓ Applied[/green]")
                    applied += 1
                except Exception:
                    s.mark_failed()
                    console.print("   [red]✗ Failed[/red]")
                    skipped += 1
            else:
                s.reject()
                console.print("   [dim]✗ Skipped[/dim]")
                skipped += 1

            console.print()

        clear_suggestions()
        console.print()
        console.print(f"[green]Done![/green] Applied: {applied} | Skipped: {skipped}")
        console.print()
    except AdapterConnectionError as e:
        console.print(f"[red]Connection error: {e}[/red]")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)


@cli.command()
@click.option("--space", default=None, help="Space name or ID to use")
@click.option("--dry-run", is_flag=True, help="Show what would be done without applying")
@click.option("--yes", "-y", is_flag=True, help="Apply all changes without prompting")
@click.option("--backend", default=None, help="Backend to use (anytype, notion)")
def rebalance(space: str | None, dry_run: bool, yes: bool, backend: str | None) -> None:
    """Rebalance all tasks: overdue + next 2 months → redistribute evenly.

    Collects:
    - Overdue tasks (due today or before, not done, not ongoing)
    - Scheduled tasks for next 2 months (not done, not ongoing)

    Redistributes across Feb-Mar (or next 2 months) on weekdays.
    """
    try:
        adapter = get_adapter(backend)
        adapter.connect()

        space_id, space_name = _get_space(adapter, space)
        console.print(f"[dim]Space: {space_name}[/dim]")
        console.print(f"[dim]Backend: {adapter.backend_name}[/dim]")

        today = date.today()
        two_months_ahead = today + timedelta(days=60)

        # Fetch all tasks
        very_old = date(2020, 1, 1)
        all_tasks_old = adapter.get_tasks(
            space_id=space_id,
            start_date=very_old,
            end_date=today,
            include_done=False,
        )
        all_tasks_future = adapter.get_tasks(
            space_id=space_id,
            start_date=today + timedelta(days=1),
            end_date=two_months_ahead,
            include_done=False,
        )

        # Filter: not done, not ongoing, not bar_movement
        def is_moveable(task) -> bool:
            if task.is_done:
                return False
            tags_lower = [t.lower() for t in (task.tags or [])]
            if "ongoing" in tags_lower:
                return False
            if "bar_movement" in tags_lower:
                return False
            return True

        overdue = [
            t for t in all_tasks_old if t.due_date and t.due_date <= today and is_moveable(t)
        ]
        scheduled = [t for t in all_tasks_future if is_moveable(t)]

        all_to_schedule = overdue + scheduled
        all_to_schedule.sort(key=lambda t: t.due_date or today)

        console.print()
        console.print(f"[yellow]Overdue tasks:[/yellow] {len(overdue)}")
        console.print(f"[yellow]Scheduled (next 2 months):[/yellow] {len(scheduled)}")
        console.print(f"[bold]Total to redistribute:[/bold] {len(all_to_schedule)}")
        console.print()

        if not all_to_schedule:
            console.print("[green]No tasks to rebalance![/green]")
            return

        # Target window: next 2 months starting from tomorrow, weekdays only
        target_start = today + timedelta(days=1)
        # Go to end of month + 1 more month
        if target_start.month <= 10:
            target_end = date(target_start.year, target_start.month + 2, 1) - timedelta(days=1)
        elif target_start.month == 11:
            target_end = date(target_start.year + 1, 1, 1) - timedelta(days=1)
        else:
            target_end = date(target_start.year + 1, 2, 1) - timedelta(days=1)

        # Extend by 1 more month for spillover
        if target_end.month <= 10:
            spillover_end = date(target_end.year, target_end.month + 2, 1) - timedelta(days=1)
        elif target_end.month == 11:
            spillover_end = date(target_end.year + 1, 1, 1) - timedelta(days=1)
        else:
            spillover_end = date(target_end.year + 1, 2, 1) - timedelta(days=1)

        # Collect weekdays
        weekdays = []
        current = target_start
        while current <= spillover_end:
            if current.weekday() < 5:  # Monday-Friday
                weekdays.append(current)
            current += timedelta(days=1)

        console.print(
            f"[dim]Target window: {target_start.strftime('%b %d')} - {spillover_end.strftime('%b %d, %Y')}[/dim]"
        )
        console.print(f"[dim]Available weekdays: {len(weekdays)}[/dim]")

        if not weekdays:
            console.print("[red]No weekdays in target window![/red]")
            return

        # Calculate tasks per day for even distribution
        tasks_per_day = len(all_to_schedule) / len(weekdays)
        console.print(f"[dim]Average tasks/day: {tasks_per_day:.1f}[/dim]")
        console.print()

        # Distribute evenly: round-robin across weekdays
        assignments = []
        for i, task in enumerate(all_to_schedule):
            new_date = weekdays[i % len(weekdays)]
            # Only add if date is changing
            if task.due_date != new_date:
                assignments.append((task, new_date))

        console.print(f"[bold]Tasks to move:[/bold] {len(assignments)}")
        console.print()

        # Show distribution preview
        from collections import defaultdict

        by_week = defaultdict(int)
        for task, new_date in assignments:
            week_start = new_date - timedelta(days=new_date.weekday())
            by_week[week_start] += 1

        # Also count tasks staying in place
        for task in all_to_schedule:
            if task.due_date and not any(t.id == task.id for t, _ in assignments):
                week_start = task.due_date - timedelta(days=task.due_date.weekday())
                by_week[week_start] += 1

        console.print("[bold]New weekly distribution:[/bold]")
        for week in sorted(by_week.keys())[:12]:
            week_end = week + timedelta(days=6)
            bar = "█" * min(by_week[week], 20)
            console.print(
                f"  {week.strftime('%b %d')} - {week_end.strftime('%b %d')}: {bar} {by_week[week]}"
            )
        console.print()

        if dry_run:
            console.print("[yellow]Dry run - no changes made[/yellow]")
            console.print()
            console.print("Sample moves:")
            for task, new_date in assignments[:15]:
                old = task.due_date.strftime("%Y-%m-%d") if task.due_date else "None"
                new = new_date.strftime("%a %b %d")
                console.print(f"  {old} → {new}  [cyan]{task.title[:40]}[/cyan]")
            if len(assignments) > 15:
                console.print(f"  ... and {len(assignments) - 15} more")
            return

        # Confirm
        if not yes and not Confirm.ask(f"Apply {len(assignments)} changes?", default=False):
            console.print("[dim]Cancelled[/dim]")
            return

        # Apply changes
        applied = 0
        failed = 0
        for task, new_date in assignments:
            try:
                adapter.update_task(
                    space_id=space_id,
                    task_id=task.id,
                    due_date=new_date,
                )
                applied += 1
                console.print(f"  [green]✓[/green] {task.title[:40]}")
            except Exception:
                failed += 1

        console.print()
        console.print(f"[green]Done![/green] Applied: {applied} | Failed: {failed}")

    except AdapterConnectionError as e:
        console.print(f"[red]Connection error: {e}[/red]")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)


@cli.command()
@click.option("--days", default=14, help="Number of days to consider (default: 14)")
@click.option("--space", default=None, help="Space name or ID to use")
@click.option("--backend", default=None, help="Backend to use (anytype, notion)")
@click.option("--dry-run", is_flag=True, help="Show plan without saving suggestions")
def reorganize(days: int, space: str | None, backend: str | None, dry_run: bool) -> None:
    try:
        adapter = get_adapter(backend)
        adapter.connect()

        space_id, space_name = _get_space(adapter, space)
        console.print(f"[dim]Space: {space_name}[/dim]")
        console.print(f"[dim]Backend: {adapter.backend_name}[/dim]")

        start = date.today()
        end = start + timedelta(days=days)
        tasks = adapter.get_tasks(
            space_id=space_id,
            start_date=start,
            end_date=end,
            include_done=False,
        )

        suggestions = build_reorganize_suggestions(tasks, start, end)
        if not suggestions:
            console.print("[green]No reorganize moves needed in this horizon.[/green]")
            return

        _display_suggestions(suggestions)
        if dry_run:
            console.print("[yellow]Dry run mode: no pending suggestions saved.[/yellow]")
            return

        save_suggestions(suggestions, space_id)
        console.print("[green]Saved as pending suggestions.[/green]")
        console.print("[dim]Run jarvis apply to approve and apply changes.[/dim]")
    except AdapterConnectionError as e:
        console.print(f"[red]Connection error: {e}[/red]")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)


@cli.group()
def calendar() -> None:
    pass


@calendar.command("plan")
@click.option("--days", default=14, help="Planning horizon in days")
@click.option("--space", default=None, help="Space name or ID to use")
@click.option("--backend", default=None, help="Backend to use (anytype, notion)")
@click.option("--min-block", default=30, type=int, help="Minimum block minutes")
@click.option(
    "--interactive/--no-interactive",
    default=True,
    help="Ask clarification questions before planning",
)
@click.option(
    "--enforce-due-dates/--allow-post-deadline",
    default=True,
    help="Prevent scheduling task blocks past due dates",
)
@click.option(
    "--force-non-interactive",
    is_flag=True,
    help="Bypass safety gate when --no-interactive is used",
)
@click.option("--dry-run", is_flag=True, help="Generate plan only")
def calendar_plan(
    days: int,
    space: str | None,
    backend: str | None,
    min_block: int,
    interactive: bool,
    enforce_due_dates: bool,
    force_non_interactive: bool,
    dry_run: bool,
) -> None:
    try:
        adapter = get_adapter(backend)
        adapter.connect()
        provider = GWSProvider()

        space_id, space_name = _get_space(adapter, space)
        console.print(f"[dim]Space: {space_name}[/dim]")
        console.print(f"[dim]Backend: {adapter.backend_name}[/dim]")

        context = load_context()
        default_start_hour, default_end_hour = parse_work_hours_from_context(context)
        selected_start_hour = default_start_hour
        selected_end_hour = default_end_hour
        selected_min_block = min_block
        selected_enforce_due_dates = enforce_due_dates
        selected_due_date_grace_days = 0
        selected_include_weekends = True

        if interactive:
            console.print()
            console.print(Panel.fit("[bold]Planning preflight[/bold]", border_style="magenta"))
            selected_start_hour = click.prompt(
                "Workday start hour (0-23)",
                type=click.IntRange(0, 23),
                default=default_start_hour,
                show_default=True,
            )
            selected_end_hour = click.prompt(
                "Workday end hour (1-24)",
                type=click.IntRange(1, 24),
                default=default_end_hour,
                show_default=True,
            )
            if selected_end_hour <= selected_start_hour:
                raise RuntimeError("Workday end hour must be greater than start hour")
            selected_min_block = click.prompt(
                "Minimum block minutes",
                type=click.IntRange(15, 240),
                default=min_block,
                show_default=True,
            )
            selected_enforce_due_dates = Confirm.ask(
                "Enforce due-date boundaries (avoid scheduling after deadlines)?",
                default=enforce_due_dates,
            )
            selected_due_date_grace_days = click.prompt(
                "Allow due-date grace days for overdue/near-due tasks",
                type=click.IntRange(0, 14),
                default=0,
                show_default=True,
            )
            selected_include_weekends = Confirm.ask(
                "Schedule across all 7 days (including weekends)?",
                default=True,
            )
            console.print(
                f"[dim]Using {selected_start_hour:02d}:00-{selected_end_hour:02d}:00, "
                f"min block {selected_min_block}m, "
                f"due-date enforcement: {'on' if selected_enforce_due_dates else 'off'}, "
                f"grace: {selected_due_date_grace_days}d, "
                f"weekends: {'on' if selected_include_weekends else 'off'}[/dim]"
            )

        start = date.today()
        end = start + timedelta(days=days)
        tasks = adapter.get_tasks(
            space_id=space_id,
            start_date=start,
            end_date=end,
            include_done=False,
        )

        overdue_or_urgent = [
            t for t in tasks if t.due_date and t.due_date <= start + timedelta(days=2)
        ]
        if (not interactive) and overdue_or_urgent and not force_non_interactive:
            raise RuntimeError(
                "Non-interactive planning blocked: urgent/overdue tasks detected. "
                "Run without --no-interactive to answer planning questions, "
                "or pass --force-non-interactive to override."
            )

        busy_slots = provider.get_busy_slots(
            datetime.combine(start, datetime.min.time(), tzinfo=datetime.now().astimezone().tzinfo),
            datetime.combine(
                end + timedelta(days=1),
                datetime.min.time(),
                tzinfo=datetime.now().astimezone().tzinfo,
            ),
        )

        plan = build_calendar_plan(
            tasks=tasks,
            busy_slots=busy_slots,
            start_date=start,
            end_date=end,
            backend=adapter.backend_name,
            space_id=space_id,
            min_block_minutes=selected_min_block,
            context=context,
            now_dt=datetime.now().astimezone(),
            workday_start_hour=selected_start_hour,
            workday_end_hour=selected_end_hour,
            enforce_due_dates=selected_enforce_due_dates,
            due_date_grace_days=selected_due_date_grace_days,
            include_weekends=selected_include_weekends,
        )
        path = save_plan(plan)

        console.print()
        console.print(Panel.fit(f"[bold]Plan ID:[/bold] {plan.plan_id}", border_style="blue"))
        console.print(f"[dim]Saved: {path}[/dim]")
        console.print(f"[green]Blocks:[/green] {len(plan.blocks)}")
        console.print(f"[yellow]Unplaced:[/yellow] {len(plan.unplaced)}")
        console.print()
        for block in plan.blocks[:12]:
            console.print(
                f"[cyan]{block.start.strftime('%a %b %d %H:%M')}[/cyan] - {block.end.strftime('%H:%M')}"
                f"  {block.task_title}"
            )
        if len(plan.blocks) > 12:
            console.print(f"[dim]... and {len(plan.blocks) - 12} more blocks[/dim]")
        if plan.unplaced:
            console.print("\n[bold]Unplaced tasks:[/bold]")
            for item in plan.unplaced[:8]:
                console.print(f"  - {item.task_title}: {item.reason}")
        if dry_run:
            console.print("\n[yellow]Dry run mode: plan generated for review only.[/yellow]")
            return

        console.print(
            "\n[dim]Run jarvis calendar apply --plan {plan_id} to write events.[/dim]".format(
                plan_id=plan.plan_id
            )
        )
    except AdapterConnectionError as e:
        console.print(f"[red]Connection error: {e}[/red]")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)


@calendar.command("apply")
@click.option("--plan", "plan_id", default=None, help="Plan ID to apply")
@click.option("--yes", "assume_yes", is_flag=True, help="Skip confirmation")
def calendar_apply(plan_id: str | None, assume_yes: bool) -> None:
    try:
        plan_ids = list_plan_ids()
        if not plan_ids:
            console.print("[yellow]No saved plans found. Run jarvis calendar plan first.[/yellow]")
            return

        target = plan_id or plan_ids[-1]
        plan = load_plan(target)
        existing = load_plan_apply(target)
        prior = {r.block_id: r for r in existing.results} if existing else {}

        if not assume_yes and not Confirm.ask(
            f"Apply {len(plan.blocks)} calendar blocks from plan {target}?",
            default=False,
        ):
            console.print("[dim]Cancelled[/dim]")
            return

        provider = GWSProvider()
        results: list[AppliedBlockResult] = []
        applied = 0
        skipped = 0
        failed = 0

        for block in plan.blocks:
            prev = prior.get(block.block_id)
            if prev and prev.status in {"applied", "already_applied"}:
                results.append(
                    AppliedBlockResult(
                        block_id=block.block_id,
                        task_id=block.task_id,
                        status="already_applied",
                        event_id=prev.event_id,
                    )
                )
                skipped += 1
                continue
            try:
                event_id = provider.create_event(
                    summary=f"Jarvis: {block.task_title}",
                    start=block.start,
                    end=block.end,
                    description=f"Task ID: {block.task_id}\nReason: {block.reason}",
                )
                results.append(
                    AppliedBlockResult(
                        block_id=block.block_id,
                        task_id=block.task_id,
                        status="applied",
                        event_id=event_id,
                    )
                )
                applied += 1
            except Exception as exc:
                results.append(
                    AppliedBlockResult(
                        block_id=block.block_id,
                        task_id=block.task_id,
                        status="failed",
                        error=str(exc),
                    )
                )
                failed += 1

        result = PlanApplyResult(
            plan_id=target,
            applied_at=datetime.now(timezone.utc),
            results=results,
        )
        path = save_plan_apply(result)
        console.print(f"[green]Applied:[/green] {applied}")
        console.print(f"[yellow]Skipped:[/yellow] {skipped}")
        console.print(f"[red]Failed:[/red] {failed}")
        console.print(f"[dim]Apply report: {path}[/dim]")
    except FileNotFoundError:
        console.print(f"[red]Plan not found: {plan_id}[/red]")
        console.print(f"[dim]Available plan IDs: {', '.join(list_plan_ids())}[/dim]")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)


@cli.command()
@click.option("--backend", default=None, help="Backend to use (anytype, notion)")
def spaces(backend: str | None) -> None:
    """List available spaces and select one."""
    from jarvis.state import clear_selected_space

    try:
        adapter = get_adapter(backend)
        adapter.connect()

        console.print(f"[dim]Backend: {adapter.backend_name}[/dim]")

        # Clear saved selection to force re-prompt
        clear_selected_space()

        space_id, space_name = select_space(adapter)
        console.print(f"[green]Selected:[/green] {space_name}")
    except AdapterConnectionError as e:
        console.print(f"[red]Connection error: {e}[/red]")
        raise SystemExit(1)
    except AuthError as e:
        console.print(f"[red]Authentication error: {e}[/red]")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)


if __name__ == "__main__":
    cli()
