"""CLI commands for jarvis wiki domain management.

Provides the `jarvis wiki` command group with subcommands:
- init: Create a new wiki domain
- ingest: Add a source to a domain's raw/ directory
- compile: Run the compilation pipeline on a domain
- status: Show domain status and article counts
- ask: Ask a question against the wiki (Q&A)
- search: Grep across wiki articles
- lint: Check quality issues and health scores
- enhance: Identify and suggest improvements for weak articles
- open: Open the wiki in Obsidian, Cursor, or VS Code
- export: Package the wiki as a zip or HTML
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click
from rich.console import Console
from rich.table import Table

if TYPE_CHECKING:
    from jarvis.wiki.models import WikiDomain

console = Console()


@click.group()
def wiki_cli() -> None:
    """Manage Jarvis wiki knowledge domains."""


# ── init ──────────────────────────────────────────────────────────────────────


@wiki_cli.command(name="init")
@click.argument("domain")
@click.option("--title", "-t", default=None, help="Human-readable title for the domain")
@click.option("--description", "-d", default="", help="Short description of the domain")
def init(domain: str, title: str | None, description: str) -> None:
    """Create a new wiki domain at ~/.jarvis/wikis/<DOMAIN>/.

    DOMAIN must be lowercase kebab-case (e.g. seas, crypto, ai-research).
    """
    from jarvis.wiki.config import get_domain_root, save_schema
    from jarvis.wiki.log import LogAppender
    from jarvis.wiki.models import LogEntry, LogEntryType, WikiDomain

    domain_root = get_domain_root(domain)
    if domain_root.exists():
        console.print(f"[red]Domain already exists: {domain_root}[/red]")
        raise SystemExit(1)

    resolved_title = title or domain.replace("-", " ").title()

    try:
        schema = WikiDomain(domain=domain, title=resolved_title, description=description)
    except Exception as exc:
        console.print(f"[red]Invalid domain: {exc}[/red]")
        raise SystemExit(1)

    # Write schema (also creates domain_root)
    save_schema(schema)

    # Create raw/ subdirectories
    for subdir in ("articles", "papers", "notes", "images", "web-clips", "repos"):
        (domain_root / "raw" / subdir).mkdir(parents=True, exist_ok=True)

    # Create wiki/ scaffold
    (domain_root / "wiki").mkdir(exist_ok=True)
    (domain_root / "wiki" / "index.md").write_text("", encoding="utf-8")
    (domain_root / "wiki" / "log.md").write_text("", encoding="utf-8")

    # Create outputs/ subdirectories
    for subdir in ("slides", "charts", "exports"):
        (domain_root / "outputs" / subdir).mkdir(parents=True, exist_ok=True)

    # Create .state/
    (domain_root / ".state").mkdir(exist_ok=True)

    # Write Obsidian vault config
    from jarvis.wiki.obsidian import setup_obsidian_vault

    setup_obsidian_vault(domain_root, schema)

    # Write the steering surface (program.md + seeds.md) from templates
    _write_templates(domain_root, domain, resolved_title)

    # Append INIT log entry
    LogAppender.append(
        domain_root,
        LogEntry(
            entry_type=LogEntryType.INIT,
            description=f"Initialized domain '{domain}' — {resolved_title}",
        ),
    )

    console.print(f"[green]✓ Created wiki domain:[/green] {domain}")
    console.print(f"  Title:       {resolved_title}")
    if description:
        console.print(f"  Description: {description}")
    console.print(f"  Location:    {domain_root}")
    console.print(
        f"  Steering:    {domain_root / 'program.md'}\n  Seeds queue: {domain_root / 'seeds.md'}"
    )


def _write_templates(domain_root: Path, domain: str, title: str) -> None:
    """Render program.md and seeds.md templates into a new domain.

    Both files are skipped if they already exist so reruns of init are safe.
    """
    templates_dir = Path(__file__).parent / "templates"
    program_dest = domain_root / "program.md"
    if not program_dest.exists():
        program_tmpl = (templates_dir / "program.md.tmpl").read_text(encoding="utf-8")
        program_dest.write_text(program_tmpl.format(title=title), encoding="utf-8")
    seeds_dest = domain_root / "seeds.md"
    if not seeds_dest.exists():
        seeds_tmpl = (templates_dir / "seeds.md.tmpl").read_text(encoding="utf-8")
        seeds_dest.write_text(seeds_tmpl.format(domain=domain), encoding="utf-8")


# ── ingest ────────────────────────────────────────────────────────────────────


@wiki_cli.command(name="ingest")
@click.argument("source")
@click.option("--domain", "-d", required=True, help="Target wiki domain")
@click.option(
    "--type",
    "-t",
    "source_type",
    type=click.Choice(["article", "paper", "note", "repo", "clip"]),
    default="article",
    show_default=True,
    help="Source type",
)
@click.option("--title", default=None, help="Override inferred title")
@click.option("--tags", multiple=True, help="Tags to attach (repeatable)")
@click.option("--category", "-c", default=None, help="Category for this source")
@click.option("--compile-now", is_flag=True, help="Compile immediately after ingestion")
def ingest(
    source: str,
    domain: str,
    source_type: str,
    title: str | None,
    tags: tuple[str, ...],
    category: str | None,
    compile_now: bool,
) -> None:
    """Ingest SOURCE into a wiki domain's raw/ directory.

    SOURCE may be a URL, a file path, or a directory path.
    When SOURCE is a directory, all .md and .pdf files are ingested recursively.
    """
    from jarvis.wiki.config import get_domain_root, load_schema
    from jarvis.wiki.log import LogAppender
    from jarvis.wiki.models import LogEntry, LogEntryType, SourceType
    from jarvis.wiki.parser import ingest_to_raw

    domain_root = get_domain_root(domain)
    if not domain_root.exists():
        console.print(f"[red]Domain not found: {domain}[/red]")
        console.print("[dim]Run `jarvis wiki init <domain>` first.[/dim]")
        raise SystemExit(1)

    try:
        schema = load_schema(domain)
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise SystemExit(1)

    src_type = SourceType(source_type)

    # Collect sources to ingest
    sources_to_ingest: list[str] = []
    src_path = Path(source)
    if src_path.is_dir():
        for f in sorted(src_path.rglob("*")):
            if f.suffix.lower() in {".md", ".pdf"}:
                sources_to_ingest.append(str(f))
        if not sources_to_ingest:
            console.print(f"[yellow]No .md or .pdf files found in {source}[/yellow]")
            return
    else:
        sources_to_ingest.append(source)

    ingested_paths: list[Path] = []
    for src in sources_to_ingest:
        try:
            dest = ingest_to_raw(
                src,
                domain_root,
                src_type,
                title=title if len(sources_to_ingest) == 1 else None,
            )
            ingested_paths.append(dest)
            console.print(f"  [cyan]ingest[/cyan] {Path(src).name} → {dest.name}")
        except Exception as exc:
            console.print(f"  [red]error[/red] {src}: {exc}")

    if not ingested_paths:
        raise SystemExit(1)

    # Append INGEST log entry
    LogAppender.append(
        domain_root,
        LogEntry(
            entry_type=LogEntryType.INGEST,
            description=(
                f"Ingested {len(ingested_paths)} source(s) of type '{source_type}' from {source}"
            ),
            metadata={"tags": list(tags), "category": category},
        ),
    )

    console.print(f"[green]✓ Ingested {len(ingested_paths)} source(s) into '{domain}'[/green]")

    if compile_now:
        console.print()
        _run_compile(
            domain,
            domain_root,
            schema,
            force=False,
            source=str(ingested_paths[0]) if len(ingested_paths) == 1 else None,
            dry_run=False,
            verbose=True,
        )


# ── compile ───────────────────────────────────────────────────────────────────


@wiki_cli.command(name="compile")
@click.option("--domain", "-d", required=True, help="Target wiki domain")
@click.option("--force", is_flag=True, help="Recompile all sources even if unchanged")
@click.option("--source", default=None, help="Compile only this specific raw file")
@click.option("--dry-run", is_flag=True, help="Show what would be compiled without LLM calls")
@click.option("--verbose", "-v", is_flag=True, help="Print per-step progress")
def compile_cmd(
    domain: str,
    force: bool,
    source: str | None,
    dry_run: bool,
    verbose: bool,
) -> None:
    """Run the compilation pipeline for a wiki domain."""
    from jarvis.wiki.config import get_domain_root, load_schema

    domain_root = get_domain_root(domain)
    if not domain_root.exists():
        console.print(f"[red]Domain not found: {domain}[/red]")
        console.print("[dim]Run `jarvis wiki init <domain>` first.[/dim]")
        raise SystemExit(1)

    try:
        schema = load_schema(domain)
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise SystemExit(1)

    _run_compile(
        domain,
        domain_root,
        schema,
        force=force,
        source=source,
        dry_run=dry_run,
        verbose=verbose,
    )


def _run_compile(
    domain: str,
    domain_root: Path,
    schema: WikiDomain,
    force: bool,
    source: str | None,
    dry_run: bool,
    verbose: bool,
) -> None:
    """Shared compile logic used by both `compile` and `ingest --compile-now`."""
    from jarvis.wiki.compiler import WikiCompiler

    if dry_run:
        console.print("[dim](dry-run: no LLM calls will be made)[/dim]")

    if verbose:
        console.print(f"[dim]Backend: {schema.llm.backend}[/dim]")

    compiler = WikiCompiler(domain_root, schema)
    stats = compiler.compile(force=force, source=source, dry_run=dry_run, verbose=verbose)

    # Summary table
    table = Table(title=f"Compile Summary — {domain}", show_header=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Count", justify="right")

    table.add_row("Sources compiled", str(stats["sources_compiled"]))
    table.add_row("Sources skipped", str(stats["sources_skipped"]))
    table.add_row("Concepts created", str(stats["concepts_created"]))
    table.add_row("Concepts updated", str(stats["concepts_updated"]))
    table.add_row("Concepts aliased", str(stats.get("concepts_aliased", 0)))
    table.add_row("Errors", str(len(stats["errors"])))

    console.print()
    console.print(table)

    if stats["errors"]:
        console.print()
        console.print("[red]Errors:[/red]")
        for err in stats["errors"]:
            console.print(f"  [red]•[/red] {err}")


# ── status ────────────────────────────────────────────────────────────────────


@wiki_cli.command(name="status")
@click.option("--domain", "-d", default=None, help="Domain to inspect")
@click.option("--all", "show_all", is_flag=True, help="Show all domains")
def status(domain: str | None, show_all: bool) -> None:
    """Show wiki domain status and article counts."""
    from jarvis.wiki.config import WIKIS_ROOT, get_domain_root

    if show_all or domain is None:
        _show_all_domains(WIKIS_ROOT)
    else:
        _show_domain_status(domain, get_domain_root(domain))


def _show_all_domains(wikis_root: Path) -> None:
    """Scan and display status for all domains."""
    if not wikis_root.exists():
        console.print(f"[yellow]No wikis directory found: {wikis_root}[/yellow]")
        return

    domains = sorted(d for d in wikis_root.iterdir() if d.is_dir())
    if not domains:
        console.print("[yellow]No wiki domains found.[/yellow]")
        console.print("[dim]Run `jarvis wiki init <domain>` to create one.[/dim]")
        return

    table = Table(title="Wiki Domains", show_header=True)
    table.add_column("Domain", style="cyan bold")
    table.add_column("Title")
    table.add_column("Summaries", justify="right")
    table.add_column("Concepts", justify="right")
    table.add_column("Raw Sources", justify="right")
    table.add_column("Uncompiled", justify="right")
    table.add_column("Last Compile")

    for domain_root in domains:
        domain_name = domain_root.name
        row = _gather_domain_stats(domain_root)
        table.add_row(
            domain_name,
            row["title"],
            str(row["summaries"]),
            str(row["concepts"]),
            str(row["raw_sources"]),
            str(row["uncompiled"]),
            row["last_compile"],
        )

    console.print()
    console.print(table)


def _show_domain_status(domain: str, domain_root: Path) -> None:
    """Display status for a single domain."""
    if not domain_root.exists():
        console.print(f"[red]Domain not found: {domain}[/red]")
        console.print("[dim]Run `jarvis wiki init <domain>` to create one.[/dim]")
        raise SystemExit(1)

    row = _gather_domain_stats(domain_root)

    table = Table(title=f"Wiki Status — {domain}", show_header=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Value")

    table.add_row("Title", row["title"])
    table.add_row("Location", str(domain_root))
    table.add_row("Summaries", str(row["summaries"]))
    table.add_row("Concepts", str(row["concepts"]))
    table.add_row("Raw Sources", str(row["raw_sources"]))
    table.add_row("Uncompiled", str(row["uncompiled"]))
    table.add_row("Last Compile", row["last_compile"])

    console.print()
    console.print(table)


# ── ask ───────────────────────────────────────────────────────────────────────


@wiki_cli.command(name="ask")
@click.argument("question", nargs=-1)
@click.option("--domain", "-d", required=True, help="Wiki domain to query")
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["md", "slides", "chart"]),
    default="md",
    show_default=True,
    help="Output format",
)
@click.option(
    "--file-back/--no-file-back", default=True, help="Save synthesized answers to wiki/queries/"
)
@click.option("--interactive", "-i", is_flag=True, help="Enter interactive Q&A loop")
def ask(
    question: tuple[str, ...],
    domain: str,
    output_format: str,
    file_back: bool,
    interactive: bool,
) -> None:
    """Ask a question against a wiki domain.

    QUESTION words are joined into a single question string.
    Use --interactive to enter a loop (Ctrl-C to exit).
    """
    from rich.markdown import Markdown

    from jarvis.wiki.config import get_domain_root, load_schema
    from jarvis.wiki.formatters import format_markdown, format_marp_slides, format_mermaid
    from jarvis.wiki.qa import WikiQA

    domain_root = get_domain_root(domain)
    if not domain_root.exists():
        console.print(f"[red]Domain not found: {domain}[/red]")
        raise SystemExit(1)

    try:
        schema = load_schema(domain)
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise SystemExit(1)

    qa = WikiQA(domain_root, schema)

    def _run_ask(q: str) -> None:
        console.print(f"\n[dim]Querying '{domain}' wiki…[/dim]")
        result = qa.ask(q, file_back=file_back)
        answer_text = result.get("answer", "")
        sources = result.get("sources_used", [])
        confidence = result.get("confidence", 0.0)

        if output_format == "slides":
            output = format_marp_slides(q, answer_text, sources)
            console.print(output)
        elif output_format == "chart":
            output = format_mermaid(answer_text)
            console.print(output)
        else:
            output = format_markdown(answer_text)
            console.print(Markdown(output))

        console.print(
            f"\n[dim]Confidence: {confidence:.0%} | Sources: {', '.join(sources) or 'none'}[/dim]"
        )
        if result.get("filed_to"):
            console.print(f"[dim]Saved to: {result['filed_to']}[/dim]")

    if interactive:
        console.print(f"[cyan]Interactive wiki Q&A — domain: {domain}[/cyan]")
        console.print("[dim]Type your question and press Enter. Ctrl-C to exit.[/dim]\n")
        try:
            while True:
                q = click.prompt("Question")
                if q.strip():
                    _run_ask(q.strip())
                console.print()
        except (KeyboardInterrupt, click.exceptions.Abort):
            console.print("\n[dim]Exiting interactive mode.[/dim]")
        return

    q = " ".join(question).strip()
    if not q:
        console.print("[red]Provide a question as arguments or use --interactive.[/red]")
        raise SystemExit(1)

    _run_ask(q)


# ── search ────────────────────────────────────────────────────────────────────


@wiki_cli.command(name="search")
@click.argument("query")
@click.option("--domain", "-d", required=True, help="Wiki domain to search")
@click.option(
    "--scope",
    type=click.Choice(["wiki", "raw", "all"]),
    default="wiki",
    show_default=True,
    help="Directory scope for search",
)
def search(query: str, domain: str, scope: str) -> None:
    """Grep for QUERY across wiki articles (or raw sources with --scope)."""
    from rich.text import Text

    from jarvis.wiki.config import get_domain_root

    domain_root = get_domain_root(domain)
    if not domain_root.exists():
        console.print(f"[red]Domain not found: {domain}[/red]")
        raise SystemExit(1)

    # Determine search directories
    search_dirs: list[Path] = []
    if scope in ("wiki", "all"):
        search_dirs.append(domain_root / "wiki")
    if scope in ("raw", "all"):
        search_dirs.append(domain_root / "raw")

    pattern = re.compile(query, re.IGNORECASE)
    total_matches = 0

    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        for md_file in sorted(search_dir.rglob("*.md")):
            lines = md_file.read_text(encoding="utf-8", errors="replace").splitlines()
            file_matches: list[tuple[int, str]] = []
            for lineno, line in enumerate(lines, start=1):
                if pattern.search(line):
                    file_matches.append((lineno, line))

            if file_matches:
                rel = md_file.relative_to(domain_root)
                console.print(f"\n[cyan bold]{rel}[/cyan bold]")
                for lineno, line in file_matches[:5]:  # cap at 5 lines per file
                    # Highlight matching portion
                    highlighted = Text()
                    last = 0
                    for m in pattern.finditer(line):
                        highlighted.append(line[last : m.start()])
                        highlighted.append(line[m.start() : m.end()], style="bold yellow")
                        last = m.end()
                    highlighted.append(line[last:])
                    console.print(f"  [dim]{lineno:4d}[/dim]  ", end="")
                    console.print(highlighted)
                if len(file_matches) > 5:
                    console.print(f"  [dim]… {len(file_matches) - 5} more match(es)[/dim]")
                total_matches += len(file_matches)

    if total_matches == 0:
        console.print(f"[yellow]No matches for '{query}' in {domain}/{scope}[/yellow]")
    else:
        console.print(f"\n[green]{total_matches} match(es) found[/green]")


def _gather_domain_stats(domain_root: Path) -> dict[str, Any]:
    """Collect stats for a domain directory."""
    # Title from schema if available
    title = domain_root.name
    schema_path = domain_root / "schema.yaml"
    if schema_path.exists():
        try:
            import yaml

            raw = yaml.safe_load(schema_path.read_text(encoding="utf-8")) or {}
            title = raw.get("title", title)
        except Exception:
            pass

    # Article counts
    summaries = (
        len(list((domain_root / "wiki" / "summaries").glob("*.md")))
        if (domain_root / "wiki" / "summaries").exists()
        else 0
    )
    concepts = (
        len(list((domain_root / "wiki" / "concepts").glob("*.md")))
        if (domain_root / "wiki" / "concepts").exists()
        else 0
    )

    # Raw source count
    raw_root = domain_root / "raw"
    raw_files: list[Path] = []
    if raw_root.exists():
        for subdir in raw_root.iterdir():
            if subdir.is_dir():
                raw_files.extend(
                    f for f in subdir.iterdir() if f.suffix.lower() in {".md", ".pdf", ".txt"}
                )
    raw_sources = len(raw_files)

    # Uncompiled: raw files not in manifest
    uncompiled = 0
    manifest_path = domain_root / ".state" / "manifest.json"
    if manifest_path.exists():
        try:
            import json

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            compiled_keys = set(manifest.get("files", {}).keys())
            uncompiled = sum(1 for f in raw_files if str(f) not in compiled_keys)
        except Exception:
            uncompiled = raw_sources
    else:
        uncompiled = raw_sources

    # Last compile timestamp from log.md
    last_compile = "—"
    log_path = domain_root / "wiki" / "log.md"
    if log_path.exists():
        try:
            lines = log_path.read_text(encoding="utf-8").splitlines()
            for line in reversed(lines):
                if "[COMPILE]" in line:
                    # Extract timestamp portion: [2026-04-05 12:00] [COMPILE] ...
                    import re

                    m = re.search(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\]", line)
                    if m:
                        last_compile = m.group(1)
                    break
        except Exception:
            pass

    return {
        "title": title,
        "summaries": summaries,
        "concepts": concepts,
        "raw_sources": raw_sources,
        "uncompiled": uncompiled,
        "last_compile": last_compile,
    }


# ── lint ──────────────────────────────────────────────────────────────────────


@wiki_cli.command(name="lint")
@click.option("--domain", "-d", required=True, help="Wiki domain to lint")
@click.option("--fix", is_flag=True, help="Auto-fix minor issues where possible")
@click.option("--output", "-o", type=click.Path(), default=None, help="Write report to file")
def lint(domain: str, fix: bool, output: str | None) -> None:
    """Check a wiki domain for quality issues and report health scores."""

    from jarvis.wiki.config import get_domain_root, load_schema
    from jarvis.wiki.lint import WikiLinter
    from jarvis.wiki.log import LogAppender
    from jarvis.wiki.models import LintSeverity, LogEntry, LogEntryType

    domain_root = get_domain_root(domain)
    if not domain_root.exists():
        console.print(f"[red]Domain not found: {domain}[/red]")
        raise SystemExit(1)

    try:
        schema = load_schema(domain)
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise SystemExit(1)

    console.print(f"[dim]Linting domain '{domain}'…[/dim]")
    linter = WikiLinter(domain_root, schema)
    report = linter.lint(fix=fix)

    # ── Summary line ──────────────────────────────────────────────────────────
    score_color = (
        "green" if report.domain_score >= 80 else "yellow" if report.domain_score >= 60 else "red"
    )
    console.print(
        f"\n[bold]Domain:[/bold] {domain}  "
        f"[bold]Articles:[/bold] {report.total_articles}  "
        f"[bold]Health Score:[/bold] [{score_color}]{report.domain_score:.1f}/100[/{score_color}]  "
        f"[bold]Issues:[/bold] {len(report.issues)}"
    )

    if not report.issues:
        console.print("[green]✓ No issues found.[/green]")
    else:
        # Group by severity
        by_severity: dict[LintSeverity, list[Any]] = {
            LintSeverity.ERROR: [],
            LintSeverity.WARNING: [],
            LintSeverity.INFO: [],
        }
        for issue in report.issues:
            by_severity[issue.severity].append(issue)

        severity_styles = {
            LintSeverity.ERROR: ("red", "✗"),
            LintSeverity.WARNING: ("yellow", "⚠"),
            LintSeverity.INFO: ("dim", "·"),
        }

        for sev in (LintSeverity.ERROR, LintSeverity.WARNING, LintSeverity.INFO):
            group = by_severity[sev]
            if not group:
                continue
            color, icon = severity_styles[sev]
            console.print(f"\n[{color} bold]{sev.value.upper()} ({len(group)})[/{color} bold]")
            for issue in group:
                score = report.health_scores.get(issue.article_slug, "—")
                console.print(
                    f"  [{color}]{icon}[/{color}] [cyan]{issue.article_slug}[/cyan]  "
                    f"{issue.message}  [dim](score: {score})[/dim]"
                )

    # ── Per-article scores table ───────────────────────────────────────────────
    if report.health_scores:
        table = Table(title="Article Health Scores", show_header=True, title_justify="left")
        table.add_column("Article", style="cyan")
        table.add_column("Score", justify="right")
        for slug, score in sorted(report.health_scores.items(), key=lambda x: x[1]):
            color = "green" if score >= 80 else "yellow" if score >= 60 else "red"
            table.add_row(slug, f"[{color}]{score}[/{color}]")
        console.print()
        console.print(table)

    # ── Write report to file ───────────────────────────────────────────────────
    if output:
        import json

        out_path = Path(output)
        out_path.write_text(
            json.dumps(
                {
                    "domain": report.domain,
                    "domain_score": report.domain_score,
                    "total_articles": report.total_articles,
                    "issues": [
                        {
                            "slug": i.article_slug,
                            "check": i.check,
                            "severity": i.severity.value,
                            "message": i.message,
                        }
                        for i in report.issues
                    ],
                    "health_scores": report.health_scores,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        console.print(f"\n[dim]Report written to {out_path}[/dim]")

    # ── Log entry ─────────────────────────────────────────────────────────────
    LogAppender.append(
        domain_root,
        LogEntry(
            entry_type=LogEntryType.LINT,
            description=(
                f"Lint complete — score {report.domain_score:.1f}/100, "
                f"{len(report.issues)} issue(s)"
            ),
            metadata={"issues": len(report.issues), "score": report.domain_score},
        ),
    )


# ── enhance ───────────────────────────────────────────────────────────────────


@wiki_cli.command(name="enhance")
@click.option("--domain", "-d", required=True, help="Wiki domain to enhance")
@click.option("--article", default=None, help="Enhance a specific article slug")
@click.option("--stale-only", is_flag=True, help="Show only stale articles")
def enhance(domain: str, article: str | None, stale_only: bool) -> None:
    """Identify articles needing improvement and suggest enhancements."""
    from jarvis.wiki.config import get_domain_root, load_schema
    from jarvis.wiki.lint import WikiLinter
    from jarvis.wiki.log import LogAppender
    from jarvis.wiki.models import LogEntry, LogEntryType

    domain_root = get_domain_root(domain)
    if not domain_root.exists():
        console.print(f"[red]Domain not found: {domain}[/red]")
        raise SystemExit(1)

    try:
        schema = load_schema(domain)
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise SystemExit(1)

    console.print(f"[dim]Analyzing '{domain}' for enhancement opportunities…[/dim]")
    linter = WikiLinter(domain_root, schema)
    report = linter.lint()

    # Filter issues to enhancement-relevant checks
    enhance_checks = {"thin_article", "stale_claim", "missing_summary", "uncategorized"}
    candidates = [
        i
        for i in report.issues
        if i.check in enhance_checks
        and (article is None or i.article_slug == article)
        and (not stale_only or i.check == "stale_claim")
    ]

    if not candidates:
        console.print("[green]No enhancement candidates found.[/green]")
        return

    console.print(f"\n[bold]Enhancement candidates in '{domain}':[/bold] {len(candidates)}\n")

    # Group by article
    by_slug: dict[str, list[Any]] = {}
    for issue in candidates:
        by_slug.setdefault(issue.article_slug, []).append(issue)

    for slug, issues in sorted(by_slug.items()):
        score = report.health_scores.get(slug, "?")
        console.print(f"[cyan bold]{slug}[/cyan bold]  [dim](score: {score})[/dim]")
        for issue in issues:
            if issue.check == "thin_article":
                console.print(
                    f"  · Thin article ({issue.detail} words) — "
                    "add more detail or ingest additional sources"
                )
            elif issue.check == "stale_claim":
                console.print(f"  · Last updated {issue.detail} — re-ingest or review for currency")
            elif issue.check == "missing_summary":
                console.print(f"  · Raw source not compiled — run: jarvis wiki compile -d {domain}")
            elif issue.check == "uncategorized":
                console.print("  · No category — assign one in frontmatter")
        console.print()

    LogAppender.append(
        domain_root,
        LogEntry(
            entry_type=LogEntryType.ENHANCE,
            description=f"Enhance scan — {len(candidates)} candidate(s) identified",
            metadata={"candidates": len(candidates)},
        ),
    )


# ── open ──────────────────────────────────────────────────────────────────────


@wiki_cli.command(name="open")
@click.option("--domain", "-d", required=True, help="Wiki domain to open")
@click.option(
    "--app",
    type=click.Choice(["obsidian", "cursor", "vscode"]),
    default="obsidian",
    show_default=True,
    help="Application to open the wiki in",
)
def open_wiki(domain: str, app: str) -> None:
    """Open a wiki domain in Obsidian, Cursor, or VS Code."""
    import subprocess

    from jarvis.wiki.config import get_domain_root
    from jarvis.wiki.obsidian import get_obsidian_url

    domain_root = get_domain_root(domain)
    if not domain_root.exists():
        console.print(f"[red]Domain not found: {domain}[/red]")
        raise SystemExit(1)

    wiki_path = domain_root / "wiki"

    if app == "obsidian":
        url = get_obsidian_url(domain_root)
        console.print(f"[dim]Opening in Obsidian: {url}[/dim]")
        subprocess.run(["open", url], check=False)
    elif app == "cursor":
        console.print(f"[dim]Opening in Cursor: {wiki_path}[/dim]")
        subprocess.run(["cursor", str(wiki_path)], check=False)
    elif app == "vscode":
        console.print(f"[dim]Opening in VS Code: {wiki_path}[/dim]")
        subprocess.run(["code", str(wiki_path)], check=False)


# ── export ────────────────────────────────────────────────────────────────────


@wiki_cli.command(name="export")
@click.option("--domain", "-d", required=True, help="Wiki domain to export")
@click.option(
    "--format",
    "-f",
    "export_format",
    type=click.Choice(["zip", "html"]),
    default="zip",
    show_default=True,
    help="Export format",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Output path (default: current directory)",
)
def export(domain: str, export_format: str, output: str | None) -> None:
    """Package a wiki domain for sharing or backup."""
    import shutil

    from jarvis.wiki.config import get_domain_root
    from jarvis.wiki.log import LogAppender
    from jarvis.wiki.models import LogEntry, LogEntryType

    domain_root = get_domain_root(domain)
    if not domain_root.exists():
        console.print(f"[red]Domain not found: {domain}[/red]")
        raise SystemExit(1)

    wiki_path = domain_root / "wiki"
    base_name = output or f"{domain}-wiki"
    # Strip extension if user included one; make_archive adds it
    base_name = str(base_name).removesuffix(".zip").removesuffix(".html")

    if export_format == "zip":
        out_path = shutil.make_archive(base_name, "zip", root_dir=wiki_path.parent, base_dir="wiki")
        console.print(f"[green]✓ Exported:[/green] {out_path}")

    elif export_format == "html":
        # Placeholder: copy .md files to an html/ directory
        out_dir = Path(base_name + "-html")
        out_dir.mkdir(parents=True, exist_ok=True)
        count = 0
        for md_file in wiki_path.rglob("*.md"):
            rel = md_file.relative_to(wiki_path)
            dest = out_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(md_file, dest)
            count += 1
        console.print(f"[green]✓ Exported {count} articles to:[/green] {out_dir}")
        console.print(
            "[dim](HTML: static site generation is a future feature — .md files copied)[/dim]"
        )

    LogAppender.append(
        domain_root,
        LogEntry(
            entry_type=LogEntryType.EXPORT,
            description=f"Exported domain '{domain}' as {export_format}",
            metadata={"format": export_format},
        ),
    )


# ── program ───────────────────────────────────────────────────────────────────


@wiki_cli.command(name="program")
@click.option("--domain", "-d", required=True, help="Wiki domain")
@click.option("--edit", is_flag=True, help="Open program.md in $EDITOR")
@click.option("--validate", is_flag=True, help="Parse and report any warnings")
def program(domain: str, edit: bool, validate: bool) -> None:
    """View, edit, or validate the per-domain research steering file."""
    import os
    import subprocess

    from jarvis.wiki.config import get_domain_root
    from jarvis.wiki.program import load_program, program_path

    domain_root = get_domain_root(domain)
    if not domain_root.exists():
        console.print(f"[red]Domain not found: {domain}[/red]")
        raise SystemExit(1)

    path = program_path(domain_root)
    if not path.exists():
        console.print(
            f"[yellow]No program.md at {path}. "
            "Run `jarvis wiki init {domain}` (or create it manually).[/yellow]"
        )
        raise SystemExit(1)

    if edit:
        editor = os.environ.get("EDITOR", "vi")
        subprocess.run([editor, str(path)], check=False)
        return

    parsed = load_program(domain_root, domain)
    if validate:
        if parsed.parse_warnings:
            console.print(f"[yellow]{len(parsed.parse_warnings)} warning(s):[/yellow]")
            for w in parsed.parse_warnings:
                console.print(f"  ⚠ {w}")
            raise SystemExit(1)
        console.print("[green]✓ program.md is valid[/green]")
        return

    # Default: pretty-print summary
    console.print(f"[bold]{domain}[/bold] research program — [dim]{path}[/dim]")
    console.print()
    console.print(f"[cyan]Active topics ({len(parsed.active_topics)}):[/cyan]")
    for topic in parsed.active_topics:
        last = f" — last_researched: {topic.last_researched}" if topic.last_researched else ""
        console.print(f"  · {topic.name} (depth: {topic.depth.value}){last}")
    if parsed.avoid_topics:
        console.print(f"\n[cyan]Avoid:[/cyan] {', '.join(parsed.avoid_topics)}")
    if parsed.source_preferences.prefer:
        console.print(
            f"\n[cyan]Prefer sources:[/cyan] {', '.join(parsed.source_preferences.prefer)}"
        )
    if parsed.source_preferences.deprioritize:
        console.print(
            f"[cyan]Deprioritize:[/cyan] {', '.join(parsed.source_preferences.deprioritize)}"
        )
    console.print(
        f"\n[cyan]Cadence:[/cyan] {parsed.cadence.autonomous_research}"
        f" (max {parsed.cadence.max_sources_per_session} sources/session)"
    )
    if parsed.parse_warnings:
        console.print()
        console.print(f"[yellow]{len(parsed.parse_warnings)} parse warning(s):[/yellow]")
        for w in parsed.parse_warnings:
            console.print(f"  ⚠ {w}")


# ── seed ──────────────────────────────────────────────────────────────────────


@wiki_cli.command(name="seed")
@click.option("--domain", "-d", required=True, help="Wiki domain")
@click.option("--url", default=None, help="Add a URL seed")
@click.option("--topic", default=None, help="Add a topic seed")
@click.option("--note", default=None, help="Add a note seed (or attach to URL/topic)")
@click.option(
    "--priority",
    type=click.Choice(["high", "medium", "low"]),
    default="medium",
    show_default=True,
)
@click.option("--list", "list_only", is_flag=True, help="Show pending and processed counts")
def seed(
    domain: str,
    url: str | None,
    topic: str | None,
    note: str | None,
    priority: str,
    list_only: bool,
) -> None:
    """Add a research seed (URL, topic, or note) or list the queue."""
    from jarvis.wiki.config import get_domain_root
    from jarvis.wiki.seeds import (
        Seed,
        SeedKind,
        SeedPriority,
        append_seed,
        load_seeds,
        seeds_path,
    )

    domain_root = get_domain_root(domain)
    if not domain_root.exists():
        console.print(f"[red]Domain not found: {domain}[/red]")
        raise SystemExit(1)

    if list_only:
        sf = load_seeds(domain_root, domain)
        console.print(
            f"[bold]{domain}[/bold] seeds — "
            f"[green]{sf.pending_count()} pending[/green], "
            f"[dim]{sf.processed_count()} processed[/dim]"
        )
        for s in sf.pending:
            tag = f"[{s.priority.value}]"
            console.print(f"  · {s.kind.value:6} {tag:8} {s.value}")
            if s.notes:
                console.print(f"      [dim]{s.notes}[/dim]")
        return

    provided = sum(1 for v in (url, topic, note) if v)
    if provided == 0:
        console.print("[red]Specify one of --url, --topic, --note, or --list[/red]")
        raise SystemExit(1)
    if provided > 1 and not (url and note) and not (topic and note):
        # Allow note as a sidecar to a URL/topic, but not URL+topic together.
        console.print(
            "[red]--url and --topic are mutually exclusive. "
            "Use --note alongside either to attach context.[/red]"
        )
        raise SystemExit(1)

    if url:
        new_seed = Seed(
            kind=SeedKind.URL,
            value=url,
            notes=note or "",
            priority=SeedPriority(priority),
        )
    elif topic:
        new_seed = Seed(
            kind=SeedKind.TOPIC,
            value=topic,
            notes=note or "",
            priority=SeedPriority(priority),
        )
    else:
        assert note  # narrowed by checks above
        new_seed = Seed(
            kind=SeedKind.NOTE,
            value=note,
            priority=SeedPriority(priority),
        )

    sf = append_seed(domain_root, domain, new_seed)
    console.print(f"[green]✓ Added {new_seed.kind.value} seed[/green] (id: {new_seed.id})")
    console.print(f"  {seeds_path(domain_root)}  — {sf.pending_count()} pending now")


# ── research ──────────────────────────────────────────────────────────────────


@wiki_cli.command(name="research")
@click.option("--domain", "-d", required=True, help="Wiki domain")
@click.option(
    "--topic",
    default=None,
    help="Specific topic to research; omit to auto-pick from program.md",
)
@click.option(
    "--max-sources",
    default=None,
    type=int,
    help="Cap on sources fetched this session (overrides program.md)",
)
@click.option(
    "--seeds-only",
    is_flag=True,
    help="Process only pending seeds; ignore program topics",
)
@click.option(
    "--auto-compile/--no-auto-compile",
    default=True,
    help="Run compile after the agent finishes (default: yes)",
)
@click.option(
    "--max-turns",
    default=25,
    type=int,
    show_default=True,
    help="Agent turn budget",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Build the agent prompt and persist it, but don't spawn the agent",
)
def research(
    domain: str,
    topic: str | None,
    max_sources: int | None,
    seeds_only: bool,
    auto_compile: bool,
    max_turns: int,
    dry_run: bool,
) -> None:
    """Run an autonomous research session for a wiki domain.

    Spawns a Claude agent with WebSearch/WebFetch/Read/Write tools, reads
    `program.md` and `seeds.md`, finds new sources online, drops them into
    `raw/articles/`, and (by default) runs the compile pipeline on the new
    files. Findings land in `.state/findings/` for the morning brief.
    """
    from jarvis.wiki.config import get_domain_root, load_schema
    from jarvis.wiki.research import WikiResearcher

    domain_root = get_domain_root(domain)
    if not domain_root.exists():
        console.print(f"[red]Domain not found: {domain}[/red]")
        raise SystemExit(1)

    schema = load_schema(domain)
    researcher = WikiResearcher(domain_root, schema)

    console.print(f"[bold]Research session — {domain}[/bold]")
    if dry_run:
        console.print("[yellow](dry-run: prompt will be built but no agent spawned)[/yellow]")

    session = researcher.research(
        topic=topic,
        max_sources=max_sources,
        seeds_only=seeds_only,
        auto_compile=auto_compile,
        dry_run=dry_run,
        max_turns=max_turns,
    )

    console.print(f"  Session id:  {session.session_id}")
    console.print(f"  Topic:       {session.topic}")
    console.print(f"  Mode:        {session.mode}")
    console.print(f"  Max sources: {session.max_sources}")
    console.print(
        f"  Session dir: {domain_root / '.state' / 'research-sessions' / session.session_id}"
    )

    if dry_run:
        console.print(
            f"\n[dim]Prompt written to: "
            f"{domain_root / '.state' / 'research-sessions' / session.session_id / 'prompt.txt'}"
            "[/dim]"
        )
        return

    table = Table(title=f"Research summary — {session.session_id}")
    table.add_column("Metric")
    table.add_column("Count", justify="right")
    table.add_row("Files created", str(len(session.files_created)))
    table.add_row("Files rejected", str(len(session.files_rejected)))
    table.add_row("Seeds consumed", str(len(session.seeds_consumed)))
    table.add_row("Errors", str(len(session.errors)))
    if session.compile_stats:
        table.add_row("Concepts created", str(session.compile_stats.get("concepts_created", 0)))
        table.add_row("Concepts updated", str(session.compile_stats.get("concepts_updated", 0)))
        table.add_row("Concepts aliased", str(session.compile_stats.get("concepts_aliased", 0)))
    console.print()
    console.print(table)

    if session.errors:
        console.print("\n[red]Errors:[/red]")
        for err in session.errors:
            console.print(f"  · {err}")
    if session.files_rejected:
        console.print("\n[yellow]Rejected files:[/yellow]")
        for path, reason in session.files_rejected:
            console.print(f"  · {path.name} — {reason}")


# ── dedupe ────────────────────────────────────────────────────────────────────


@wiki_cli.command(name="dedupe")
@click.option("--domain", "-d", required=True, help="Wiki domain")
@click.option(
    "--confirm",
    is_flag=True,
    help="Actually perform the merges. Without this flag, dry-run only.",
)
@click.option(
    "--confidence",
    default=0.75,
    type=float,
    show_default=True,
    help="Minimum LLM confidence to confirm a merge",
)
@click.option(
    "--max-pairs",
    default=None,
    type=int,
    help="Stop after considering N candidate pairs (useful for safe trial runs)",
)
def dedupe(
    domain: str,
    confirm: bool,
    confidence: float,
    max_pairs: int | None,
) -> None:
    """Find and merge legacy duplicate concept pages.

    Track 1's compiler dedup prevents NEW duplicates; this command collapses
    duplicates that already exist on disk. For each candidate pair (same
    normalized form OR Jaccard ≥ 0.5) it asks the LLM to confirm, then
    merges the bodies and deletes the secondary file.

    Defaults to dry-run for safety. Pass --confirm to apply.
    """
    from jarvis.wiki.config import get_domain_root, load_schema
    from jarvis.wiki.dedupe import WikiDedupe

    domain_root = get_domain_root(domain)
    if not domain_root.exists():
        console.print(f"[red]Domain not found: {domain}[/red]")
        raise SystemExit(1)

    schema = load_schema(domain)
    deduper = WikiDedupe(domain_root, schema)

    mode = "[bold red]CONFIRM MODE[/bold red]" if confirm else "[yellow]dry-run[/yellow]"
    console.print(f"Dedupe pass on [bold]{domain}[/bold] — {mode}")

    report = deduper.run(
        dry_run=not confirm,
        confidence=confidence,
        max_pairs=max_pairs,
    )

    table = Table(title=f"Dedupe summary — {domain}")
    table.add_column("Metric")
    table.add_column("Count", justify="right")
    table.add_row("Total concepts", str(report.total_concepts))
    table.add_row("Candidate pairs evaluated", str(report.candidate_pairs))
    table.add_row("LLM confirmed merges", str(report.confirmed_merges))
    table.add_row("LLM rejected pairs", str(report.rejected_pairs))
    if confirm:
        table.add_row("Files actually merged", str(len(report.merged_files)))
    table.add_row("Errors", str(len(report.errors)))
    console.print()
    console.print(table)

    if report.proposals:
        console.print("\n[cyan]Proposals:[/cyan]")
        for p in report.proposals:
            mark = "[green]✓[/green]" if p.confirmed else "[red]✗[/red]"
            console.print(f"  {mark} {p.canonical}  ←  {p.secondary}  [dim]({p.reason})[/dim]")
            if p.note:
                console.print(f"      [dim]{p.note}[/dim]")

    if report.errors:
        console.print("\n[red]Errors:[/red]")
        for err in report.errors:
            console.print(f"  · {err}")

    if not confirm and report.confirmed_merges > 0:
        console.print(
            f"\n[yellow]Re-run with --confirm to apply {report.confirmed_merges} merges.[/yellow]"
        )
