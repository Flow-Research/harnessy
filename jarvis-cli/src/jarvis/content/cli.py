"""CLI commands for content management.

Provides the `jarvis content` command group with subcommands:
- list: List content pieces with status
- approve: Approve and push a piece to AnyType
- push: Push all approved pieces to AnyType
- migrate: Restructure flat files to folder model
- status: Show summary counts by status
- strategy: Push content strategy to AnyType
"""

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from jarvis.anytype_client import AnyTypeClient

console = Console()

# Default content root relative to project
DEFAULT_CONTENT_ROOT = ".jarvis/context/private/julian/flow-content"


def get_connected_client() -> AnyTypeClient:
    """Get a connected AnyType client."""
    try:
        client = AnyTypeClient()
        client.connect()
        return client
    except Exception as e:
        console.print(f"[red]Failed to connect to AnyType: {e}[/red]")
        raise SystemExit(1)


def get_space_for_flow(client: AnyTypeClient) -> tuple[str, str]:
    """Find the Flow space in AnyType."""
    spaces = client.get_spaces()
    for space_id, space_name in spaces:
        if space_name.lower() == "flow":
            return space_id, space_name

    # Fall back to saved/first space
    from jarvis.journal.cli import get_space_selection
    return get_space_selection(client)


def resolve_content_root() -> Path:
    """Find the content root directory."""
    path = Path.cwd() / DEFAULT_CONTENT_ROOT
    if path.exists():
        return path
    # Try from git root
    import subprocess
    try:
        git_root = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        path = Path(git_root) / DEFAULT_CONTENT_ROOT
        if path.exists():
            return path
    except subprocess.CalledProcessError:
        pass
    console.print(f"[red]Content root not found: {DEFAULT_CONTENT_ROOT}[/red]")
    raise SystemExit(1)


@click.group()
def content_cli() -> None:
    """Manage Flow Network content pipeline."""


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
    space_id, space_name = get_space_for_flow(client)
    console.print(f"[dim]Using space: {space_name}[/dim]")

    publisher = ContentPublisher(client, space_id, content_root)

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
    space_id, space_name = get_space_for_flow(client)
    console.print(f"[dim]Using space: {space_name}[/dim]")

    publisher = ContentPublisher(client, space_id, content_root)
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
    space_id, space_name = get_space_for_flow(client)
    console.print(f"[dim]Using space: {space_name}[/dim]")

    publisher = ContentPublisher(client, space_id, content_root)
    publisher.push_strategy()
