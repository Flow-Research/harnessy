"""CLI commands for content management.

Provides the `jarvis content` command group with subcommands:
- list: List content pieces with status
- approve: Approve and push a piece to AnyType
- push: Push all approved pieces to AnyType
- migrate: Restructure flat files to folder model
- status: Show summary counts by status
- strategy: Push content strategy to AnyType

Workspace paths and AnyType space/collection names are configurable
via `~/.jarvis/config.yaml` (see ContentConfig) or JARVIS_* env vars.
"""

import getpass
import os
import subprocess
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from jarvis.anytype_client import AnyTypeClient
from jarvis.config import get_config

console = Console()


def _git_root() -> Path | None:
    """Return the current git repository root, or None when not in a git tree."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _candidate_roots(base: Path, user: str) -> list[Path]:
    """Candidate content roots to probe when no explicit path is configured."""
    private_dir = base / ".jarvis" / "context" / "private"
    candidates = [
        private_dir / user / "content",
        private_dir / user / "flow-content",  # backward-compat
    ]
    # Any sibling user folder with a content or flow-content dir.
    if private_dir.exists():
        for child in sorted(private_dir.iterdir()):
            if not child.is_dir():
                continue
            for leaf in ("content", "flow-content"):
                c = child / leaf
                if c not in candidates:
                    candidates.append(c)
    return candidates


def get_connected_client() -> AnyTypeClient:
    """Get a connected AnyType client."""
    try:
        client = AnyTypeClient()
        client.connect()
        return client
    except Exception as e:
        console.print(f"[red]Failed to connect to AnyType: {e}[/red]")
        raise SystemExit(1)


def get_target_space(client: AnyTypeClient) -> tuple[str, str]:
    """Find the configured AnyType space, or prompt for selection.

    Uses `content.anytype_space_name` from config (case-insensitive match).
    Falls back to the shared space-selection prompt if unset or not found.
    """
    target_name = get_config().content.anytype_space_name
    if target_name:
        target_lower = target_name.lower()
        for space_id, space_name in client.get_spaces():
            if space_name.lower() == target_lower:
                return space_id, space_name

    from jarvis.journal.cli import get_space_selection
    return get_space_selection(client)


def resolve_content_root() -> Path:
    """Find the content root directory.

    Resolution order:
    1. `content.root_path` from config (absolute or relative to CWD / git root)
    2. `.jarvis/context/private/<user>/content` under CWD or git root
    3. `.jarvis/context/private/<user>/flow-content` (backward-compat)
    4. Any sibling `private/<other-user>/content` or `flow-content` folder
    """
    cfg = get_config()
    user = os.environ.get("USER") or getpass.getuser()
    search_bases = [Path.cwd()]
    git_root = _git_root()
    if git_root is not None and git_root not in search_bases:
        search_bases.append(git_root)

    if cfg.content.root_path:
        configured = Path(cfg.content.root_path).expanduser()
        if configured.is_absolute():
            if configured.exists():
                return configured
        else:
            for base in search_bases:
                candidate = base / configured
                if candidate.exists():
                    return candidate
        console.print(
            f"[red]Configured content root not found: {cfg.content.root_path}[/red]"
        )
        raise SystemExit(1)

    for base in search_bases:
        for candidate in _candidate_roots(base, user):
            if candidate.exists():
                return candidate

    console.print(
        "[red]Content root not found. Set `content.root_path` in "
        "~/.jarvis/config.yaml or create "
        ".jarvis/context/private/<user>/content.[/red]"
    )
    raise SystemExit(1)


@click.group()
def content_cli() -> None:
    """Manage the content publishing pipeline."""


@content_cli.command(name="list")
@click.option("--status", "-s", type=click.Choice(["draft", "review", "approved", "published", "rejected"]))
def list_pieces(status: str | None) -> None:
    """List content pieces with status."""
    from jarvis.content.publisher import ContentPublisher

    content_root = resolve_content_root()
    # List doesn't need AnyType connection
    publisher = ContentPublisher.__new__(ContentPublisher)
    publisher.content_root = content_root

    pieces = publisher.list_pieces(status=status)
    if not pieces:
        console.print("[yellow]No content pieces found.[/yellow]")
        return

    table = Table(title="Content Pieces")
    table.add_column("Name", style="cyan")
    table.add_column("Title", style="white")
    table.add_column("Status", style="bold")
    table.add_column("Platform")
    table.add_column("Audience")
    table.add_column("Scheduled")
    table.add_column("AnyType", style="dim")

    for p in pieces:
        status_style = {
            "draft": "yellow",
            "review": "blue",
            "approved": "green",
            "published": "bold green",
            "rejected": "red",
        }.get(p["status"], "white")

        table.add_row(
            p["name"],
            p["title"][:40],
            f"[{status_style}]{p['status']}[/{status_style}]",
            p["platform"],
            p["audience"],
            str(p["scheduled"]),
            "yes" if p["anytype_id"] else "",
        )

    console.print(table)


@content_cli.command()
@click.argument("path", required=False)
@click.option("--all", "approve_all", is_flag=True, help="Approve all pieces in 'review' status")
def approve(path: str | None, approve_all: bool) -> None:
    """Approve content and push to AnyType.

    PATH is the piece folder (e.g., drafts/2026/Apr/02-flow-thesis-thread).
    Use --all to approve all pieces currently in 'review' status.
    """
    from jarvis.content.frontmatter import find_drafts
    from jarvis.content.publisher import ContentPublisher

    content_root = resolve_content_root()
    client = get_connected_client()
    space_id, space_name = get_target_space(client)
    console.print(f"[dim]Using space: {space_name}[/dim]")

    publisher = ContentPublisher(
        client,
        space_id,
        content_root,
        root_collection_name=get_config().content.anytype_root_collection,
    )

    if approve_all:
        pieces = find_drafts(content_root / "drafts", status="review")
        if not pieces:
            console.print("[yellow]No pieces in 'review' status.[/yellow]")
            return
        for piece_dir in pieces:
            publisher.approve_and_push(piece_dir)
        console.print(f"[green]Approved {len(pieces)} pieces.[/green]")
    elif path:
        piece_dir = Path(path)
        if not piece_dir.is_absolute():
            piece_dir = content_root / path
        if not (piece_dir / "index.md").exists():
            console.print(f"[red]No index.md in {piece_dir}[/red]")
            raise SystemExit(1)
        publisher.approve_and_push(piece_dir)
    else:
        console.print("[red]Provide a path or use --all[/red]")
        raise SystemExit(1)


@content_cli.command()
@click.option("--force", is_flag=True, help="Re-push even if already pushed")
def push(force: bool) -> None:
    """Push all approved pieces to AnyType."""
    from jarvis.content.publisher import ContentPublisher

    content_root = resolve_content_root()
    client = get_connected_client()
    space_id, space_name = get_target_space(client)
    console.print(f"[dim]Using space: {space_name}[/dim]")

    publisher = ContentPublisher(
        client,
        space_id,
        content_root,
        root_collection_name=get_config().content.anytype_root_collection,
    )
    results = publisher.push_pending(force=force)

    if results:
        console.print(f"[green]Pushed {len(results)} pieces to AnyType.[/green]")
    else:
        console.print("[yellow]Nothing to push.[/yellow]")


@content_cli.command()
def migrate() -> None:
    """Restructure flat content files to folder model.

    Converts dd-slug.md files to dd-slug/index.md + platform files.
    """
    from jarvis.content.migrate import migrate_flat_to_folders

    content_root = resolve_content_root()
    count = migrate_flat_to_folders(content_root / "drafts")
    console.print(f"[green]Migrated {count} files to folder structure.[/green]")


@content_cli.command()
def status() -> None:
    """Show content pipeline status summary."""
    from jarvis.content.publisher import ContentPublisher

    content_root = resolve_content_root()
    publisher = ContentPublisher.__new__(ContentPublisher)
    publisher.content_root = content_root

    summary = publisher.status_summary()
    if not summary:
        console.print("[yellow]No content pieces found.[/yellow]")
        return

    total = sum(summary.values())
    console.print(f"\n[bold]Content Pipeline Status[/bold] ({total} pieces)\n")
    for s, count in sorted(summary.items()):
        bar = "█" * count
        console.print(f"  {s:12s} {bar} {count}")
    console.print()


@content_cli.command()
def strategy() -> None:
    """Push the content strategy document to AnyType."""
    from jarvis.content.publisher import ContentPublisher

    content_root = resolve_content_root()
    client = get_connected_client()
    space_id, space_name = get_target_space(client)
    console.print(f"[dim]Using space: {space_name}[/dim]")

    publisher = ContentPublisher(
        client,
        space_id,
        content_root,
        root_collection_name=get_config().content.anytype_root_collection,
    )
    publisher.push_strategy()
