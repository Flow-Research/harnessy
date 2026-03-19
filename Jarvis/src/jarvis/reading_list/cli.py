"""CLI for reading list organization."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from jarvis.adapters import get_adapter

from .cache import ResultCache, clear_cache
from .fetcher import fetch_all
from .models import (
    FetchedContent,
    PrioritizationResult,
    PrioritizedItem,
    ReadingItem,
    SourceDocument,
    SourceType,
    Tier,
    timestamp_now,
)
from .parser import extract_reading_items
from .prioritizer import prioritize_items
from .source_loader import SourceResolutionError, load_source_document

console = Console()


def _filter_items(
    items: list[PrioritizedItem],
    tier: str | None,
    topic: str | None,
) -> list[PrioritizedItem]:
    filtered = items
    if tier:
        filtered = [item for item in filtered if item.tier == tier]
    if topic:
        filtered = [item for item in filtered if item.topic.value == topic]
    return filtered


def _render_items_table(
    source: SourceDocument,
    items: list[PrioritizedItem],
    fetch_summary: str,
) -> None:
    console.print()
    console.print(
        Panel(
            (
                f"[bold]{source.title}[/bold]\n"
                f"[dim]{source.source_type.value}: {source.source_ref}[/dim]\n"
                f"{fetch_summary}"
            ),
            title="Reading List — Prioritized",
            border_style="cyan",
        )
    )
    grouped: dict[Tier, list[PrioritizedItem]] = defaultdict(list)
    for item in items:
        grouped[item.tier].append(item)
    for tier_name in ["read_now", "this_week", "this_month", "reference", "deferred"]:
        tier_items = grouped.get(tier_name, [])
        if not tier_items:
            continue
        console.print()
        console.print(f"[bold]{tier_name.replace('_', ' ').title()} ({len(tier_items)})[/bold]")
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("#", style="cyan", width=4)
        table.add_column("Title", overflow="fold")
        table.add_column("Topic", style="green", width=22)
        table.add_column("Rationale", overflow="fold")
        for item in sorted(tier_items, key=lambda current: current.rank):
            title = item.content.fetched_title or item.content.item.title or item.content.item.url
            table.add_row(str(item.rank), title[:120], item.topic.value, item.rationale)
        console.print(table)


def _render_extracted_list(source: SourceDocument, items: list[ReadingItem]) -> None:
    console.print()
    console.print(
        Panel(
            (
                f"[bold]{source.title}[/bold]\n"
                f"[dim]{len(items)} links extracted from {source.source_type.value}[/dim]"
            ),
            title="Reading List — Extracted Items",
            border_style="cyan",
        )
    )
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("#", style="cyan", width=4)
    table.add_column("Section", style="yellow", width=20)
    table.add_column("Type", style="green", width=12)
    table.add_column("Title / Description", overflow="fold")
    table.add_column("URL", overflow="fold")
    for index, item in enumerate(items, start=1):
        title = item.title or item.description or "Untitled"
        table.add_row(str(index), item.section or "-", item.item_type.value, title[:120], item.url)
    console.print(table)


def _readable_title(item: PrioritizedItem) -> str:
    """Extract the best readable title for an item."""
    title = item.content.fetched_title or item.content.item.title
    if title and not title.startswith("http"):
        return title[:120]
    # Fall back to cleaning the URL into something readable
    from urllib.parse import urlparse

    parsed = urlparse(item.content.item.url)
    path = parsed.path.strip("/").rsplit("/", 1)[-1] if parsed.path.strip("/") else ""
    if path:
        return f"{parsed.hostname}: {path.replace('-', ' ').replace('_', ' ')}"
    return parsed.hostname or item.content.item.url[:80]


def _type_badge(item: PrioritizedItem) -> str:
    """Return a short type label from the item type."""
    badge_map = {
        "paper": "Paper",
        "tweet": "Tweet",
        "repo": "Repo",
        "article": "Article",
        "pdf": "PDF",
        "video": "Video",
    }
    return badge_map.get(item.content.item.item_type.value, "")


def _result_to_markdown(result: PrioritizationResult) -> str:
    by_tier: dict[Tier, list[PrioritizedItem]] = defaultdict(list)
    for item in result.items:
        by_tier[item.tier].append(item)
    lines = [
        f"# Reading List Prioritized — {result.source.title}",
        "",
        f"Source: {result.source.source_ref}",
        f"Generated: {result.generated_at}",
        "",
    ]
    for tier_name in ["read_now", "this_week", "this_month", "reference", "deferred"]:
        tier_items = by_tier.get(tier_name, [])
        if not tier_items:
            continue
        lines.extend([f"## {tier_name.replace('_', ' ').title()}", ""])
        # Group by topic within the tier
        by_topic: dict[str, list[PrioritizedItem]] = defaultdict(list)
        for item in sorted(tier_items, key=lambda current: current.rank):
            by_topic[item.topic.value].append(item)
        for topic_key, topic_items in by_topic.items():
            topic_label = topic_key.replace("_", " ").title()
            lines.append(f"### {topic_label}")
            lines.append("")
            # Deduplicate shared rationales
            rationales = {item.rationale for item in topic_items}
            shared_rationale = rationales.pop() if len(rationales) == 1 else None
            if shared_rationale:
                lines.append(f"> {shared_rationale}")
                lines.append("")
            for item in topic_items:
                title = _readable_title(item)
                badge = _type_badge(item)
                badge_str = f" [{badge}]" if badge else ""
                rationale_str = f" — {item.rationale}" if not shared_rationale else ""
                lines.append(
                    f"- **{title}**{badge_str}{rationale_str} "
                    f"| [Link]({item.content.item.url})"
                )
            lines.append("")
    return "\n".join(lines)


def _save_to_journal(result: PrioritizationResult, backend: str | None) -> None:
    adapter = get_adapter(backend)
    adapter.connect()
    space_id = adapter.get_default_space()
    title = f"Reading List Prioritized — {result.source.title}"
    content = _result_to_markdown(result)
    adapter.create_journal_entry(space_id=space_id, content=content, title=title)


def _write_back_to_source(result: PrioritizationResult, backend: str | None) -> None:
    """Write the prioritized result back to the source object."""
    source = result.source
    if not source.supports_write_back:
        console.print(
            "[yellow]Write-back skipped: source is not a writable backend object "
            f"(type={source.source_type.value}).[/yellow]"
        )
        return
    backend_name = backend or source.source_type.value
    adapter = get_adapter(backend_name)
    adapter.connect()
    markdown = _result_to_markdown(result)
    adapter.update_object(
        space_id=source.space_id,
        object_id=source.object_id,
        updates={"body": markdown},
    )
    console.print(
        f"[green]Updated source object '{source.title}' "
        f"({source.object_id}) with prioritized reading list.[/green]"
    )


def _build_result(
    source: SourceDocument,
    prioritized: list[PrioritizedItem],
    fetched: list[FetchedContent],
) -> PrioritizationResult:
    return PrioritizationResult(
        source=source,
        items=prioritized,
        fetch_successes=sum(1 for item in fetched if item.fetch_status == "success"),
        fetch_failures=sum(1 for item in fetched if item.fetch_status != "success"),
        generated_at=timestamp_now(),
    )


def _run_organize(
    target: str,
    resolver: str | None,
    backend: str | None,
    output: str | None,
    output_format: str,
    tier_filter: str | None,
    topic_filter: str | None,
    journal: bool,
    no_fetch: bool,
    no_cache: bool,
    write_back: bool = False,
) -> None:
    source = load_source_document(target, resolver=resolver, backend=backend)
    result_cache = ResultCache()
    mode_suffix = "metadata-only" if no_fetch else "deep-fetch"
    cache_key = f"{source.fingerprint}:{mode_suffix}"
    if not no_cache:
        cached = result_cache.get(cache_key)
        if cached is not None:
            filtered = _filter_items(cached.items, tier_filter, topic_filter)
            if output_format == "json":
                click.echo(cached.model_dump_json(indent=2))
            elif output_format == "markdown":
                markdown = _result_to_markdown(cached)
                click.echo(markdown)
                if output:
                    Path(output).write_text(markdown)
            else:
                _render_items_table(
                    cached.source,
                    filtered,
                    (
                        "[dim]Cached result · "
                        f"fetch successes: {cached.fetch_successes}, "
                        f"failures: {cached.fetch_failures}[/dim]"
                    ),
                )
                if output:
                    Path(output).write_text(_result_to_markdown(cached))
            if journal:
                _save_to_journal(cached, backend)
            if write_back:
                _write_back_to_source(cached, backend)
            return

    items = extract_reading_items(source.markdown)
    if not items:
        raise RuntimeError("No reading items found in source")
    fetched = [
        FetchedContent(
            item=item,
            fetched_title=item.title,
            fetched_text=item.description,
            authors=[],
            fetch_status="failed",
            fetched_at=timestamp_now(),
        )
        for item in items
    ]
    if not no_fetch:
        import asyncio

        fetched = asyncio.run(fetch_all(items, no_cache=no_cache))
    prioritized = prioritize_items(fetched)
    result = _build_result(source, prioritized, fetched)
    result_cache.set(cache_key, result)
    filtered = _filter_items(result.items, tier_filter, topic_filter)
    if output_format == "json":
        click.echo(result.model_dump_json(indent=2))
    elif output_format == "markdown":
        markdown = _result_to_markdown(result)
        click.echo(markdown)
        if output:
            Path(output).write_text(markdown)
    else:
        _render_items_table(
            result.source,
            filtered,
            (
                f"[dim]Fetch successes: {result.fetch_successes}, "
                f"failures: {result.fetch_failures}[/dim]"
            ),
        )
        if output:
            Path(output).write_text(_result_to_markdown(result))
    if journal:
        _save_to_journal(result, backend)
    if write_back:
        _write_back_to_source(result, backend)


@click.group(name="reading-list")
def reading_list_cli() -> None:
    """Organize and prioritize reading lists against current project context."""


@reading_list_cli.command(name="list")
@click.argument("target")
@click.option(
    "--resolver",
    type=click.Choice([member.value for member in SourceType]),
    default=None,
)
@click.option("--backend", default=None, help="Backend override for object-based resolvers")
def list_command(target: str, resolver: str | None, backend: str | None) -> None:
    """Extract and display links from a reading list source."""
    try:
        source = load_source_document(target, resolver=resolver, backend=backend)
        items = extract_reading_items(source.markdown)
        _render_extracted_list(source, items)
    except SourceResolutionError as exc:
        console.print(f"[red]Source error: {exc}[/red]")
        raise SystemExit(1)
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise SystemExit(1)


@reading_list_cli.command(name="organize")
@click.argument("target")
@click.option(
    "--resolver",
    type=click.Choice([member.value for member in SourceType]),
    default=None,
)
@click.option("--backend", default=None, help="Backend override for object-based resolvers")
@click.option("--output", type=click.Path(), default=None, help="Save markdown output to file")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json", "markdown"]),
    default="table",
)
@click.option(
    "--tier",
    "tier_filter",
    type=click.Choice(["read_now", "this_week", "this_month", "reference", "deferred"]),
    default=None,
)
@click.option("--topic", "topic_filter", default=None)
@click.option("--journal", is_flag=True, help="Save prioritized output to journal")
@click.option(
    "--no-fetch",
    is_flag=True,
    help="Skip deep URL fetching and prioritize from metadata only",
)
@click.option("--no-cache", is_flag=True, help="Ignore cached content and results")
@click.option(
    "--write-back",
    is_flag=True,
    help="Write prioritized result back to the source object (AnyType/Notion only)",
)
def organize_command(
    target: str,
    resolver: str | None,
    backend: str | None,
    output: str | None,
    output_format: str,
    tier_filter: str | None,
    topic_filter: str | None,
    journal: bool,
    no_fetch: bool,
    no_cache: bool,
    write_back: bool,
) -> None:
    """Deep research and prioritize a reading list."""
    try:
        _run_organize(
            target,
            resolver,
            backend,
            output,
            output_format,
            tier_filter,
            topic_filter,
            journal,
            no_fetch,
            no_cache,
            write_back,
        )
    except SourceResolutionError as exc:
        console.print(f"[red]Source error: {exc}[/red]")
        raise SystemExit(1)
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise SystemExit(1)


@reading_list_cli.command(name="extract")
@click.argument("target")
@click.option(
    "--resolver",
    type=click.Choice([member.value for member in SourceType]),
    default=None,
)
@click.option("--backend", default=None, help="Backend override for object-based resolvers")
def extract_command(target: str, resolver: str | None, backend: str | None) -> None:
    """Extract raw reading items as JSON for agent consumption.

    Returns source metadata and unscored items — no AI prioritization.
    Designed for agent orchestration: the agent scores items using its own
    context and reasoning, then writes back via `reading-list write-back`.
    """
    try:
        source = load_source_document(target, resolver=resolver, backend=backend)
        items = extract_reading_items(source.markdown)
        import json as _json

        payload = {
            "source": {
                "title": source.title,
                "source_type": source.source_type.value,
                "source_ref": source.source_ref,
                "object_id": source.object_id,
                "space_id": source.space_id,
                "supports_write_back": source.supports_write_back,
            },
            "items": [
                {
                    "url": item.url,
                    "title": item.title,
                    "description": item.description,
                    "section": item.section,
                    "domain": item.domain,
                    "item_type": item.item_type.value,
                }
                for item in items
            ],
            "count": len(items),
        }
        click.echo(_json.dumps(payload, indent=2))
    except SourceResolutionError as exc:
        console.print(f"[red]Source error: {exc}[/red]")
        raise SystemExit(1)
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise SystemExit(1)


@reading_list_cli.command(name="write-back")
@click.argument("target")
@click.option(
    "--resolver",
    type=click.Choice([member.value for member in SourceType]),
    default=None,
)
@click.option("--backend", default=None, help="Backend override for object-based resolvers")
@click.option(
    "--file",
    "input_file",
    type=click.Path(exists=True),
    default=None,
    help="Read markdown from a file",
)
@click.option("--stdin", "use_stdin", is_flag=True, help="Read markdown from stdin")
def write_back_command(
    target: str,
    resolver: str | None,
    backend: str | None,
    input_file: str | None,
    use_stdin: bool,
) -> None:
    """Write agent-formatted markdown back to a reading list source.

    Accepts markdown from --file or --stdin and writes it to the target
    object (AnyType/Notion). Use after the agent has scored and formatted
    items independently.
    """
    if not input_file and not use_stdin:
        console.print("[red]Error: provide --file or --stdin[/red]")
        raise SystemExit(1)
    try:
        source = load_source_document(target, resolver=resolver, backend=backend)
        if not source.supports_write_back:
            console.print(
                "[yellow]Write-back not supported: source is not a writable backend object "
                f"(type={source.source_type.value}).[/yellow]"
            )
            raise SystemExit(1)
        if input_file:
            markdown = Path(input_file).read_text()
        else:
            import sys

            markdown = sys.stdin.read()
        if not markdown.strip():
            console.print("[red]Error: empty markdown input[/red]")
            raise SystemExit(1)
        backend_name = backend or source.source_type.value
        adapter = get_adapter(backend_name)
        adapter.connect()
        adapter.update_object(
            space_id=source.space_id,
            object_id=source.object_id,
            updates={"body": markdown},
        )
        console.print(
            f"[green]Updated '{source.title}' ({source.object_id}) with provided markdown.[/green]"
        )
    except SourceResolutionError as exc:
        console.print(f"[red]Source error: {exc}[/red]")
        raise SystemExit(1)
    except SystemExit:
        raise
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise SystemExit(1)


@reading_list_cli.command(name="cache-clear")
def cache_clear_command() -> None:
    """Clear reading list caches."""
    removed = clear_cache()
    console.print(f"[green]Removed {removed} cached file(s).[/green]")


@click.command(name="rl")
@click.argument("target")
@click.option(
    "--resolver",
    type=click.Choice([member.value for member in SourceType]),
    default=None,
)
@click.option("--backend", default=None)
@click.option("--output", type=click.Path(), default=None)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json", "markdown"]),
    default="table",
)
@click.option(
    "--tier",
    "tier_filter",
    type=click.Choice(["read_now", "this_week", "this_month", "reference", "deferred"]),
    default=None,
)
@click.option("--topic", "topic_filter", default=None)
@click.option("--journal", is_flag=True)
@click.option("--no-fetch", is_flag=True)
@click.option("--no-cache", is_flag=True)
@click.option("--write-back", is_flag=True)
def quick_reading_list(
    target: str,
    resolver: str | None,
    backend: str | None,
    output: str | None,
    output_format: str,
    tier_filter: str | None,
    topic_filter: str | None,
    journal: bool,
    no_fetch: bool,
    no_cache: bool,
    write_back: bool,
) -> None:
    """Quick alias for reading-list organize."""
    try:
        _run_organize(
            target,
            resolver,
            backend,
            output,
            output_format,
            tier_filter,
            topic_filter,
            journal,
            no_fetch,
            no_cache,
            write_back,
        )
    except SourceResolutionError as exc:
        console.print(f"[red]Source error: {exc}[/red]")
        raise SystemExit(1)
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise SystemExit(1)
