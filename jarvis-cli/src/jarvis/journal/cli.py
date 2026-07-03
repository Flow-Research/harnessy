"""CLI commands for journal operations.

Provides the `jarvis journal` command group with subcommands:
- write: Create a new journal entry
- list: List recent entries
- read: Read an entry's content
- search: Search entries
- insights: Get AI insights
"""

from datetime import date, datetime

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from jarvis.anytype_client import AnyTypeClient
from jarvis.journal.capture import CaptureMode, capture_entry, determine_capture_mode
from jarvis.journal.hierarchy import JournalHierarchy
from jarvis.journal.models import CONTENT_PREVIEW_LENGTH, JournalEntryReference
from jarvis.journal.prompts import (
    FILE_SUMMARY_SYSTEM,
    TITLE_GENERATION_SYSTEM,
    format_file_summary_prompt,
    format_title_prompt,
)
from jarvis.journal.state import save_draft, save_entry_reference
from jarvis.knowledge_body import strip_duplicate_title_heading

console = Console()


def get_connected_client() -> AnyTypeClient:
    """Get a connected AnyType client.

    Returns:
        Connected AnyTypeClient instance

    Raises:
        SystemExit: If connection fails
    """
    try:
        client = AnyTypeClient()
        client.connect()
        return client
    except Exception as e:
        console.print(f"[red]Failed to connect to AnyType: {e}[/red]")
        raise SystemExit(1)


def get_space_selection(client: AnyTypeClient, space: str | None = None) -> tuple[str, str]:
    """Get space selection from user or argument.

    Resolution order:
        1. Explicit ``space`` arg (name or ID)
        2. ``backends.anytype.default_space_id`` in non-interactive contexts
        3. Saved selection in ``~/.jarvis/config.json``
        4. ``backends.anytype.default_space_id`` from ``~/.jarvis/config.yaml``
        5. Single available space (auto-select)
        6. Interactive prompt (TTY only)

    Args:
        client: Connected AnyType client
        space: Optional space name or ID

    Returns:
        Tuple of (space_id, space_name)
    """
    import sys

    from jarvis.state import get_selected_space, save_selected_space

    spaces = client.get_spaces()

    # If space specified, find it
    if space:
        for space_id, space_name in spaces:
            if space_id == space or space_name.lower() == space.lower():
                return space_id, space_name
        console.print(f"[red]Space not found: {space}[/red]")
        raise SystemExit(1)

    configured_default = _configured_default_space(spaces)
    if not sys.stdin.isatty() and configured_default:
        return configured_default

    # Check saved selection (~/.jarvis/config.json)
    saved_space_id = get_selected_space()
    if saved_space_id:
        for space_id, space_name in spaces:
            if space_id == saved_space_id:
                return space_id, space_name

    # Fall back to config.yaml default_space_id (works for cron / non-interactive)
    if configured_default:
        return configured_default

    # Single space - use automatically
    if len(spaces) == 1:
        space_id, space_name = spaces[0]
        save_selected_space(space_id)
        return space_id, space_name

    # Non-interactive context: fail loudly instead of hanging on EOF
    if not sys.stdin.isatty():
        console.print(
            "[red]No space resolved and no TTY available for prompt.[/red] "
            "Set backends.anytype.default_space_id in ~/.jarvis/config.yaml "
            "or pass --space."
        )
        raise SystemExit(2)

    # Prompt user
    console.print()
    console.print("[bold]Select a space:[/bold]")
    for i, (space_id, space_name) in enumerate(spaces, 1):
        console.print(f"  [cyan]{i}[/cyan]. {space_name}")

    choice = Prompt.ask(
        "Enter number",
        choices=[str(i) for i in range(1, len(spaces) + 1)],
        default="1",
    )

    selected_idx = int(choice) - 1
    space_id, space_name = spaces[selected_idx]
    save_selected_space(space_id)
    return space_id, space_name


def _configured_default_space(spaces: list[tuple[str, str]]) -> tuple[str, str] | None:
    """Return configured AnyType default space when it is available."""
    try:
        from jarvis.config import load_config

        cfg = load_config()
        default_id = cfg.backends.anytype.default_space_id
    except Exception:
        default_id = None

    if default_id:
        for space_id, space_name in spaces:
            if space_id == default_id:
                return space_id, space_name

    return None


def get_space_selections(
    client: AnyTypeClient,
    spaces: tuple[str, ...] | None = None,
) -> list[tuple[str, str]]:
    """Get one or more target spaces for a journal write.

    Resolution order:
        1. Explicit repeated ``--space`` args (name or ID)
        2. Single available space (auto-select)
        3. Interactive multi-select prompt (TTY only)
        4. Existing single-space selection behavior for non-interactive contexts

    Args:
        client: Connected AnyType client
        spaces: Optional repeated space names or IDs from the CLI

    Returns:
        List of (space_id, space_name) tuples.
    """
    import sys

    from jarvis.state import save_selected_space

    requested = tuple(s for s in (spaces or ()) if s)
    available_spaces = client.get_spaces()

    if not available_spaces:
        console.print("[red]No AnyType spaces found.[/red]")
        raise SystemExit(1)

    if requested:
        return _resolve_requested_spaces(available_spaces, requested)

    if len(available_spaces) == 1:
        space_id, space_name = available_spaces[0]
        save_selected_space(space_id)
        return [(space_id, space_name)]

    if sys.stdin.isatty():
        return _prompt_for_space_selections(available_spaces)

    return [get_space_selection(client)]


def _resolve_requested_spaces(
    available_spaces: list[tuple[str, str]],
    requested: tuple[str, ...],
) -> list[tuple[str, str]]:
    """Resolve repeated space args against available spaces."""
    resolved: list[tuple[str, str]] = []
    seen_ids: set[str] = set()
    missing: list[str] = []

    for requested_space in requested:
        match = next(
            (
                (space_id, space_name)
                for space_id, space_name in available_spaces
                if space_id == requested_space or space_name.lower() == requested_space.lower()
            ),
            None,
        )
        if not match:
            missing.append(requested_space)
            continue

        space_id, _ = match
        if space_id not in seen_ids:
            resolved.append(match)
            seen_ids.add(space_id)

    if missing:
        console.print(f"[red]Space not found: {', '.join(missing)}[/red]")
        console.print("[dim]Available spaces:[/dim]")
        for _, space_name in available_spaces:
            console.print(f"  • {space_name}")
        raise SystemExit(1)

    return resolved


def _prompt_for_space_selections(
    available_spaces: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Prompt for one or more spaces using comma-separated numbers."""
    from jarvis.state import save_selected_space

    console.print()
    console.print("[bold]Select journal spaces:[/bold]")
    for i, (_, space_name) in enumerate(available_spaces, 1):
        console.print(f"  [cyan]{i}[/cyan]. {space_name}")
    console.print("[dim]Enter numbers separated by commas, or 'all'.[/dim]")

    while True:
        choice = Prompt.ask("Spaces", default="1").strip().lower()
        if choice == "all":
            return available_spaces

        selected_indexes: list[int] = []
        invalid = False
        for part in choice.split(","):
            stripped = part.strip()
            if not stripped:
                continue
            try:
                idx = int(stripped)
            except ValueError:
                invalid = True
                break
            if not 1 <= idx <= len(available_spaces):
                invalid = True
                break
            if idx not in selected_indexes:
                selected_indexes.append(idx)

        if not invalid and selected_indexes:
            selected = [available_spaces[idx - 1] for idx in selected_indexes]
            if len(selected) == 1:
                save_selected_space(selected[0][0])
            return selected

        console.print("[red]Enter valid numbers from the list, or 'all'.[/red]")


def get_anthropic_client():  # type: ignore[return]
    """Get Anthropic client from environment.

    Returns:
        Configured Anthropic client

    Raises:
        RuntimeError: If API key not configured or package not installed
    """
    import os

    try:
        from anthropic import Anthropic
    except ImportError:
        raise RuntimeError("anthropic package not installed. Run: uv pip install anthropic")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable not set")

    return Anthropic(api_key=api_key)


def call_ai(
    system: str,
    prompt: str,
    max_tokens: int = 1000,
    model: str = "claude-sonnet-4-20250514",
) -> str | None:
    """Call Anthropic API with standard error handling.

    Args:
        system: System prompt
        prompt: User prompt
        max_tokens: Maximum response tokens
        model: Model to use

    Returns:
        AI response text or None if call fails
    """
    try:
        client = get_anthropic_client()
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        if response.content and len(response.content) > 0:
            return response.content[0].text.strip()
    except Exception:
        pass  # Caller handles fallback
    return None


def generate_title(content: str) -> str:
    """Generate a title for the entry using AI.

    Args:
        content: Journal entry content

    Returns:
        Generated title
    """
    prompt = format_title_prompt(content)
    title = call_ai(TITLE_GENERATION_SYSTEM, prompt, max_tokens=100)

    if title:
        # Clean up any quotes or extra formatting
        return title.strip("\"'")

    # Fallback: use first line or truncated content
    console.print("[yellow]Could not generate title, using fallback[/yellow]")
    first_line = content.split("\n")[0][:50]
    return first_line if first_line else "Untitled Entry"


@click.group(name="journal")
def journal_cli() -> None:
    """AI-powered journaling for AnyType.

    Write, search, and analyze your journal entries with AI assistance.
    """
    pass


@journal_cli.command(name="write")
@click.argument("text", required=False, default=None)
@click.option("-e", "--editor", is_flag=True, help="Open editor for entry")
@click.option("-i", "--interactive", is_flag=True, help="Interactive multi-line input")
@click.option(
    "-f",
    "--file",
    "file_path",
    default=None,
    type=click.Path(exists=True),
    help="Read entry content from a file (prepends AI summary)",
)
@click.option(
    "--space",
    "spaces",
    multiple=True,
    help="Space name or ID (repeatable; omit for interactive multi-select)",
)
@click.option("--title", default=None, help="Custom title (skips AI generation)")
@click.option("--no-deep-dive", is_flag=True, help="Skip deep dive prompt")
def write_entry(
    text: str | None,
    editor: bool,
    interactive: bool,
    file_path: str | None,
    spaces: tuple[str, ...],
    title: str | None,
    no_deep_dive: bool,
) -> None:
    """Write a new journal entry.

    Examples:
        jarvis journal write "Had a breakthrough today"
        jarvis journal write -e
        jarvis journal write -i
        jarvis journal write --file ./notes.md
    """
    try:
        # Determine capture mode
        mode, initial_text = determine_capture_mode(
            text=text,
            interactive=interactive,
            force_editor=editor,
            file_path=file_path,
        )

        # Show mode info
        if mode == CaptureMode.EDITOR:
            console.print("[dim]Opening editor...[/dim]")
        elif mode == CaptureMode.INTERACTIVE:
            console.print("[dim]Interactive mode (press Enter twice to finish)[/dim]")
        elif mode == CaptureMode.FILE:
            console.print(f"[dim]Reading from file: {file_path}[/dim]")

        # Capture entry content
        content = capture_entry(mode, initial_text)

        if not content:
            console.print("[yellow]No content entered. Entry cancelled.[/yellow]")
            return

        # Generate or use provided title
        if title:
            entry_title = title
            console.print(f"[dim]Using title: {entry_title}[/dim]")
        else:
            console.print("[dim]Generating title...[/dim]")
            entry_title = generate_title(content)
            console.print(f"[dim]Title: {entry_title}[/dim]")

        content = strip_duplicate_title_heading(content, entry_title)

        # For file mode: generate summary and compose combined content
        if mode == CaptureMode.FILE:
            content = _compose_file_entry(content, file_path)

        # Save draft immediately for recovery
        draft_path = save_draft(content)
        console.print(f"[dim]Draft saved: {draft_path.name}[/dim]")

        # Connect to AnyType
        client = get_connected_client()
        target_spaces = get_space_selections(client, spaces)
        entry_date = date.today()

        successes: list[tuple[str, JournalEntryReference]] = []
        failures: list[tuple[str, str]] = []

        for space_id, space_name in target_spaces:
            try:
                ref = _save_entry_to_space(
                    client=client,
                    space_id=space_id,
                    space_name=space_name,
                    entry_date=entry_date,
                    title=entry_title,
                    content=content,
                )
                successes.append((space_name, ref))
            except Exception as e:
                failures.append((space_name, str(e)))

        if not failures:
            try:
                draft_path.unlink()
            except OSError:
                pass  # Non-critical: draft cleanup failed

        _display_write_summary(successes, failures)

        if failures:
            console.print("[dim]Draft kept for recovery.[/dim]")
            raise SystemExit(1)

        if not no_deep_dive:
            if len(successes) == 1:
                _offer_deep_dive(successes[0][1].id, content)
            elif len(successes) > 1:
                console.print("[dim]Deep dive skipped for multi-space write.[/dim]")

    except SystemExit:
        raise
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print("[dim]Your draft has been saved for recovery.[/dim]")
        raise SystemExit(1)


def _save_entry_to_space(
    client: AnyTypeClient,
    space_id: str,
    space_name: str,
    entry_date: date,
    title: str,
    content: str,
) -> JournalEntryReference:
    """Save a journal entry to one target space and persist its local reference."""
    console.print(f"[dim]Saving to {space_name}...[/dim]")
    hierarchy = JournalHierarchy(client, space_id)

    entry_id, _, _, _ = hierarchy.create_entry(
        entry_date=entry_date,
        title=title,
        content=content,
    )

    full_title = f"{entry_date.day} - {title}"
    path = hierarchy.get_path(entry_date)

    ref = JournalEntryReference(
        id=entry_id,
        space_id=space_id,
        path=path,
        title=full_title,
        entry_date=entry_date,
        created_at=datetime.now(),
        content_preview=(
            content[:CONTENT_PREVIEW_LENGTH] if len(content) > CONTENT_PREVIEW_LENGTH else content
        ),
    )
    save_entry_reference(ref)
    return ref


def _display_write_summary(
    successes: list[tuple[str, JournalEntryReference]],
    failures: list[tuple[str, str]],
) -> None:
    """Display a per-space journal write summary."""
    if len(successes) == 1 and not failures:
        space_name, ref = successes[0]
        console.print()
        console.print(
            Panel(
                f"[green]Entry saved![/green]\n\n"
                f"[bold]{ref.title}[/bold]\n"
                f"[dim]{ref.path}[/dim]\n"
                f"[dim]Space: {space_name}[/dim]",
                title="Journal",
                border_style="green",
            )
        )
        return

    lines: list[str] = []
    if successes:
        lines.append("[green]Saved[/green]")
        for space_name, ref in successes:
            lines.append(f"  ✓ {space_name}: {ref.title} ([dim]{ref.path}[/dim])")

    if failures:
        if lines:
            lines.append("")
        lines.append("[red]Failed[/red]")
        for space_name, error in failures:
            lines.append(f"  ✗ {space_name}: {error}")

    border_style = "red" if failures else "green"
    console.print()
    console.print(Panel("\n".join(lines), title="Journal", border_style=border_style))


def _compose_file_entry(file_content: str, file_path: str | None) -> str:
    """Compose a journal entry from file content with AI summary.

    Generates an AI summary paragraph and prepends it above the full
    file content, separated by a horizontal rule.

    Args:
        file_content: The raw file content
        file_path: Path to the source file (for filename context)

    Returns:
        Combined content: summary + separator + full file content
    """
    from pathlib import Path

    filename = Path(file_path).name if file_path else "unknown"

    console.print("[dim]Generating summary...[/dim]")

    prompt = format_file_summary_prompt(file_content, filename)
    summary = call_ai(FILE_SUMMARY_SYSTEM, prompt, max_tokens=300)

    if summary:
        return f"{summary}\n\n---\n\n{file_content}"
    else:
        console.print("[yellow]Could not generate summary, using file content only.[/yellow]")
        return file_content


def _offer_deep_dive(entry_id: str, content: str) -> None:
    """Offer the user a deep dive on their entry.

    Args:
        entry_id: The saved entry's ID
        content: Entry content for analysis
    """
    console.print()

    if not Confirm.ask("Would you like a deep dive on this entry?", default=False):
        return

    console.print()
    console.print("[dim]What aspect would you like to explore?[/dim]")
    console.print("[dim]Examples: feelings, action items, patterns, gratitude[/dim]")
    console.print()

    focus = Prompt.ask("Focus", default="explore the underlying themes")

    console.print()
    console.print("[dim]Generating deep dive...[/dim]")

    try:
        from jarvis.journal.models import DeepDive
        from jarvis.journal.prompts import DEEP_DIVE_SYSTEM, format_deep_dive_prompt
        from jarvis.journal.state import save_deep_dive

        prompt = format_deep_dive_prompt(content, focus)
        ai_response = call_ai(DEEP_DIVE_SYSTEM, prompt, max_tokens=1000)

        if not ai_response:
            console.print("[yellow]Could not generate deep dive[/yellow]")
            return

        # Display the deep dive
        console.print()
        console.print(
            Panel(
                ai_response,
                title=f"Deep Dive: {focus}",
                border_style="cyan",
            )
        )

        # Save the deep dive
        dd = DeepDive(
            id=f"dd_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            entry_id=entry_id,
            user_request=focus,
            ai_response=ai_response,
            format_type=focus.split()[0].lower(),  # Simple type extraction
            created_at=datetime.now(),
        )
        save_deep_dive(entry_id, dd)
        console.print("[dim]Deep dive saved.[/dim]")

    except Exception as e:
        console.print(f"[yellow]Could not generate deep dive: {e}[/yellow]")


@journal_cli.command(name="list")
@click.option("-n", "--limit", default=10, help="Number of entries to show")
@click.option("--all", "show_all", is_flag=True, help="Show all entries")
def list_entries(limit: int, show_all: bool) -> None:
    """List recent journal entries.

    Examples:
        jarvis journal list
        jarvis journal list -n 20
        jarvis journal list --all
    """
    from rich.table import Table

    from jarvis.journal.state import load_entries

    try:
        all_entries = load_entries()
        total_count = len(all_entries)

        if not all_entries:
            console.print("[dim]No journal entries yet.[/dim]")
            console.print("[dim]Create one with: jarvis journal write[/dim]")
            return

        # Apply limit unless --all
        entries = all_entries if show_all else all_entries[:limit]

        # Create table
        table = Table(title="Journal Entries", show_header=True, header_style="bold")
        table.add_column("Date", style="cyan", width=12)
        table.add_column("Title", style="white")
        table.add_column("DD", style="dim", width=3)  # Deep dive indicator

        for entry in entries:
            date_str = entry.entry_date.strftime("%Y-%m-%d")
            dd_indicator = "✓" if entry.has_deep_dive else ""
            table.add_row(date_str, entry.title, dd_indicator)

        console.print()
        console.print(table)
        console.print()

        if not show_all and total_count > limit:
            msg = f"Showing {limit} of {total_count} entries. Use --all to see all."
            console.print(f"[dim]{msg}[/dim]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)


@journal_cli.command(name="read")
@click.argument("entry_id", required=False, default=None)
@click.option("-n", "--number", type=int, help="Read entry by list number (1=most recent)")
@click.option("--latest", is_flag=True, help="Read the most recent entry")
def read_entry(entry_id: str | None, number: int | None, latest: bool) -> None:
    """Read a journal entry.

    Examples:
        jarvis journal read --latest
        jarvis journal read -n 1
        jarvis journal read entry_abc123
    """
    from jarvis.journal.state import get_entry_reference, load_entries

    try:
        entries = load_entries()

        if not entries:
            console.print("[dim]No journal entries yet.[/dim]")
            return

        # Determine which entry to read
        target_entry = None

        if latest or (entry_id is None and number is None):
            target_entry = entries[0]
        elif number is not None:
            if 1 <= number <= len(entries):
                target_entry = entries[number - 1]
            else:
                max_num = len(entries)
                console.print(f"[red]Entry number {number} not found. Valid: 1-{max_num}[/red]")
                return
        elif entry_id:
            target_entry = get_entry_reference(entry_id)
            if not target_entry:
                console.print(f"[red]Entry not found: {entry_id}[/red]")
                return

        if not target_entry:
            console.print("[red]Could not determine which entry to read.[/red]")
            return

        # Display entry info
        console.print()
        console.print(
            Panel(
                f"[bold]{target_entry.title}[/bold]\n\n"
                f"[dim]Date:[/dim] {target_entry.entry_date}\n"
                f"[dim]Path:[/dim] {target_entry.path}\n"
                f"[dim]ID:[/dim] {target_entry.id}\n\n"
                f"{target_entry.content_preview}"
                f"{'...' if len(target_entry.content_preview) >= CONTENT_PREVIEW_LENGTH else ''}",
                title="Journal Entry",
                border_style="blue",
            )
        )

        # Show deep dive indicator
        if target_entry.has_deep_dive:
            console.print()
            console.print("[cyan]This entry has deep dive analysis.[/cyan]")

        # Try to fetch full content from AnyType
        try:
            client = get_connected_client()
            full_content = client.get_page_content(target_entry.space_id, target_entry.id)
            if full_content and full_content != target_entry.content_preview:
                console.print()
                console.print("[dim]Full content from AnyType:[/dim]")
                console.print()
                console.print(full_content)
        except Exception:
            # Silently fail - we showed the preview at least
            pass

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)


@journal_cli.command(name="search")
@click.argument("query")
@click.option("-n", "--limit", default=10, help="Maximum results to show")
def search_entries(query: str, limit: int) -> None:
    """Search journal entries.

    Searches titles and content previews for matching text.

    Examples:
        jarvis journal search "project"
        jarvis journal search feelings -n 20
    """
    from rich.table import Table

    from jarvis.journal.state import search_entries as do_search

    try:
        results = do_search(query, limit=limit)

        if not results:
            console.print(f"[dim]No entries found matching '{query}'[/dim]")
            return

        # Create results table
        table = Table(title=f"Search: '{query}'", show_header=True, header_style="bold")
        table.add_column("Date", style="cyan", width=12)
        table.add_column("Title", style="white")
        table.add_column("Preview", style="dim", max_width=40)

        for entry in results:
            date_str = entry.entry_date.strftime("%Y-%m-%d")
            content = entry.content_preview
            preview = content[:40] + "..." if len(content) > 40 else content
            table.add_row(date_str, entry.title, preview)

        console.print()
        console.print(table)
        console.print()
        console.print(f"[dim]Found {len(results)} matching entries[/dim]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)


@journal_cli.command(name="insights")
@click.option("--since", default="2 weeks", help="Analysis window (e.g., '2 weeks', '1 month')")
@click.option("--limit", default=50, help="Max entries to analyze")
def get_insights(since: str, limit: int) -> None:
    """AI analysis across journal entries.

    Analyzes patterns and themes in recent journal entries.

    Examples:
        jarvis journal insights
        jarvis journal insights --since "1 month"
        jarvis journal insights --limit 20
    """
    from jarvis.journal.prompts import INSIGHTS_SYSTEM, format_insights_prompt
    from jarvis.journal.state import get_entries_by_date_range

    try:
        # Parse time range
        end_date = date.today()
        start_date = _parse_since(since, end_date)

        # Get entries in range
        entries = get_entries_by_date_range(start_date, end_date, limit=limit)

        if not entries:
            console.print("[dim]No entries found in the specified time range.[/dim]")
            return

        if len(entries) < 2:
            console.print("[dim]Need at least 2 entries for meaningful insights.[/dim]")
            return

        # Format entries for analysis
        entries_text = "\n\n---\n\n".join(
            [f"**{e.entry_date} - {e.title}**\n{e.content_preview}" for e in entries]
        )

        # Create time range description
        time_range = f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}"

        console.print(f"[dim]Analyzing {len(entries)} entries ({time_range})...[/dim]")
        console.print()

        # Get AI insights
        prompt = format_insights_prompt(entries_text, time_range, len(entries))
        insights = call_ai(INSIGHTS_SYSTEM, prompt, max_tokens=1500)

        if not insights:
            console.print("[yellow]Could not generate insights[/yellow]")
            return

        console.print(
            Panel(
                insights,
                title=f"Insights from {len(entries)} Entries",
                border_style="magenta",
            )
        )

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)


def _parse_since(since: str, end_date: date) -> date:
    """Parse a 'since' string into a start date.

    Args:
        since: Time description (e.g., "2 weeks", "1 month", "3 days")
        end_date: The end date to calculate from

    Returns:
        Calculated start date
    """
    from datetime import timedelta

    since = since.lower().strip()

    # Parse patterns like "2 weeks", "1 month", "3 days"
    parts = since.split()
    if len(parts) == 2:
        try:
            num = int(parts[0])
            unit = parts[1].rstrip("s")  # Remove trailing 's'

            if unit == "day":
                return end_date - timedelta(days=num)
            elif unit == "week":
                return end_date - timedelta(weeks=num)
            elif unit == "month":
                # Approximate months as 30 days
                return end_date - timedelta(days=num * 30)
            elif unit == "year":
                return end_date - timedelta(days=num * 365)
        except ValueError:
            pass

    # Default to 2 weeks if parsing fails
    console.print(f"[yellow]Could not parse '{since}', using 2 weeks.[/yellow]")
    return end_date - timedelta(weeks=2)


# Create alias for jarvis j -> jarvis journal write
j = journal_cli
