"""Click command group ``jarvis sync`` — preset CRUD plus the actual ``sync run``.

UX patterns mirror the rest of jarvis:
    - rich.console.Console for output, rich.prompt for input.
    - Confirm/Prompt for interactive flows; click options for ad-hoc runs.
    - Errors print in red and exit with status 1; we never raise unhandled.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import cast

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from jarvis.sync.engine import (
    SyncAdapter,
    SyncOperation,
    SyncResult,
    UnsupportedMode,
    run_sync,
)
from jarvis.sync.object_link import AnytypeLink, InvalidLinkError, parse_link
from jarvis.sync.presets import (
    Preset,
    PresetOptions,
    load_registry,
    save_registry,
)
from jarvis.sync.state import load_state, save_state

console = Console()


@click.group(name="sync")
def sync_group() -> None:
    """Sync local folders/files to an Anytype Collection."""


# ---------------------------------------------------------------------------
# `jarvis sync run`
# ---------------------------------------------------------------------------


@sync_group.command(name="run")
@click.option("--preset", "preset_name", type=str, default=None, help="Use a saved preset.")
@click.option(
    "--source",
    "source_str",
    type=click.Path(exists=False),
    default=None,
    help="Source path (file or directory). Overrides the preset's source.",
)
@click.option(
    "--destination",
    "destination_str",
    type=str,
    default=None,
    help="Anytype object link for the target Collection. Overrides the preset's destination.",
)
@click.option("--prune", is_flag=True, help="Delete on Anytype what's gone locally.")
@click.option("--dry-run", is_flag=True, help="Show what would change without touching Anytype.")
@click.option("--yes", "assume_yes", is_flag=True, help="Skip confirmation prompts for writes.")
@click.option(
    "--include-extension",
    "include_extension",
    multiple=True,
    help="Additional text file extension to include, e.g. .md or py. Repeatable.",
)
@click.option(
    "--ignore",
    "ignore_glob",
    multiple=True,
    help="Additional glob to ignore during traversal. Repeatable.",
)
@click.option(
    "--skip-destination-check",
    is_flag=True,
    help="Do not verify that the destination object is an Anytype Collection before writing.",
)
@click.option(
    "--unsupported-mode",
    type=click.Choice(["upload", "warn", "stub", "error"]),
    default=None,
    help=("How to handle files that cannot sync as text: upload, warn, stub, or error."),
)
def run_cmd(
    preset_name: str | None,
    source_str: str | None,
    destination_str: str | None,
    prune: bool,
    dry_run: bool,
    assume_yes: bool,
    include_extension: tuple[str, ...],
    ignore_glob: tuple[str, ...],
    skip_destination_check: bool,
    unsupported_mode: str | None,
) -> None:
    """Run a sync. Prompts interactively for any missing source/destination."""
    preset: Preset | None = None
    if preset_name:
        registry = load_registry()
        preset = registry.get(preset_name)
        if preset is None:
            console.print(f"[red]Unknown preset: {preset_name}[/red]")
            raise SystemExit(1)

    # Source resolution: CLI flag > preset > prompt
    source = _resolve_source(source_str, preset)
    if source is None:
        return  # user cancelled

    # Space + destination resolution
    destination = _resolve_destination(destination_str, preset)
    if destination is None:
        return

    if preset is not None:
        include_extensions = preset.options.include_extensions
        effective_unsupported_mode: UnsupportedMode = preset.options.unsupported_mode
        ignore = preset.ignore
    else:
        default_options = PresetOptions()
        include_extensions = default_options.include_extensions
        effective_unsupported_mode = default_options.unsupported_mode
        ignore = [".git", ".DS_Store", "node_modules"]
    if include_extension:
        include_extensions = _normalize_extensions([*include_extensions, *include_extension])
    if ignore_glob:
        ignore = [*ignore, *ignore_glob]
    if unsupported_mode:
        effective_unsupported_mode = cast(UnsupportedMode, unsupported_mode)
    eff_preset_name = _state_name(preset_name, source, destination)

    # Show plan
    prior_state = load_state(eff_preset_name)
    console.print(
        Panel.fit(
            f"[bold]Source:[/bold] {source}\n"
            f"[bold]Destination object:[/bold] {destination.object_id}\n"
            f"[bold]Destination space:[/bold] {destination.space_id}\n"
            f"[bold]Preset:[/bold] {eff_preset_name}\n"
            f"[bold]Unsupported files:[/bold] {effective_unsupported_mode}\n"
            f"[bold]Prune:[/bold] {prune}    [bold]Dry run:[/bold] {dry_run}",
            title="About to sync",
        )
    )
    if not dry_run and not assume_yes and not Confirm.ask("Proceed?", default=True):
        console.print("Cancelled.")
        return

    if dry_run:
        adapter: SyncAdapter = _DryRunAdapter()
    else:
        adapter = _get_anytype_adapter()
        if adapter is None:
            return
        if not skip_destination_check and not _validate_destination_collection(
            adapter, destination
        ):
            return

    result = run_sync(
        preset_name=eff_preset_name,
        source=source,
        destination=destination,
        include_extensions=include_extensions,
        ignore=ignore,
        adapter=adapter,
        prior_state=prior_state,
        dry_run=dry_run,
        prune=prune,
        unsupported_mode=effective_unsupported_mode,
    )

    if not dry_run and result.state is not None:
        save_state(result.state)

    _print_summary(result, dry_run)
    if result.errors:
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# `jarvis sync preset ...`
# ---------------------------------------------------------------------------


@sync_group.group(name="preset")
def preset_group() -> None:
    """Manage saved sync presets."""


@preset_group.command(name="add")
def preset_add() -> None:
    """Interactively define a new preset."""
    name = Prompt.ask("Preset name (slug-safe; no spaces, slashes, colons)").strip()
    if not name:
        console.print("[red]Empty name.[/red]")
        raise SystemExit(1)

    registry = load_registry()
    if registry.get(name) is not None:
        if not Confirm.ask(f"Preset '{name}' already exists. Overwrite?", default=False):
            return

    source: Path | None = None
    if Confirm.ask("Pre-fill a source path? (No = ask each time)", default=False):
        path_str = Prompt.ask("Source path").strip()
        candidate = Path(path_str).expanduser()
        if not candidate.exists():
            console.print(f"[yellow]Warning: {candidate} does not exist yet.[/yellow]")
        source = candidate

    destination: str | None = None
    if Confirm.ask("Pre-fill a destination link? (No = ask each time)", default=False):
        link_str = Prompt.ask("Anytype object link").strip()
        try:
            parse_link(link_str)
        except InvalidLinkError as e:
            console.print(f"[red]Invalid link: {e}[/red]")
            raise SystemExit(1) from e
        destination = link_str

    ignore_default = [".git", ".DS_Store", "node_modules"]
    ignore = ignore_default
    if Confirm.ask(f"Use default ignore globs? [{', '.join(ignore_default)}]", default=True):
        pass
    else:
        raw = Prompt.ask("Ignore globs (comma-separated)", default=", ".join(ignore_default))
        ignore = [g.strip() for g in raw.split(",") if g.strip()]

    options = PresetOptions()
    if not Confirm.ask(
        f"Use default included extensions? [{', '.join(options.include_extensions)}]",
        default=True,
    ):
        raw = Prompt.ask(
            "Included file extensions (comma-separated)",
            default=", ".join(options.include_extensions),
        )
        options = PresetOptions(
            include_extensions=_normalize_extensions(raw.split(",")),
            unsupported_mode=options.unsupported_mode,
        )
    unsupported_raw = Prompt.ask(
        "Unsupported file handling",
        choices=["upload", "warn", "stub", "error"],
        default=options.unsupported_mode,
    )
    options = PresetOptions(
        include_extensions=options.include_extensions,
        unsupported_mode=cast(UnsupportedMode, unsupported_raw),
    )

    try:
        preset = Preset(
            name=name,
            source=source,
            destination=destination,
            ignore=ignore,
            options=options,
        )
    except ValueError as e:
        console.print(f"[red]Invalid preset: {e}[/red]")
        raise SystemExit(1) from e

    registry.upsert(preset)
    save_registry(registry)
    console.print(f"[green]✓ Saved preset '{name}'.[/green]")


@preset_group.command(name="list")
def preset_list() -> None:
    """List all saved presets."""
    registry = load_registry()
    if not registry.presets:
        console.print("No presets yet. Run [bold]jarvis sync preset add[/bold] to create one.")
        return

    table = Table(title="Sync presets")
    table.add_column("Name")
    table.add_column("Source")
    table.add_column("Destination")
    table.add_column("Ignore")
    for p in registry.presets:
        table.add_row(
            p.name,
            str(p.source) if p.source else "[dim]ask at run time[/dim]",
            p.destination or "[dim]ask at run time[/dim]",
            ", ".join(p.ignore) if p.ignore else "—",
        )
    console.print(table)


@preset_group.command(name="show")
@click.argument("name")
def preset_show(name: str) -> None:
    """Show one preset's full config."""
    registry = load_registry()
    p = registry.get(name)
    if p is None:
        console.print(f"[red]No preset named '{name}'.[/red]")
        raise SystemExit(1)
    console.print(Panel(p.model_dump_json(indent=2), title=f"Preset: {name}"))


@preset_group.command(name="edit")
@click.argument("name")
def preset_edit(name: str) -> None:
    """Edit an existing preset interactively."""
    registry = load_registry()
    existing = registry.get(name)
    if existing is None:
        console.print(f"[red]No preset named '{name}'.[/red]")
        raise SystemExit(1)

    new_source_str = Prompt.ask(
        "Source path",
        default=str(existing.source) if existing.source else "",
    ).strip()
    new_source = Path(new_source_str).expanduser() if new_source_str else None

    new_dest_raw = Prompt.ask(
        "Destination link",
        default=existing.destination or "",
    ).strip()
    new_dest: str | None
    if new_dest_raw:
        try:
            parse_link(new_dest_raw)
        except InvalidLinkError as e:
            console.print(f"[red]Invalid link: {e}[/red]")
            raise SystemExit(1) from e
        new_dest = new_dest_raw
    else:
        new_dest = None

    new_ignore_str = Prompt.ask(
        "Ignore globs (comma-separated)",
        default=", ".join(existing.ignore),
    ).strip()
    new_ignore = [g.strip() for g in new_ignore_str.split(",") if g.strip()]
    new_extensions_str = Prompt.ask(
        "Included file extensions (comma-separated)",
        default=", ".join(existing.options.include_extensions),
    ).strip()
    new_options = PresetOptions(
        include_extensions=_normalize_extensions(new_extensions_str.split(",")),
        unsupported_mode=existing.options.unsupported_mode,
    )
    new_unsupported_mode = Prompt.ask(
        "Unsupported file handling",
        choices=["upload", "warn", "stub", "error"],
        default=existing.options.unsupported_mode,
    ).strip()
    new_options = PresetOptions(
        include_extensions=new_options.include_extensions,
        unsupported_mode=cast(UnsupportedMode, new_unsupported_mode),
    )

    updated = Preset(
        name=name,
        source=new_source,
        destination=new_dest,
        ignore=new_ignore,
        options=new_options,
    )
    registry.upsert(updated)
    save_registry(registry)
    console.print(f"[green]✓ Updated preset '{name}'.[/green]")


@preset_group.command(name="delete")
@click.argument("name")
def preset_delete(name: str) -> None:
    """Delete a preset (with confirmation)."""
    registry = load_registry()
    if registry.get(name) is None:
        console.print(f"[red]No preset named '{name}'.[/red]")
        raise SystemExit(1)
    if not Confirm.ask(f"Delete preset '{name}'?", default=False):
        return
    registry.remove(name)
    save_registry(registry)
    console.print(f"[green]✓ Deleted preset '{name}'.[/green]")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_source(cli_source: str | None, preset: Preset | None) -> Path | None:
    if cli_source:
        p = Path(cli_source).expanduser().resolve()
        if not p.exists():
            console.print(f"[red]Path does not exist: {p}[/red]")
            return None
        return p
    if preset is not None and preset.source is not None:
        return preset.source.expanduser().resolve()
    raw = Prompt.ask("Source path (file or directory)").strip()
    if not raw:
        console.print("[red]No source provided.[/red]")
        return None
    p = Path(raw).expanduser().resolve()
    if not p.exists():
        console.print(f"[red]Path does not exist: {p}[/red]")
        return None
    return p


def _normalize_extensions(values: tuple[str, ...] | list[str]) -> list[str]:
    """Return cleaned extensions with leading dots and no empty entries."""
    out: list[str] = []
    for value in values:
        ext = value.strip()
        if not ext:
            continue
        if not ext.startswith("."):
            ext = f".{ext}"
        if ext not in out:
            out.append(ext)
    return out


def _state_name(preset_name: str | None, source: Path, destination: AnytypeLink) -> str:
    """Return the state bucket for a sync run.

    Presets keep their explicit name. Ad-hoc runs get a deterministic source +
    destination key so different one-off syncs do not overwrite each other's
    incremental state.
    """
    if preset_name:
        return preset_name
    raw = f"{source.resolve()}|{destination.space_id}|{destination.object_id}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"_adhoc_{digest}"


def _resolve_destination(cli_destination: str | None, preset: Preset | None) -> AnytypeLink | None:
    if cli_destination:
        try:
            return parse_link(cli_destination)
        except InvalidLinkError as e:
            console.print(f"[red]Invalid destination link: {e}[/red]")
            return None
    if preset is not None and preset.destination is not None:
        return preset.resolved_destination()

    # Prompt: pick Space first, then ask for the object link, verify the link's space matches.
    selected_space_id = _pick_space()
    if selected_space_id is None:
        return None
    raw = Prompt.ask("Paste the Anytype object link for the target folder/collection").strip()
    try:
        link = parse_link(raw)
    except InvalidLinkError as e:
        console.print(f"[red]Invalid link: {e}[/red]")
        return None
    if link.space_id != selected_space_id:
        if not Confirm.ask(
            "That link is in a different Space than the one you just picked. Continue anyway?",
            default=False,
        ):
            return None
    return link


def _pick_space() -> str | None:
    """Use the existing AnyTypeClient.get_spaces helper to let the operator pick a Space."""
    from jarvis.anytype_client import AnyTypeClient

    try:
        client = AnyTypeClient()
        client.connect()
        spaces = client.get_spaces()
    except Exception as e:
        console.print(f"[red]Could not connect to Anytype: {e}[/red]")
        return None

    if not spaces:
        console.print("[red]No Spaces found in Anytype.[/red]")
        return None

    console.print("\n[bold]Available Spaces:[/bold]")
    for i, (sid, sname) in enumerate(spaces, start=1):
        console.print(f"  {i}. {sname}  [dim]({sid})[/dim]")
    choice = Prompt.ask(
        "Pick a Space (number)",
        choices=[str(i) for i in range(1, len(spaces) + 1)],
        default="1",
    )
    return spaces[int(choice) - 1][0]


def _get_anytype_adapter() -> SyncAdapter | None:
    """Get a connected AnyTypeAdapter from the registry.

    The adapter satisfies the SyncAdapter Protocol structurally — no inheritance
    needed. Returns None if connection fails (the caller prints a message and
    exits).
    """
    from jarvis.adapters import get_adapter

    try:
        adapter = get_adapter("anytype")
        adapter.connect()
        return adapter  # type: ignore[return-value]
    except Exception as e:
        console.print(f"[red]Could not connect to Anytype: {e}[/red]")
        return None


def _validate_destination_collection(adapter: SyncAdapter, destination: AnytypeLink) -> bool:
    """Verify real syncs only target a Collection/list-like Anytype object."""
    validator = getattr(adapter, "validate_collection", None)
    if validator is None:
        return True
    try:
        validator(destination.space_id, destination.object_id)
        return True
    except Exception as e:
        console.print(f"[red]Invalid sync destination: {e}[/red]")
        console.print(
            "[dim]Pass an Anytype Collection link, or use --skip-destination-check "
            "if you know this object can accept children.[/dim]"
        )
        return False


class _DryRunAdapter:
    """Adapter guard for dry-runs; the engine should never call it."""

    def create_collection_in(
        self, space_id: str, parent_collection_id: str | None, name: str
    ) -> str:
        raise RuntimeError("dry-run attempted to create a collection")

    def create_page_in(
        self,
        space_id: str,
        parent_collection_id: str | None,
        name: str,
        body_markdown: str,
    ) -> str:
        raise RuntimeError("dry-run attempted to create a page")

    def update_page_content(self, space_id: str, object_id: str, body_markdown: str) -> None:
        raise RuntimeError("dry-run attempted to update a page")

    def upload_file_in(
        self, space_id: str, parent_collection_id: str | None, file_path: Path
    ) -> str:
        raise RuntimeError("dry-run attempted to upload a file")

    def delete_object(self, space_id: str, object_id: str) -> bool:
        raise RuntimeError("dry-run attempted to delete an object")

    def delete_file(self, space_id: str, file_id: str) -> bool:
        raise RuntimeError("dry-run attempted to delete a file")


def _print_summary(result: SyncResult, dry_run: bool) -> None:
    title = "Dry run summary" if dry_run else "Sync summary"
    console.print(
        Panel.fit(
            f"[bold]Created:[/bold] {result.created}\n"
            f"[bold]Updated:[/bold] {result.updated}\n"
            f"[bold]Unchanged:[/bold] {result.unchanged}\n"
            f"[bold]Skipped:[/bold] {result.skipped}\n"
            f"[bold]Stubbed:[/bold] {result.stubbed}\n"
            f"[bold]Pruned:[/bold] {result.pruned}\n"
            f"[bold]Warnings:[/bold] {len(result.warnings)}\n"
            f"[bold]Errors:[/bold] {len(result.errors)}",
            title=title,
        )
    )
    if result.warnings:
        console.print("\n[yellow bold]Warnings:[/yellow bold]")
        for warning in result.warnings[:25]:
            console.print(f"  • {warning}")
        if len(result.warnings) > 25:
            console.print(f"  [dim]… {len(result.warnings) - 25} more[/dim]")
    if result.errors:
        console.print("\n[red bold]Errors:[/red bold]")
        for err in result.errors:
            console.print(f"  • {err}")
    if dry_run:
        console.print("\n[dim]No changes were made. Re-run without --dry-run to apply.[/dim]")
    elif result.state is not None:
        console.print(
            f"\n[dim]State written to ~/.jarvis/sync/state/{result.state.preset}.json[/dim]"
        )


# Helper used by tests — not exported for end users.
def _operations_summary(ops: list[SyncOperation]) -> dict[str, int]:
    out: dict[str, int] = {}
    for op in ops:
        out[op.kind] = out.get(op.kind, 0) + 1
    return out
