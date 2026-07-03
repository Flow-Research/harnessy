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
import re
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from jarvis.anytype_client import AnyTypeClient
from jarvis.config import get_config

if TYPE_CHECKING:
    from jarvis.sync.object_link import AnytypeLink
    from jarvis.sync.state import SyncState

console = Console()


def _git_root() -> Path | None:
    """Return the current git repository root, or None when not in a git tree."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
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
        console.print(f"[red]Configured content root not found: {cfg.content.root_path}[/red]")
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


@content_cli.command(name="package")
@click.argument("path")
@click.option(
    "--output",
    default="journal.md",
    show_default=True,
    help="Output filename inside the content piece folder.",
)
def package(path: str, output: str) -> None:
    """Build a journal-ready package file for a content piece."""
    content_root = resolve_content_root()
    piece_dir = _resolve_piece_dir(path, content_root)
    output_path = package_piece(piece_dir, content_root, output_name=output)
    console.print(f"[green]Wrote {output_path}[/green]")


@content_cli.command(name="verify")
@click.argument("path")
@click.option(
    "--require-file",
    "required_files",
    multiple=True,
    default=("index.md",),
    help="File that must exist in the piece folder. Repeatable.",
)
@click.option(
    "--require",
    "required_text",
    multiple=True,
    help="Text that must appear somewhere in the content package. Repeatable.",
)
@click.option(
    "--forbid",
    "forbidden_text",
    multiple=True,
    help="Text that must not appear anywhere in the content package. Repeatable.",
)
@click.option(
    "--hygiene/--no-hygiene",
    default=True,
    help="Check configured AI-speak patterns as part of verification.",
)
@click.option(
    "--hygiene-config",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Text hygiene pattern registry YAML.",
)
def verify(
    path: str,
    required_files: tuple[str, ...],
    required_text: tuple[str, ...],
    forbidden_text: tuple[str, ...],
    hygiene: bool,
    hygiene_config: Path | None,
) -> None:
    """Verify a content piece before publishing/syncing."""
    content_root = resolve_content_root()
    piece_dir = _resolve_piece_dir(path, content_root)
    errors = verify_piece(
        piece_dir,
        required_files=required_files,
        required_text=required_text,
        forbidden_text=forbidden_text,
        hygiene=hygiene,
        hygiene_config=hygiene_config,
    )
    if errors:
        console.print("[red]Content verification failed:[/red]")
        for error in errors:
            console.print(f"  • {escape(error)}")
        raise SystemExit(1)
    console.print("[green]Content verification passed.[/green]")


@content_cli.command(name="audit-anytype")
@click.argument("path")
@click.option("--sync-preset", default=None, help="Sync preset/state name to audit.")
@click.option(
    "--sync-source",
    default=None,
    type=click.Path(exists=False),
    help="Sync source root.",
)
@click.option("--sync-destination", default=None, help="Anytype destination object_id:space_id.")
def audit_anytype(
    path: str,
    sync_preset: str | None,
    sync_source: str | None,
    sync_destination: str | None,
) -> None:
    """Audit Anytype Collection links for duplicates for one content piece."""
    content_root = resolve_content_root()
    piece_dir = _resolve_piece_dir(path, content_root)
    state_info = _resolve_sync_state_for_piece(
        piece_dir=piece_dir,
        content_root=content_root,
        sync_preset=sync_preset,
        sync_source=sync_source,
        sync_destination=sync_destination,
    )
    if state_info is None:
        console.print(
            "[red]Could not find a sync state for this piece. Pass --sync-preset "
            "or both --sync-source and --sync-destination.[/red]"
        )
        raise SystemExit(1)

    state, destination, relpath, _source = state_info
    from jarvis.sync.cli import _build_dedupe_plan, _get_anytype_adapter, _print_dedupe_plan

    adapter = _get_anytype_adapter()
    if adapter is None:
        raise SystemExit(1)
    plan = _build_dedupe_plan(
        state=state,
        destination=destination,
        adapter=adapter,
        target_relpath=relpath,
    )
    _print_dedupe_plan(plan, dry_run=True)
    if plan.removals:
        raise SystemExit(1)


@content_cli.command(name="publish-draft")
@click.argument("path")
@click.option("--journal/--no-journal", default=False, help="Write journal.md to Anytype Journal.")
@click.option("--space", "journal_spaces", multiple=True, help="Journal space name or ID.")
@click.option("--sync/--no-sync", default=True, help="Run Anytype content sync after packaging.")
@click.option(
    "--dedupe/--no-dedupe",
    default=True,
    help="Remove duplicate Collection links after sync.",
)
@click.option("--sync-preset", default=None, help="Sync preset/state name to use.")
@click.option(
    "--sync-source",
    default=None,
    type=click.Path(exists=False),
    help="Sync source root.",
)
@click.option("--sync-destination", default=None, help="Anytype destination object_id:space_id.")
@click.option(
    "--require",
    "required_text",
    multiple=True,
    help="Text that must appear somewhere before publish. Repeatable.",
)
@click.option(
    "--forbid",
    "forbidden_text",
    multiple=True,
    help="Text that must not appear anywhere before publish. Repeatable.",
)
@click.option(
    "--hygiene/--no-hygiene",
    default=True,
    help="Clean configured AI-speak patterns before packaging and publishing.",
)
@click.option(
    "--hygiene-config",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Text hygiene pattern registry YAML.",
)
def publish_draft(
    path: str,
    journal: bool,
    journal_spaces: tuple[str, ...],
    sync: bool,
    dedupe: bool,
    sync_preset: str | None,
    sync_source: str | None,
    sync_destination: str | None,
    required_text: tuple[str, ...],
    forbidden_text: tuple[str, ...],
    hygiene: bool,
    hygiene_config: Path | None,
) -> None:
    """Package, verify, journal, sync, and dedupe a content draft."""
    content_root = resolve_content_root()
    piece_dir = _resolve_piece_dir(path, content_root)
    if hygiene:
        _clean_text_hygiene([piece_dir], hygiene_config)
    journal_path = package_piece(piece_dir, content_root)
    if hygiene:
        _clean_text_hygiene([journal_path], hygiene_config)
    errors = verify_piece(
        piece_dir,
        required_files=("index.md", "journal.md"),
        required_text=required_text,
        forbidden_text=forbidden_text,
        hygiene=hygiene,
        hygiene_config=hygiene_config,
    )
    if errors:
        console.print("[red]Content verification failed:[/red]")
        for error in errors:
            console.print(f"  • {escape(error)}")
        raise SystemExit(1)

    title = _piece_title(piece_dir)
    if journal:
        journal_args = [
            "journal",
            "write",
            "--file",
            str(journal_path),
            "--title",
            title,
            "--no-deep-dive",
        ]
        for space in journal_spaces:
            journal_args.extend(["--space", space])
        _run_jarvis_command(journal_args)

    if not sync:
        console.print("[green]Packaged and verified content draft.[/green]")
        return

    state_info = _resolve_sync_state_for_piece(
        piece_dir=piece_dir,
        content_root=content_root,
        sync_preset=sync_preset,
        sync_source=sync_source,
        sync_destination=sync_destination,
    )
    if state_info is None:
        if not sync_source or not sync_destination:
            console.print(
                "[red]Could not resolve sync target. Pass --sync-preset or "
                "both --sync-source and --sync-destination.[/red]"
            )
            raise SystemExit(1)
        from jarvis.sync.object_link import parse_link

        source = Path(sync_source).expanduser().resolve()
        destination = parse_link(sync_destination)
        try:
            relpath = piece_dir.relative_to(source).as_posix()
        except ValueError:
            console.print(f"[red]Content piece is not inside sync source: {source}[/red]")
            raise SystemExit(1) from None
    else:
        _state, destination, relpath, source = state_info

    if sync_preset:
        sync_args = ["sync", "run", "--preset", sync_preset, "--yes"]
    else:
        sync_args = [
            "sync",
            "run",
            "--source",
            str(source),
            "--destination",
            f"{destination.object_id}:{destination.space_id}",
            "--yes",
        ]
    _run_jarvis_command(sync_args)

    if dedupe:
        if sync_preset:
            dedupe_args = ["sync", "dedupe", "--preset", sync_preset, "--path", relpath, "--yes"]
        else:
            dedupe_args = [
                "sync",
                "dedupe",
                "--source",
                str(source),
                "--destination",
                f"{destination.object_id}:{destination.space_id}",
                "--path",
                relpath,
                "--yes",
            ]
        _run_jarvis_command(dedupe_args)

    console.print("[green]Published content draft workflow complete.[/green]")


@content_cli.command(name="list")
@click.option(
    "--status",
    "-s",
    type=click.Choice(["draft", "review", "approved", "published", "rejected"]),
)
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


def _resolve_piece_dir(path: str, content_root: Path) -> Path:
    """Resolve a content piece directory from an absolute, CWD-relative, or root-relative path."""
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        piece_dir = candidate
    elif candidate.exists():
        piece_dir = candidate.resolve()
    else:
        piece_dir = content_root / candidate
    if piece_dir.is_file():
        piece_dir = piece_dir.parent
    if not (piece_dir / "index.md").exists():
        console.print(f"[red]No index.md in {piece_dir}[/red]")
        raise SystemExit(1)
    return piece_dir.resolve()


def package_piece(piece_dir: Path, content_root: Path, *, output_name: str = "journal.md") -> Path:
    """Write a journal-ready package file for one content piece."""
    from jarvis.content.frontmatter import parse_frontmatter

    index_path = piece_dir / "index.md"
    fm, index_body = parse_frontmatter(index_path)
    title = str(fm.get("title") or piece_dir.name)
    try:
        relpath = piece_dir.relative_to(content_root).as_posix()
    except ValueError:
        relpath = piece_dir.as_posix()

    lines = [
        f"# {title}",
        "",
        f"- Content package: `{relpath}`",
        f"- Status: {fm.get('status', 'unknown')}",
        f"- Platform: {fm.get('platform', 'unknown')}",
        f"- Audience: {fm.get('audience', 'unknown')}",
        f"- Scheduled: {fm.get('scheduled', 'unscheduled')}",
        "",
        "## Main Draft",
        "",
        index_body.strip(),
        "",
    ]

    supporting_files = [
        path
        for path in sorted(piece_dir.glob("*.md"))
        if path.name not in {"index.md", output_name}
    ]
    if supporting_files:
        lines.extend(["## Supporting Files", ""])
        for file_path in supporting_files:
            _file_fm, body = parse_frontmatter(file_path)
            lines.extend([f"### {file_path.name}", "", body.strip(), ""])

    output_path = piece_dir / output_name
    output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return output_path


def verify_piece(
    piece_dir: Path,
    *,
    required_files: tuple[str, ...],
    required_text: tuple[str, ...] = (),
    forbidden_text: tuple[str, ...] = (),
    hygiene: bool = True,
    hygiene_config: Path | None = None,
) -> list[str]:
    """Return content package validation errors."""
    from jarvis.content.frontmatter import parse_frontmatter

    errors: list[str] = []
    for file_name in required_files:
        if not (piece_dir / file_name).exists():
            errors.append(f"missing required file: {file_name}")

    index_path = piece_dir / "index.md"
    if index_path.exists():
        fm, _body = parse_frontmatter(index_path)
        for key in ("title", "platform", "audience", "type", "voice", "status", "scheduled"):
            if not fm.get(key):
                errors.append(f"index.md frontmatter missing: {key}")

    combined = "\n\n".join(
        path.read_text(encoding="utf-8") for path in sorted(piece_dir.glob("*.md"))
    )
    for needle in required_text:
        if needle not in combined:
            errors.append(f"required text not found: {needle}")
    for needle in forbidden_text:
        if needle in combined:
            errors.append(f"forbidden text found: {needle}")
    if hygiene:
        errors.extend(_text_hygiene_errors(piece_dir, hygiene_config))
    return errors


def _text_hygiene_errors(piece_dir: Path, config_path: Path | None) -> list[str]:
    from jarvis.text_hygiene import check_paths

    try:
        result = check_paths([piece_dir], config_path=config_path)
    except (OSError, ValueError, re.error) as exc:
        return [f"text hygiene check failed: {exc}"]
    return [
        (
            f"AI-speak pattern found: {finding.path.name}:{finding.line} "
            f"[{finding.rule_id}] {finding.match}"
        )
        for finding in result.findings
    ]


def _clean_text_hygiene(paths: list[Path], config_path: Path | None) -> None:
    from jarvis.text_hygiene import clean_paths, format_report

    try:
        result = clean_paths(paths, config_path=config_path)
    except (OSError, ValueError, re.error) as exc:
        console.print(f"[red]Text hygiene cleanup failed: {exc}[/red]")
        raise SystemExit(1) from exc
    if result.findings:
        console.print(f"[yellow]{format_report(result)}[/yellow]")


def _piece_title(piece_dir: Path) -> str:
    from jarvis.content.frontmatter import parse_frontmatter

    fm, _body = parse_frontmatter(piece_dir / "index.md")
    return str(fm.get("title") or piece_dir.name)


def _run_jarvis_command(args: list[str]) -> None:
    """Run another Jarvis command using the current Python environment."""
    command = [sys.executable, "-m", "jarvis", *args]
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def _resolve_sync_state_for_piece(
    *,
    piece_dir: Path,
    content_root: Path,
    sync_preset: str | None,
    sync_source: str | None,
    sync_destination: str | None,
) -> tuple["SyncState", "AnytypeLink", str, Path] | None:
    """Resolve sync state, destination, relpath, and source for a content piece."""
    from jarvis.sync.cli import _state_name
    from jarvis.sync.object_link import parse_link
    from jarvis.sync.presets import load_registry
    from jarvis.sync.state import SyncState, get_state_dir, load_state

    state: SyncState | None = None
    source: Path | None = Path(sync_source).expanduser().resolve() if sync_source else None
    destination = parse_link(sync_destination) if sync_destination else None

    if sync_preset:
        preset = load_registry().get(sync_preset)
        if preset is not None and source is None and preset.source is not None:
            source = preset.source.expanduser().resolve()
        state = load_state(sync_preset)
    elif source is not None and destination is not None:
        state = load_state(_state_name(None, source, destination))
    else:
        matches: list[tuple[SyncState, str]] = []
        for state_path in sorted(get_state_dir().glob("*.json")):
            try:
                candidate = load_state(state_path.stem)
            except Exception:
                continue
            if candidate is None:
                continue
            relpath = _piece_relpath_from_state(piece_dir, content_root, source, candidate)
            if relpath is not None:
                matches.append((candidate, relpath))
        if len(matches) == 1:
            state, _relpath = matches[0]

    if state is None:
        return None
    if destination is None:
        destination = parse_link(f"{state.destination_object_id}:{state.space_id}")
    relpath = _piece_relpath_from_state(piece_dir, content_root, source, state)
    if relpath is None:
        return None
    if source is None:
        source = _infer_sync_source(piece_dir, content_root, relpath)
    return state, destination, relpath, source


def _piece_relpath_from_state(
    piece_dir: Path,
    content_root: Path,
    source: Path | None,
    state: "SyncState",
) -> str | None:
    candidates: list[str] = []
    if source is not None:
        try:
            candidates.append(piece_dir.relative_to(source).as_posix())
        except ValueError:
            pass
    try:
        root_rel = piece_dir.relative_to(content_root).as_posix()
        candidates.append(root_rel)
        if root_rel.startswith("drafts/"):
            candidates.append(root_rel.removeprefix("drafts/"))
    except ValueError:
        pass

    collection_paths = {
        relpath for relpath, record in state.objects.items() if record.kind == "collection"
    }
    for candidate in candidates:
        if candidate in collection_paths:
            return candidate
    suffix_matches = [
        relpath
        for relpath in collection_paths
        if relpath.endswith(f"/{piece_dir.name}") or relpath == piece_dir.name
    ]
    if len(suffix_matches) == 1:
        return suffix_matches[0]
    return None


def _infer_sync_source(piece_dir: Path, content_root: Path, relpath: str) -> Path:
    if (content_root / relpath).resolve() == piece_dir:
        return content_root
    drafts_root = content_root / "drafts"
    if (drafts_root / relpath).resolve() == piece_dir:
        return drafts_root
    return content_root
