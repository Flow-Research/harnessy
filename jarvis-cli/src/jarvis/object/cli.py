"""Object CLI commands for inspecting and updating any backend object by ID.

Supports:
  - Pasting raw object IDs or AnyType/Notion URLs
  - Displaying all properties in a rich table
  - Interactive property editing (back-and-forth prompts)
  - Inline flag-based updates for scripted use
"""

import re

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from jarvis.adapters import AdapterRegistry
from jarvis.adapters.base import KnowledgeBaseAdapter
from jarvis.adapters.exceptions import (
    AuthError,
    ConnectionError as AdapterConnectionError,
    NotFoundError,
    ValidationError as AdapterValidationError,
)
from jarvis.models import BackendObject
from jarvis.state import save_selected_space

console = Console()


# ============================================================================
# ID Parsing
# ============================================================================

# Patterns for extracting object IDs from pasted URLs/links
_ID_PATTERNS = [
    # Notion page URLs:  https://www.notion.so/workspace/Page-Title-<32hex>
    # or https://www.notion.so/<32hex>
    re.compile(r"notion\.so/(?:[^/]+/)?(?:[^/]*-)?([a-f0-9]{32})(?:\?|$|#)", re.I),
    # Notion page IDs with dashes: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    re.compile(r"^([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})$", re.I),
    # AnyType deeplink: anytype://object/<id>
    re.compile(r"anytype://(?:object/)?(.+?)(?:\?|$)", re.I),
    # Raw AnyType CID (bafyrei...)
    re.compile(r"^(bafyrei[a-z2-7]{46,})$", re.I),
    # Generic UUID
    re.compile(r"^([a-f0-9]{32})$", re.I),
]


def parse_object_id(raw: str) -> str:
    """Extract an object ID from a raw string (URL, deeplink, or plain ID).

    Args:
        raw: User-provided string -- could be a URL, deeplink, or bare ID.

    Returns:
        Extracted object ID string.
    """
    raw = raw.strip()

    for pattern in _ID_PATTERNS:
        match = pattern.search(raw)
        if match:
            return match.group(1)

    # If nothing matched, return as-is (the backend will validate)
    return raw


# ============================================================================
# Helpers
# ============================================================================


def _get_adapter(backend: str | None = None) -> KnowledgeBaseAdapter:
    """Get the configured adapter instance."""
    return AdapterRegistry.get_adapter(backend)


def _get_space(
    adapter: KnowledgeBaseAdapter, space_arg: str | None
) -> tuple[str, str]:
    """Get space ID from argument or saved selection."""
    from jarvis.cli import select_space

    spaces = adapter.list_spaces()

    if space_arg:
        for space in spaces:
            if space_arg.lower() in space.name.lower() or space_arg == space.id:
                save_selected_space(space.id)
                return space.id, space.name
        console.print(f"[yellow]Space '{space_arg}' not found.[/yellow]")
        raise SystemExit(1)

    return select_space(adapter)


def _display_object(obj: BackendObject) -> None:
    """Display a BackendObject in a rich panel with property table.

    Args:
        obj: The object to display.
    """
    # Header
    icon = obj.icon or ""
    title = f"{icon} {obj.name}".strip()
    console.print()
    console.print(
        Panel(
            f"[bold]{title}[/bold]\n"
            f"[dim]Type: {obj.object_type}  |  Backend: {obj.backend}[/dim]",
            border_style="cyan",
        )
    )

    # Metadata
    console.print(f"  [dim]ID:[/dim]       {obj.id}")
    if obj.created_at:
        console.print(f"  [dim]Created:[/dim]  {obj.created_at.strftime('%Y-%m-%d %H:%M')}")
    if obj.updated_at:
        console.print(f"  [dim]Updated:[/dim]  {obj.updated_at.strftime('%Y-%m-%d %H:%M')}")
    console.print()

    # Properties table
    editable = obj.get_editable_properties()
    system = [p for p in obj.properties if p.is_system]

    if editable:
        table = Table(title="Properties", show_header=True, header_style="bold cyan")
        table.add_column("Key", style="cyan", min_width=12)
        table.add_column("Name", style="dim")
        table.add_column("Format", style="dim")
        table.add_column("Value", min_width=20)

        for prop in editable:
            table.add_row(
                prop.key,
                prop.name if prop.name != prop.key else "",
                prop.format.value,
                prop.display_value or "[dim]-[/dim]",
            )

        console.print(table)
        console.print()

    if system:
        sys_table = Table(
            title="System Properties (read-only)",
            show_header=True,
            header_style="bold dim",
        )
        sys_table.add_column("Key", style="dim")
        sys_table.add_column("Value", style="dim")

        for prop in system:
            val = prop.display_value
            if val and len(val) > 60:
                val = val[:57] + "..."
            sys_table.add_row(prop.key, val or "-")

        console.print(sys_table)
        console.print()

    # Content preview
    if obj.content:
        preview = obj.content[:500]
        if len(obj.content) > 500:
            preview += "\n..."
        console.print(
            Panel(preview, title="Content Preview", border_style="dim", width=80)
        )
        console.print()


def _interactive_update(
    adapter: KnowledgeBaseAdapter,
    space_id: str,
    obj: BackendObject,
) -> None:
    """Run an interactive update loop on the object.

    Prompts the user to select properties to edit and enter new values,
    until they choose to finish.

    Args:
        adapter: Connected adapter instance.
        space_id: Space ID.
        obj: The BackendObject to update.
    """
    from rich.prompt import Prompt

    editable = obj.get_editable_properties()
    if not editable:
        console.print("[yellow]No editable properties on this object.[/yellow]")
        return

    console.print("[bold]Interactive Edit Mode[/bold]")
    console.print("[dim]Enter property key and new value. Type 'done' to finish.[/dim]")
    console.print()

    # Show quick reference
    console.print("[dim]Editable properties:[/dim]")
    for p in editable:
        val_preview = p.display_value[:40] if p.display_value else "-"
        console.print(f"  [cyan]{p.key}[/cyan] ({p.format.value}) = {val_preview}")
    console.print(f"  [cyan]name[/cyan] (text) = {obj.name}")
    console.print()

    while True:
        key = Prompt.ask(
            "[bold]Property to edit[/bold] (or 'done')",
            default="done",
        )

        if key.lower() in ("done", "q", "quit", "exit"):
            break

        # Validate the key exists
        if key == "name":
            current = obj.name
            fmt_hint = "text"
        else:
            prop = obj.get_property(key)
            if prop is None:
                console.print(f"[red]Property '{key}' not found.[/red]")
                console.print("[dim]Available keys: " + ", ".join(p.key for p in editable) + "[/dim]")
                continue
            if prop.is_system:
                console.print(f"[red]'{key}' is a system property and cannot be edited.[/red]")
                continue
            current = prop.display_value
            fmt_hint = prop.format.value

        console.print(f"  [dim]Current value:[/dim] {current or '(empty)'}")
        console.print(f"  [dim]Format:[/dim] {fmt_hint}")
        new_value = Prompt.ask("  [bold]New value[/bold]")

        if not new_value:
            console.print("  [dim]Skipped (empty value).[/dim]")
            continue

        # Apply the update
        try:
            obj = adapter.update_object(
                space_id=space_id,
                object_id=obj.id,
                updates={key: new_value},
            )
            console.print(f"  [green]Updated {key}[/green]")
        except AdapterValidationError as e:
            console.print(f"  [red]Validation error: {e}[/red]")
        except Exception as e:
            console.print(f"  [red]Update failed: {e}[/red]")

    console.print()
    console.print("[green]Done.[/green]")

    # Show final state
    _display_object(obj)


# ============================================================================
# CLI Commands
# ============================================================================


@click.group(name="object")
def object_cli() -> None:
    """Inspect and update any object by ID.

    Paste an object ID, AnyType link, or Notion URL to fetch
    and inspect any object from your knowledge base.
    """
    pass


@object_cli.command(name="get")
@click.argument("object_id_or_url", required=True)
@click.option("--space", default=None, help="Space name or ID to use")
@click.option("--backend", default=None, help="Backend to use (anytype, notion)")
@click.option("--raw", is_flag=True, help="Show raw API response as JSON")
def get_object(
    object_id_or_url: str,
    space: str | None,
    backend: str | None,
    raw: bool,
) -> None:
    """Fetch and display an object by ID or URL.

    Accepts raw IDs, AnyType deeplinks, or Notion page URLs.

    Examples:
        jarvis object get bafyreig...
        jarvis object get https://notion.so/My-Page-abc123def456...
        jarvis o bafyreig...
    """
    object_id = parse_object_id(object_id_or_url)

    try:
        adapter = _get_adapter(backend)
        adapter.connect()

        space_id, space_name = _get_space(adapter, space)
        console.print(f"[dim]Space: {space_name} | Backend: {adapter.backend_name}[/dim]")

        obj = adapter.get_object(space_id, object_id)

        if raw:
            import json
            console.print(json.dumps(obj.raw, indent=2, default=str))
        else:
            _display_object(obj)

    except NotFoundError:
        console.print(f"[red]Object not found: {object_id}[/red]")
        console.print("[dim]Check the ID and make sure the object exists in this space.[/dim]")
        raise SystemExit(1)
    except AdapterConnectionError as e:
        console.print(f"[red]Connection error: {e}[/red]")
        raise SystemExit(1)
    except AuthError as e:
        console.print(f"[red]Authentication error: {e}[/red]")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)


@object_cli.command(name="edit")
@click.argument("object_id_or_url", required=True)
@click.option("--space", default=None, help="Space name or ID to use")
@click.option("--backend", default=None, help="Backend to use (anytype, notion)")
@click.option("--set", "set_values", multiple=True, help="Set property: key=value (repeatable)")
@click.option("--body", "body_text", default=None, help="Replace body/content with this markdown text")
@click.option(
    "--body-file", "body_file", default=None,
    type=click.Path(exists=True),
    help="Replace body/content with contents of this file",
)
def edit_object(
    object_id_or_url: str,
    space: str | None,
    backend: str | None,
    set_values: tuple[str, ...],
    body_text: str | None,
    body_file: str | None,
) -> None:
    """Inspect and edit an object's properties and content.

    Without flags, enters interactive mode. With --set, applies
    property updates. With --body or --body-file, replaces the
    object's markdown body content.

    Examples:
        jarvis object edit bafyreig...                          # Interactive
        jarvis object edit bafyreig... --set due_date=2026-04-01  # Inline
        jarvis object edit bafyreig... --body "# New Content"     # Replace body
        jarvis object edit bafyreig... --body-file content.md     # From file
    """
    object_id = parse_object_id(object_id_or_url)

    try:
        adapter = _get_adapter(backend)
        adapter.connect()

        space_id, space_name = _get_space(adapter, space)
        console.print(f"[dim]Space: {space_name} | Backend: {adapter.backend_name}[/dim]")

        obj = adapter.get_object(space_id, object_id)

        # Resolve body content from --body or --body-file
        body_content = body_text
        if body_file:
            with open(body_file) as f:
                body_content = f.read()

        if set_values or body_content is not None:
            # Inline mode: parse key=value pairs and apply
            updates: dict[str, object] = {}
            for kv in set_values:
                if "=" not in kv:
                    console.print(f"[red]Invalid format: '{kv}'. Use key=value[/red]")
                    raise SystemExit(1)
                key, _, value = kv.partition("=")
                updates[key.strip()] = value.strip()

            if body_content is not None:
                updates["body"] = body_content

            console.print(f"[dim]Applying {len(updates)} update(s)...[/dim]")
            try:
                obj = adapter.update_object(
                    space_id=space_id,
                    object_id=obj.id,
                    updates=updates,
                )
                console.print("[green]Updated successfully.[/green]")
                _display_object(obj)
            except AdapterValidationError as e:
                console.print(f"[red]Validation error: {e}[/red]")
                raise SystemExit(1)
        else:
            # Interactive mode: show object then prompt for edits
            _display_object(obj)
            _interactive_update(adapter, space_id, obj)

    except NotFoundError:
        console.print(f"[red]Object not found: {object_id}[/red]")
        raise SystemExit(1)
    except AdapterConnectionError as e:
        console.print(f"[red]Connection error: {e}[/red]")
        raise SystemExit(1)
    except AuthError as e:
        console.print(f"[red]Authentication error: {e}[/red]")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)


# Alias: 'o' command does get by default, edit if --set is provided
@click.command(name="o")
@click.argument("object_id_or_url", required=True)
@click.option("--space", default=None, help="Space name or ID")
@click.option("--backend", default=None, help="Backend to use")
@click.option("--set", "set_values", multiple=True, help="Set property: key=value")
@click.option("--body", "body_text", default=None, help="Replace body/content markdown")
@click.option(
    "--body-file", "body_file", default=None,
    type=click.Path(exists=True),
    help="Replace body/content from file",
)
@click.option("--raw", is_flag=True, help="Show raw JSON response")
@click.option("--edit", "-e", is_flag=True, help="Enter interactive edit mode")
def quick_object(
    object_id_or_url: str,
    space: str | None,
    backend: str | None,
    set_values: tuple[str, ...],
    body_text: str | None,
    body_file: str | None,
    raw: bool,
    edit: bool,
) -> None:
    """Quick object lookup and edit.

    Fetches an object by ID/URL and shows its details.
    Add --set to update properties, --body to replace content,
    or --edit for interactive mode.

    Examples:
        jarvis o bafyreig...                               # Show object
        jarvis o bafyreig... --edit                         # Interactive edit
        jarvis o bafyreig... --set due_date=2026-04-01      # Quick update
        jarvis o bafyreig... --body "# New Content"         # Replace body
        jarvis o bafyreig... --body-file content.md         # Body from file
    """
    object_id = parse_object_id(object_id_or_url)

    try:
        adapter = _get_adapter(backend)
        adapter.connect()

        space_id, space_name = _get_space(adapter, space)
        console.print(f"[dim]Space: {space_name} | Backend: {adapter.backend_name}[/dim]")

        obj = adapter.get_object(space_id, object_id)

        # Resolve body content
        body_content = body_text
        if body_file:
            with open(body_file) as f:
                body_content = f.read()

        if set_values or body_content is not None:
            # Apply inline updates
            updates: dict[str, object] = {}
            for kv in set_values:
                if "=" not in kv:
                    console.print(f"[red]Invalid format: '{kv}'. Use key=value[/red]")
                    raise SystemExit(1)
                key, _, value = kv.partition("=")
                updates[key.strip()] = value.strip()

            if body_content is not None:
                updates["body"] = body_content

            console.print(f"[dim]Applying {len(updates)} update(s)...[/dim]")
            try:
                obj = adapter.update_object(
                    space_id=space_id,
                    object_id=obj.id,
                    updates=updates,
                )
                console.print("[green]Updated successfully.[/green]")
            except AdapterValidationError as e:
                console.print(f"[red]Validation error: {e}[/red]")
                raise SystemExit(1)

        if raw:
            import json
            console.print(json.dumps(obj.raw, indent=2, default=str))
        else:
            _display_object(obj)

        if edit and not set_values and body_content is None:
            _interactive_update(adapter, space_id, obj)

    except NotFoundError:
        console.print(f"[red]Object not found: {object_id}[/red]")
        raise SystemExit(1)
    except AdapterConnectionError as e:
        console.print(f"[red]Connection error: {e}[/red]")
        raise SystemExit(1)
    except AuthError as e:
        console.print(f"[red]Authentication error: {e}[/red]")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)
