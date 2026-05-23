"""CLI commands for meeting transcript ingestion."""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from pathlib import Path

import click
import httpx
from rich.console import Console
from rich.table import Table

from jarvis.config import (
    ConfigError,
    default_env_file_path,
    get_fathom_api_key,
    get_fathom_webhook_secret,
    load_config,
    save_config,
    update_managed_env_var,
)

from .automation import (
    build_fathom_automation_plan,
    require_command,
    start_fathom_tmux_stack,
    tmux_launch_commands,
)
from .fathom import FathomClient
from .poll_state import load_poll_state, poll_account_key, save_poll_state
from .service import (
    ingest_archived_fathom_payload,
    ingest_fathom_inbox,
    ingest_fathom_meeting,
    ingest_fathom_meetings_since,
    ingest_meeting,
    list_fathom_meetings,
)
from .webhook import list_inbox_files, serve_fathom_webhook

console = Console()

_WEBHOOK_TRIGGER_CHOICES = [
    "my_recordings",
    "shared_external_recordings",
    "my_shared_with_team_recordings",
    "shared_team_recordings",
]
_DESTINATION_CHOICES = ["private-context", "wiki", "journal", "memory"]


def _configured_fathom_accounts() -> list[str | None]:
    """Return account labels that should be polled by default."""

    cfg = load_config(reload=True)
    if cfg.fathom.accounts:
        accounts = sorted(cfg.fathom.accounts)
        available = []
        for account in accounts:
            try:
                get_fathom_api_key(account)
            except ConfigError:
                continue
            available.append(account)
        return available or accounts
    if cfg.fathom.default_account:
        return [cfg.fathom.default_account]
    return [None]


def _poll_created_after(
    *,
    now: datetime,
    account_state: dict[str, object],
    initial_lookback_hours: float,
    overlap_hours: float,
) -> str:
    """Compute the next poll created_after value from persisted account state."""

    previous_success = account_state.get("last_successful_poll_at")
    if isinstance(previous_success, str) and previous_success.strip():
        try:
            previous_dt = datetime.fromisoformat(previous_success)
        except ValueError:
            previous_dt = now - timedelta(hours=initial_lookback_hours)
        else:
            return (previous_dt - timedelta(hours=overlap_hours)).isoformat()
    return (now - timedelta(hours=initial_lookback_hours)).isoformat()


@click.group(name="meeting")
def meeting_cli() -> None:
    """Ingest meeting transcripts and summaries into Jarvis destinations."""


@meeting_cli.group(name="fathom")
def fathom_group() -> None:
    """Pull and ingest meetings directly from Fathom."""


@fathom_group.group(name="webhook")
def fathom_webhook_group() -> None:
    """Receive and process local Fathom webhooks."""


@meeting_cli.command(name="ingest")
@click.argument("source")
@click.option(
    "--resolver",
    type=click.Choice(["anytype", "notion", "file", "url", "stdin"]),
    default=None,
    help="Override source resolution",
)
@click.option("--backend", default=None, help="Backend override for object-based resolvers")
@click.option("--title", default=None, help="Override the inferred meeting title")
@click.option("--project", default="", help="Attach a project slug or label")
@click.option(
    "--auto-route/--no-auto-route",
    default=False,
    help="Infer project from private meeting route rules when --project is omitted",
)
@click.option("--tag", "tags", multiple=True, help="Attach tags (repeatable)")
@click.option(
    "--dest",
    "destinations",
    multiple=True,
    type=click.Choice(_DESTINATION_CHOICES),
    help="Destination to write to (defaults to private-context)",
)
@click.option("--wiki-domain", default=None, help="Wiki domain when using the wiki destination")
@click.option("--enrich-ai/--no-enrich-ai", default=True, help="Use AI to fill missing sections")
@click.option("--json", "as_json", is_flag=True, help="Emit the result as JSON")
def ingest_command(
    source: str,
    resolver: str | None,
    backend: str | None,
    title: str | None,
    project: str,
    auto_route: bool,
    tags: tuple[str, ...],
    destinations: tuple[str, ...],
    wiki_domain: str | None,
    enrich_ai: bool,
    as_json: bool,
) -> None:
    """Ingest a meeting transcript-like source into one or more destinations.

    SOURCE may be a file path, URL, AnyType/Notion object, or '-' for stdin.
    """

    try:
        result = ingest_meeting(
            source,
            resolver=resolver,
            backend=backend,
            title=title,
            project=project,
            auto_route=auto_route,
            tags=list(tags) or None,
            destinations=list(destinations),
            wiki_domain=wiki_domain,
            enrich_ai=enrich_ai,
        )
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise SystemExit(1)

    if as_json:
        click.echo(json.dumps(result.model_dump(mode="json"), indent=2))
        return

    console.print(f"[green]Ingested:[/green] {result.meeting.title}")
    console.print(f"[dim]Date:[/dim] {result.meeting.meeting_date.isoformat()}")
    console.print(f"[dim]Destinations:[/dim] {', '.join(result.destinations)}")
    for path in result.written_paths:
        console.print(f"[dim]Wrote:[/dim] {path}")
    if result.journal_entry_id:
        console.print(f"[dim]Journal entry:[/dim] {result.journal_entry_id}")


@fathom_group.command(name="list")
@click.option("--account", default=None, help="Named Fathom account from config")
@click.option("--limit", default=10, help="Number of meetings to list")
@click.option(
    "--created-after",
    default=None,
    help="Filter meetings created after this ISO timestamp",
)
@click.option("--json", "as_json", is_flag=True, help="Emit the result as JSON")
def fathom_list_command(
    account: str | None,
    limit: int,
    created_after: str | None,
    as_json: bool,
) -> None:
    """List recent Fathom meetings with recording IDs for ingestion."""

    try:
        items = list_fathom_meetings(
            account=account,
            limit=limit,
            created_after=created_after,
        )
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise SystemExit(1)

    if as_json:
        click.echo(json.dumps(items, indent=2))
        return

    table = Table(title="Fathom Meetings")
    table.add_column("Recording ID")
    table.add_column("Title")
    table.add_column("Created At")
    for item in items:
        title = str(item.get("meeting_title") or item.get("title") or "Untitled")
        table.add_row(
            str(item.get("recording_id") or ""),
            title,
            str(item.get("created_at") or item.get("recording_start_time") or ""),
        )
    console.print(table)


@fathom_group.command(name="ingest")
@click.argument("recording_id")
@click.option("--account", default=None, help="Named Fathom account from config")
@click.option("--project", default="", help="Attach a project slug or label")
@click.option(
    "--auto-route/--no-auto-route",
    default=False,
    help="Infer project from private meeting route rules when --project is omitted",
)
@click.option("--tag", "tags", multiple=True, help="Attach tags (repeatable)")
@click.option(
    "--dest",
    "destinations",
    multiple=True,
    type=click.Choice(_DESTINATION_CHOICES),
    help="Destination to write to (defaults to private-context)",
)
@click.option("--wiki-domain", default=None, help="Wiki domain when using the wiki destination")
@click.option(
    "--created-after",
    default=None,
    help="Limit Fathom search to meetings after this ISO timestamp",
)
@click.option("--backend", default=None, help="Backend override for the journal destination")
@click.option("--json", "as_json", is_flag=True, help="Emit the result as JSON")
def fathom_ingest_command(
    recording_id: str,
    account: str | None,
    project: str,
    auto_route: bool,
    tags: tuple[str, ...],
    destinations: tuple[str, ...],
    wiki_domain: str | None,
    created_after: str | None,
    backend: str | None,
    as_json: bool,
) -> None:
    """Fetch a Fathom meeting by recording ID and ingest it into destinations."""

    try:
        result = ingest_fathom_meeting(
            recording_id,
            account=account,
            project=project,
            auto_route=auto_route,
            tags=list(tags) or None,
            destinations=list(destinations),
            wiki_domain=wiki_domain,
            created_after=created_after,
            backend=backend,
        )
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise SystemExit(1)

    if as_json:
        click.echo(json.dumps(result.model_dump(mode="json"), indent=2))
        return

    console.print(f"[green]Ingested Fathom recording:[/green] {recording_id}")
    console.print(f"[dim]Title:[/dim] {result.meeting.title}")
    for path in result.written_paths:
        console.print(f"[dim]Wrote:[/dim] {path}")
    if result.journal_entry_id:
        console.print(f"[dim]Journal entry:[/dim] {result.journal_entry_id}")


@fathom_group.command(name="ingest-today")
@click.option("--account", default=None, help="Named Fathom account from config")
@click.option("--date", "target_date", default=None, help="Local date to ingest (YYYY-MM-DD)")
@click.option(
    "--lookback-hours",
    type=click.FloatRange(min=0.0, min_open=True),
    default=None,
    help="Use a rolling lookback window instead of local midnight/date.",
)
@click.option(
    "--all-unpulled",
    is_flag=True,
    help="Scan Fathom pages without a date cutoff and ingest recordings not yet pulled.",
)
@click.option("--limit", default=100, help="Meetings to fetch per Fathom page")
@click.option("--max-pages", default=5, help="Maximum Fathom result pages to scan")
@click.option("--project", default="", help="Attach a project slug or label")
@click.option(
    "--auto-route/--no-auto-route",
    default=False,
    help="Infer project from private meeting route rules when --project is omitted",
)
@click.option("--tag", "tags", multiple=True, help="Attach tags (repeatable)")
@click.option(
    "--dest",
    "destinations",
    multiple=True,
    type=click.Choice(_DESTINATION_CHOICES),
    help="Destination to write to (defaults to private-context)",
)
@click.option("--wiki-domain", default=None, help="Wiki domain when using the wiki destination")
@click.option("--backend", default=None, help="Backend override for the journal destination")
@click.option(
    "--skip-existing/--no-skip-existing",
    default=True,
    help="Skip recordings already present in private meeting context",
)
@click.option("--json", "as_json", is_flag=True, help="Emit the result as JSON")
def fathom_ingest_today_command(
    account: str | None,
    target_date: str | None,
    lookback_hours: float | None,
    all_unpulled: bool,
    limit: int,
    max_pages: int,
    project: str,
    auto_route: bool,
    tags: tuple[str, ...],
    destinations: tuple[str, ...],
    wiki_domain: str | None,
    backend: str | None,
    skip_existing: bool,
    as_json: bool,
) -> None:
    """Ingest Fathom recordings as a webhook safety poll."""

    selected_scope_count = sum(
        bool(value) for value in (target_date, lookback_hours is not None, all_unpulled)
    )
    if selected_scope_count > 1:
        raise click.UsageError(
            "--date, --lookback-hours, and --all-unpulled are mutually exclusive"
        )

    try:
        if all_unpulled:
            created_after = None
        elif lookback_hours is not None:
            created_after = (
                datetime.now().astimezone() - timedelta(hours=lookback_hours)
            ).isoformat()
        else:
            day = date.fromisoformat(target_date) if target_date else date.today()
            created_after = datetime.combine(day, time.min).astimezone().isoformat()
        results = ingest_fathom_meetings_since(
            account=account,
            created_after=created_after,
            limit=limit,
            max_pages=max_pages,
            project=project,
            auto_route=auto_route,
            tags=list(tags) or None,
            destinations=list(destinations),
            wiki_domain=wiki_domain,
            backend=backend,
            skip_existing=skip_existing,
        )
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise SystemExit(1)

    if as_json:
        click.echo(
            json.dumps(
                {
                    "created_after": created_after,
                    "lookback_hours": lookback_hours,
                    "all_unpulled": all_unpulled,
                    "ingested": [result.model_dump(mode="json") for result in results],
                },
                indent=2,
            )
        )
        return

    console.print(f"[green]Ingested Fathom recordings:[/green] {len(results)}")
    for result in results:
        console.print(f"[dim]Meeting:[/dim] {result.meeting.title}")
        for path in result.written_paths:
            console.print(f"[dim]Wrote:[/dim] {path}")


@fathom_group.command(name="poll")
@click.option(
    "--account",
    "accounts",
    multiple=True,
    help="Specific Fathom account to poll (repeatable). Defaults to all configured accounts.",
)
@click.option(
    "--initial-lookback-hours",
    type=click.FloatRange(min=0.0, min_open=True),
    default=48.0,
    show_default=True,
    help="Lookback window for accounts with no prior successful poll.",
)
@click.option(
    "--overlap-hours",
    type=click.FloatRange(min=0.0),
    default=6.0,
    show_default=True,
    help="Safety overlap subtracted from the previous successful poll watermark.",
)
@click.option("--limit", default=100, help="Meetings to fetch per Fathom page")
@click.option("--max-pages", default=5, help="Maximum Fathom result pages to scan per account")
@click.option("--project", default="", help="Attach a project slug or label")
@click.option(
    "--auto-route/--no-auto-route",
    default=False,
    help="Infer project from private meeting route rules when --project is omitted",
)
@click.option("--tag", "tags", multiple=True, help="Attach tags (repeatable)")
@click.option(
    "--dest",
    "destinations",
    multiple=True,
    type=click.Choice(_DESTINATION_CHOICES),
    help="Destination to write to (defaults to private-context)",
)
@click.option("--wiki-domain", default=None, help="Wiki domain when using the wiki destination")
@click.option("--backend", default=None, help="Backend override for the journal destination")
@click.option(
    "--skip-existing/--no-skip-existing",
    default=True,
    help="Skip recordings already present in private meeting context",
)
@click.option(
    "--state-file",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Override the local poll state file path",
)
@click.option("--json", "as_json", is_flag=True, help="Emit the result as JSON")
def fathom_poll_command(
    accounts: tuple[str, ...],
    initial_lookback_hours: float,
    overlap_hours: float,
    limit: int,
    max_pages: int,
    project: str,
    auto_route: bool,
    tags: tuple[str, ...],
    destinations: tuple[str, ...],
    wiki_domain: str | None,
    backend: str | None,
    skip_existing: bool,
    state_file: Path | None,
    as_json: bool,
) -> None:
    """Poll configured Fathom accounts incrementally for unpulled recordings."""

    target_accounts = list(accounts) or _configured_fathom_accounts()
    now = datetime.now().astimezone()
    state = load_poll_state(state_file)
    account_state = state.setdefault("accounts", {})
    if not isinstance(account_state, dict):
        account_state = {}
        state["accounts"] = account_state

    responses: list[dict[str, object]] = []
    had_error = False
    for account in target_accounts:
        key = poll_account_key(account)
        existing = account_state.get(key)
        if not isinstance(existing, dict):
            existing = {}
        created_after = _poll_created_after(
            now=now,
            account_state=existing,
            initial_lookback_hours=initial_lookback_hours,
            overlap_hours=overlap_hours,
        )

        try:
            results = ingest_fathom_meetings_since(
                account=account,
                created_after=created_after,
                limit=limit,
                max_pages=max_pages,
                project=project,
                auto_route=auto_route,
                tags=list(tags) or None,
                destinations=list(destinations),
                wiki_domain=wiki_domain,
                backend=backend,
                skip_existing=skip_existing,
            )
        except Exception as exc:
            had_error = True
            existing["last_error"] = str(exc)
            existing["last_failed_poll_at"] = now.isoformat()
            existing["last_created_after"] = created_after
            account_state[key] = existing
            responses.append(
                {
                    "account": account,
                    "created_after": created_after,
                    "ingested": [],
                    "error": str(exc),
                }
            )
            continue

        existing.update(
            {
                "last_successful_poll_at": now.isoformat(),
                "last_created_after": created_after,
                "last_ingested_count": len(results),
                "last_error": None,
            }
        )
        account_state[key] = existing
        responses.append(
            {
                "account": account,
                "created_after": created_after,
                "ingested": [result.model_dump(mode="json") for result in results],
            }
        )

    saved_path = save_poll_state(state, state_file)
    output = {
        "poll_started_at": now.isoformat(),
        "state_file": str(saved_path),
        "accounts": responses,
    }

    if as_json:
        click.echo(json.dumps(output, indent=2))
    else:
        for response in responses:
            account_label = response.get("account") or "default"
            ingested = response.get("ingested")
            count = len(ingested) if isinstance(ingested, list) else 0
            if response.get("error"):
                console.print(f"[red]{account_label} failed:[/red] {response['error']}")
            else:
                console.print(f"[green]{account_label} ingested:[/green] {count}")
        console.print(f"[dim]State:[/dim] {saved_path}")

    if had_error:
        raise SystemExit(1)


@fathom_group.command(name="start")
@click.option("--account", default=None, help="Named Fathom account from config")
@click.option("--port", default=8765, help="Local port to bind")
@click.option(
    "--auto-ingest/--no-auto-ingest",
    default=True,
    help="Automatically ingest verified payloads into destinations",
)
@click.option("--project", default="", help="Attach a project slug or label during auto-ingest")
@click.option(
    "--auto-route/--no-auto-route",
    default=False,
    help="Infer project from private meeting route rules when --project is omitted",
)
@click.option("--tag", "tags", multiple=True, help="Attach tags during auto-ingest")
@click.option(
    "--dest",
    "destinations",
    multiple=True,
    type=click.Choice(_DESTINATION_CHOICES),
    help="Destination for auto-ingest (defaults to private-context)",
)
@click.option(
    "--wiki-domain",
    default=None,
    help="Wiki domain when auto-ingesting to the wiki destination",
)
@click.option(
    "--backend",
    default=None,
    help="Backend override when auto-ingesting to the journal destination",
)
@click.option(
    "--layout",
    type=click.Choice(["windows", "panes"]),
    default="windows",
    show_default=True,
    help="Tmux layout for the webhook and tunnel processes",
)
@click.option(
    "--verify-signatures/--no-verify-signatures",
    default=True,
    help="Verify Fathom webhook signatures before accepting payloads",
)
@click.option(
    "--tolerance-seconds",
    default=300,
    help="Maximum webhook timestamp skew when verifying signatures",
)
@click.option("--session-name", default=None, help="Tmux session name to create")
@click.option(
    "--tunnel-name",
    default=None,
    help="Cloudflare named tunnel to run instead of creating a quick trycloudflare URL",
)
@click.option(
    "--attach/--no-attach",
    default=True,
    help="Attach to the tmux session after launching",
)
@click.option("--dry-run", is_flag=True, help="Print the launch plan without creating sessions")
@click.option("--json", "as_json", is_flag=True, help="Emit the launch plan as JSON")
def fathom_start_command(
    account: str | None,
    port: int,
    auto_ingest: bool,
    project: str,
    auto_route: bool,
    tags: tuple[str, ...],
    destinations: tuple[str, ...],
    wiki_domain: str | None,
    backend: str | None,
    layout: str,
    verify_signatures: bool,
    tolerance_seconds: int,
    session_name: str | None,
    tunnel_name: str | None,
    attach: bool,
    dry_run: bool,
    as_json: bool,
) -> None:
    """Launch the Fathom webhook receiver and tunnel together in tmux."""

    try:
        cfg = load_config()
        resolved_account = account
        if not resolved_account:
            account_names = sorted(cfg.fathom.accounts.keys())
            default_account = cfg.fathom.default_account or (
                account_names[0] if account_names else ""
            )
            resolved_account = click.prompt(
                "Fathom account",
                default=default_account,
                show_default=bool(default_account),
            ).strip()
        if not resolved_account:
            raise RuntimeError("A Fathom account is required")

        require_command("tmux")
        require_command("cloudflared")

        resolved_destinations = list(destinations) or ["private-context"]
        resolved_session_name = session_name or f"fathom-{resolved_account}"
        plan = build_fathom_automation_plan(
            session_name=resolved_session_name,
            cwd=Path.cwd(),
            layout=layout,
            account=resolved_account,
            port=port,
            auto_ingest=auto_ingest,
            destinations=resolved_destinations,
            wiki_domain=wiki_domain,
            backend=backend,
            project=project,
            tags=list(tags),
            auto_route=auto_route,
            verify_signatures=verify_signatures,
            tolerance_seconds=tolerance_seconds,
            tunnel_name=tunnel_name,
        )
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise SystemExit(1)

    commands = tmux_launch_commands(plan)
    if as_json:
        click.echo(
            json.dumps(
                {
                    "ok": True,
                    "session_name": plan.session_name,
                    "cwd": str(plan.cwd),
                    "layout": plan.layout,
                    "webhook_command": plan.webhook_command,
                    "tunnel_command": plan.tunnel_command,
                    "tunnel_name": tunnel_name,
                    "tmux_commands": commands,
                    "dry_run": dry_run,
                },
                indent=2,
            )
        )
        return

    if dry_run:
        console.print(f"[cyan]Session:[/cyan] {plan.session_name}")
        console.print(f"[dim]Webhook:[/dim] {plan.webhook_command}")
        console.print(f"[dim]Tunnel:[/dim]  {plan.tunnel_command}")
        return

    try:
        start_fathom_tmux_stack(plan, attach=attach)
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise SystemExit(1)

    console.print(f"[green]Launched tmux session:[/green] {plan.session_name}")
    if plan.layout == "windows":
        console.print("[dim]Switch windows:[/dim] Ctrl-b then n / p")
    else:
        console.print("[dim]Switch panes:[/dim] Ctrl-b then arrow key")
    console.print(f"[dim]Attach:[/dim] tmux attach-session -t {plan.session_name}")


@fathom_webhook_group.command(name="create")
@click.option("--account", default=None, help="Named Fathom account from config")
@click.option("--destination-url", required=True, help="Public URL Fathom should POST to")
@click.option(
    "--triggered-for",
    multiple=True,
    type=click.Choice(_WEBHOOK_TRIGGER_CHOICES),
    default=("my_recordings",),
    show_default=True,
    help="Recording scope that should trigger the webhook (repeatable)",
)
@click.option(
    "--include-transcript/--no-include-transcript",
    default=True,
    help="Include transcripts in webhook payloads",
)
@click.option(
    "--include-summary/--no-include-summary",
    default=True,
    help="Include summaries in webhook payloads",
)
@click.option(
    "--include-action-items/--no-include-action-items",
    default=True,
    help="Include action items in webhook payloads",
)
@click.option(
    "--include-crm-matches/--no-include-crm-matches",
    default=False,
    help="Include CRM matches in webhook payloads",
)
@click.option(
    "--save/--no-save",
    default=True,
    help="Save webhook ID/URL and signing secret to local Jarvis config/env",
)
@click.option("--env-file", default=None, help="Managed env file path for saved secret")
@click.option("--show-secret", is_flag=True, help="Print the webhook signing secret")
@click.option("--json", "as_json", is_flag=True, help="Emit the result as JSON")
def fathom_webhook_create_command(
    account: str | None,
    destination_url: str,
    triggered_for: tuple[str, ...],
    include_transcript: bool,
    include_summary: bool,
    include_action_items: bool,
    include_crm_matches: bool,
    save: bool,
    env_file: str | None,
    show_secret: bool,
    as_json: bool,
) -> None:
    """Create a Fathom webhook via API and optionally persist its secret."""

    try:
        if not any(
            [include_transcript, include_summary, include_action_items, include_crm_matches]
        ):
            raise RuntimeError("At least one include option must be enabled")
        client = FathomClient(account=account)
        webhook = client.create_webhook(
            destination_url=destination_url,
            triggered_for=list(triggered_for),
            include_transcript=include_transcript,
            include_summary=include_summary,
            include_action_items=include_action_items,
            include_crm_matches=include_crm_matches,
        )
        saved = False
        secret_env_var = ""
        if save:
            cfg = load_config(reload=True)
            resolved_account = account or cfg.fathom.default_account
            if not resolved_account or resolved_account not in cfg.fathom.accounts:
                raise RuntimeError("A configured Fathom account is required when using --save")
            acct = cfg.fathom.accounts[resolved_account]
            acct.webhook_id = str(webhook.get("id") or "")
            acct.webhook_destination_url = str(webhook.get("url") or destination_url)
            save_config(cfg)
            secret = str(webhook.get("secret") or "")
            if secret:
                secret_env_var = acct.webhook_secret_env_var
                target = Path(env_file).expanduser() if env_file else default_env_file_path()
                update_managed_env_var(target, secret_env_var, secret)
            saved = True
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise SystemExit(1)

    payload = dict(webhook)
    if payload.get("secret") and not show_secret:
        payload["secret"] = "****"
    payload["saved"] = saved
    if secret_env_var:
        payload["secret_env_var"] = secret_env_var

    if as_json:
        click.echo(json.dumps(payload, indent=2))
        return

    console.print(f"[green]Created Fathom webhook:[/green] {payload.get('id')}")
    console.print(f"[dim]URL:[/dim] {payload.get('url')}")
    if saved:
        console.print("[dim]Saved webhook metadata and signing secret locally.[/dim]")


@fathom_webhook_group.command(name="delete")
@click.argument("webhook_id", required=False)
@click.option("--account", default=None, help="Named Fathom account from config")
@click.option(
    "--clear-saved/--no-clear-saved",
    default=True,
    help="Clear the saved webhook ID after successful deletion",
)
@click.option("--json", "as_json", is_flag=True, help="Emit the result as JSON")
def fathom_webhook_delete_command(
    webhook_id: str | None,
    account: str | None,
    clear_saved: bool,
    as_json: bool,
) -> None:
    """Delete a Fathom webhook via API."""

    try:
        cfg = load_config(reload=True)
        resolved_account = account or cfg.fathom.default_account
        acct = cfg.fathom.accounts.get(resolved_account or "") if resolved_account else None
        resolved_webhook_id = webhook_id or (acct.webhook_id if acct else None)
        if not resolved_webhook_id:
            raise RuntimeError("Webhook ID is required or must be saved in account config")

        client = FathomClient(account=account)
        client.delete_webhook(str(resolved_webhook_id))

        cleared = False
        if clear_saved and acct and acct.webhook_id == str(resolved_webhook_id):
            acct.webhook_id = None
            save_config(cfg)
            cleared = True
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise SystemExit(1)

    payload = {"deleted": str(resolved_webhook_id), "cleared_saved": cleared}
    if as_json:
        click.echo(json.dumps(payload, indent=2))
        return
    console.print(f"[green]Deleted Fathom webhook:[/green] {resolved_webhook_id}")
    if cleared:
        console.print("[dim]Cleared saved webhook ID from account config.[/dim]")


@fathom_webhook_group.command(name="status")
@click.option("--account", default=None, help="Named Fathom account from config")
@click.option(
    "--check-url/--no-check-url",
    default=False,
    help="Attempt an HTTP reachability check against the saved destination URL",
)
@click.option("--json", "as_json", is_flag=True, help="Emit the result as JSON")
def fathom_webhook_status_command(
    account: str | None,
    check_url: bool,
    as_json: bool,
) -> None:
    """Show local Fathom webhook configuration and inbox health."""

    cfg = load_config(reload=True)
    resolved_account = account or cfg.fathom.default_account
    acct = cfg.fathom.accounts.get(resolved_account or "") if resolved_account else None
    if acct is None:
        console.print("[red]Error: configured Fathom account not found[/red]")
        raise SystemExit(1)

    secret_error = ""
    try:
        get_fathom_webhook_secret(resolved_account)
        secret_configured = True
    except Exception as exc:
        secret_configured = False
        secret_error = str(exc)

    status: dict[str, object] = {
        "account": resolved_account,
        "webhook_id": acct.webhook_id,
        "webhook_destination_url": acct.webhook_destination_url,
        "webhook_secret_env_var": acct.webhook_secret_env_var,
        "webhook_secret_configured": secret_configured,
        "pending_count": len(list_inbox_files(resolved_account, state="pending")),
        "invalid_count": len(list_inbox_files(resolved_account, state="invalid")),
        "processed_count": len(list_inbox_files(resolved_account, state="processed")),
    }
    if secret_error:
        status["webhook_secret_error"] = secret_error

    if check_url and acct.webhook_destination_url:
        try:
            response = httpx.get(acct.webhook_destination_url, timeout=10.0)
            status["url_status_code"] = response.status_code
            status["url_reachable"] = True
        except Exception as exc:
            status["url_reachable"] = False
            status["url_error"] = str(exc)

    if as_json:
        click.echo(json.dumps(status, indent=2))
        return

    console.print(f"[cyan]Fathom account:[/cyan] {resolved_account}")
    console.print(f"[dim]Webhook ID:[/dim] {acct.webhook_id or '[none]'}")
    console.print(f"[dim]Destination URL:[/dim] {acct.webhook_destination_url or '[none]'}")
    console.print(
        f"[dim]Secret configured:[/dim] {'yes' if secret_configured else 'no'}"
    )
    console.print(
        "[dim]Inbox:[/dim] "
        f"{status['pending_count']} pending, "
        f"{status['invalid_count']} invalid, "
        f"{status['processed_count']} processed"
    )


@fathom_webhook_group.command(name="serve")
@click.option("--account", default=None, help="Named Fathom account from config")
@click.option("--port", default=8765, help="Local port to bind")
@click.option(
    "--verify-signatures/--no-verify-signatures",
    default=True,
    help="Verify Fathom webhook signatures before accepting payloads",
)
@click.option(
    "--tolerance-seconds",
    default=300,
    help="Maximum webhook timestamp skew when verifying signatures",
)
@click.option(
    "--auto-ingest/--no-auto-ingest",
    default=False,
    help="Automatically ingest each verified webhook payload into destinations",
)
@click.option("--project", default="", help="Attach a project slug or label during auto-ingest")
@click.option(
    "--auto-route/--no-auto-route",
    default=False,
    help="Infer project from private meeting route rules when --project is omitted",
)
@click.option("--tag", "tags", multiple=True, help="Attach tags during auto-ingest")
@click.option(
    "--dest",
    "destinations",
    multiple=True,
    type=click.Choice(_DESTINATION_CHOICES),
    help="Destination for auto-ingest (defaults to private-context)",
)
@click.option(
    "--wiki-domain",
    default=None,
    help="Wiki domain when auto-ingesting to the wiki destination",
)
@click.option(
    "--backend",
    default=None,
    help="Backend override when auto-ingesting to the journal destination",
)
def fathom_webhook_serve_command(
    account: str | None,
    port: int,
    verify_signatures: bool,
    tolerance_seconds: int,
    auto_ingest: bool,
    project: str,
    auto_route: bool,
    tags: tuple[str, ...],
    destinations: tuple[str, ...],
    wiki_domain: str | None,
    backend: str | None,
) -> None:
    """Run a local webhook receiver and archive payloads into the Fathom inbox."""

    console.print(f"[dim]Listening on http://127.0.0.1:{port}[/dim]")
    callback = None
    if auto_ingest:
        resolved_destinations = list(destinations) or ["private-context"]

        def callback(path) -> None:  # type: ignore[no-untyped-def]
            ingest_archived_fathom_payload(
                path,
                account=account,
                project=project,
                auto_route=auto_route,
                tags=list(tags) or None,
                destinations=resolved_destinations,
                wiki_domain=wiki_domain,
                backend=backend,
                keep=False,
            )

    serve_fathom_webhook(
        port=port,
        account=account,
        verify_signatures=verify_signatures,
        tolerance_seconds=tolerance_seconds,
        on_verified=callback,
    )


@fathom_webhook_group.command(name="ingest-inbox")
@click.option("--account", default=None, help="Named Fathom account from config")
@click.option("--project", default="", help="Attach a project slug or label")
@click.option(
    "--auto-route/--no-auto-route",
    default=False,
    help="Infer project from private meeting route rules when --project is omitted",
)
@click.option("--tag", "tags", multiple=True, help="Attach tags (repeatable)")
@click.option(
    "--dest",
    "destinations",
    multiple=True,
    type=click.Choice(_DESTINATION_CHOICES),
    help="Destination to write to (defaults to private-context)",
)
@click.option("--wiki-domain", default=None, help="Wiki domain when using the wiki destination")
@click.option("--backend", default=None, help="Backend override for the journal destination")
@click.option("--limit", default=None, type=int, help="Maximum inbox items to ingest")
@click.option("--keep", is_flag=True, help="Keep inbox files in pending after ingestion")
@click.option("--json", "as_json", is_flag=True, help="Emit the result as JSON")
def fathom_webhook_ingest_inbox_command(
    account: str | None,
    project: str,
    auto_route: bool,
    tags: tuple[str, ...],
    destinations: tuple[str, ...],
    wiki_domain: str | None,
    backend: str | None,
    limit: int | None,
    keep: bool,
    as_json: bool,
) -> None:
    """Ingest archived webhook payloads from the local Fathom inbox."""

    try:
        results = ingest_fathom_inbox(
            account=account,
            project=project,
            auto_route=auto_route,
            tags=list(tags) or None,
            destinations=list(destinations),
            wiki_domain=wiki_domain,
            backend=backend,
            limit=limit,
            keep=keep,
        )
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise SystemExit(1)

    if as_json:
        click.echo(json.dumps([result.model_dump(mode="json") for result in results], indent=2))
        return

    console.print(f"[green]Ingested inbox payloads:[/green] {len(results)}")
    for result in results:
        console.print(f"[dim]Meeting:[/dim] {result.meeting.title}")
        for path in result.written_paths:
            console.print(f"[dim]Wrote:[/dim] {path}")
