"""CLI commands for WhatsApp channel integration."""

from __future__ import annotations

import json
from typing import Any

import click
from rich.console import Console
from rich.table import Table

from jarvis.config import (
    ConfigError,
    get_whatsapp_access_token,
    get_whatsapp_account_config,
    get_whatsapp_app_secret,
    get_whatsapp_verify_token,
    load_config,
)

from .service import (
    ingest_archived_whatsapp_payload,
    ingest_whatsapp_inbox,
    send_template_message,
    send_text_message,
)
from .storage import (
    find_thread,
    list_inbox_files,
    list_threads,
    render_thread_markdown,
    safe_account_name,
    update_thread_status,
)
from .webhook import serve_whatsapp_webhook

console = Console()
_DESTINATION_CHOICES = click.Choice(
    ["team-inbox", "private-context", "journal", "memory"],
    case_sensitive=False,
)
_THREAD_STATUS_CHOICES = click.Choice(["new", "triaged", "waiting", "done"], case_sensitive=False)


@click.group(name="whatsapp")
def whatsapp_cli() -> None:
    """Capture WhatsApp messages, manage local threads, and send replies."""


@whatsapp_cli.command(name="setup")
@click.option("--account", default="personal", help="Named WhatsApp account to show setup for")
@click.option("--json", "as_json", is_flag=True, help="Emit setup guidance as JSON")
def setup_command(account: str, as_json: bool) -> None:
    """Show the config and provider setup checklist for a Meta WhatsApp account."""

    env_prefix = account.upper().replace("-", "_")
    payload = {
        "account": account,
        "provider": "meta",
        "config_yaml": {
            "whatsapp": {
                "default_account": account,
                "accounts": {
                    account: {
                        "provider": "meta",
                        "phone_number_id": "...",
                        "business_account_id": "...",
                        "access_token_env_var": f"JARVIS_WHATSAPP_META_TOKEN_{env_prefix}",
                        "app_secret_env_var": f"JARVIS_WHATSAPP_META_APP_SECRET_{env_prefix}",
                        "verify_token_env_var": f"JARVIS_WHATSAPP_VERIFY_TOKEN_{env_prefix}",
                        "api_version": "v24.0",
                    }
                },
            }
        },
        "env_vars": [
            f"JARVIS_WHATSAPP_META_TOKEN_{env_prefix}",
            f"JARVIS_WHATSAPP_META_APP_SECRET_{env_prefix}",
            f"JARVIS_WHATSAPP_VERIFY_TOKEN_{env_prefix}",
        ],
        "steps": [
            "Create a Meta Developer app and enable WhatsApp.",
            "Connect a WhatsApp Business Account and phone number.",
            "Add the config snippet to ~/.jarvis/config.yaml.",
            "Export the token, app secret, and verify-token env vars.",
            "Run `jarvis whatsapp webhook serve --account "
            f"{account} --port 8787` behind an HTTPS tunnel.",
            "Register the tunnel URL in Meta and subscribe to messages webhooks.",
            "Send a test message, then run `jarvis whatsapp webhook ingest-inbox`.",
        ],
    }
    if as_json:
        click.echo(json.dumps(payload, indent=2))
        return

    console.print("[bold]WhatsApp Meta Cloud API setup[/bold]")
    console.print()
    console.print("Add this shape to [cyan]~/.jarvis/config.yaml[/cyan]:")
    console.print(json.dumps(payload["config_yaml"], indent=2))
    console.print()
    console.print("Required environment variables:")
    for env_var in payload["env_vars"]:
        console.print(f"  - {env_var}")
    console.print()
    console.print("Provider setup:")
    for index, step in enumerate(payload["steps"], start=1):
        console.print(f"  {index}. {step}")


@whatsapp_cli.group(name="webhook")
def webhook_group() -> None:
    """Receive and process local WhatsApp webhooks."""


@webhook_group.command(name="serve")
@click.option("--account", default=None, help="Named WhatsApp account from config")
@click.option("--port", default=8787, help="Local port to bind")
@click.option(
    "--verify-signatures/--no-verify-signatures",
    default=True,
    help="Verify Meta webhook signatures before accepting payloads",
)
@click.option(
    "--auto-ingest/--no-auto-ingest",
    default=False,
    help="Automatically ingest verified payloads into destinations",
)
@click.option(
    "--dest",
    "destinations",
    multiple=True,
    type=_DESTINATION_CHOICES,
    help="Destination for auto-ingest: team-inbox, private-context, journal, memory",
)
@click.option("--backend", default=None, help="Backend override for journal destination")
def webhook_serve_command(
    account: str | None,
    port: int,
    verify_signatures: bool,
    auto_ingest: bool,
    destinations: tuple[str, ...],
    backend: str | None,
) -> None:
    """Run a local webhook receiver for Meta WhatsApp events."""

    callback = None
    if auto_ingest:

        def _ingest(path: Any) -> None:
            ingest_archived_whatsapp_payload(
                path,
                account=account,
                destinations=list(destinations) or None,
                backend=backend,
            )

        callback = _ingest

    try:
        serve_whatsapp_webhook(
            port=port,
            account=account,
            verify_signatures=verify_signatures,
            on_verified=callback,
        )
    except ConfigError as exc:
        console.print(f"[red]{exc}[/red]")
        raise SystemExit(1) from exc


@webhook_group.command(name="status")
@click.option("--account", default=None, help="Named WhatsApp account from config")
@click.option("--json", "as_json", is_flag=True, help="Emit status as JSON")
def webhook_status_command(account: str | None, as_json: bool) -> None:
    """Show local WhatsApp webhook config and inbox health."""

    payload = build_webhook_status(account)
    if as_json:
        click.echo(json.dumps(payload, indent=2))
        return

    table = Table(title="WhatsApp Webhook")
    table.add_column("Field")
    table.add_column("Value")
    for key, value in payload.items():
        table.add_row(key, str(value))
    console.print(table)


@webhook_group.command(name="ingest-inbox")
@click.option("--account", default=None, help="Named WhatsApp account from config")
@click.option(
    "--dest",
    "destinations",
    multiple=True,
    type=_DESTINATION_CHOICES,
    help="Destination(s): team-inbox, private-context, journal, memory",
)
@click.option("--backend", default=None, help="Backend override for journal destination")
@click.option("--limit", type=int, default=None, help="Maximum inbox items to ingest")
@click.option("--keep", is_flag=True, help="Keep inbox files in pending after ingestion")
@click.option("--json", "as_json", is_flag=True, help="Emit the result as JSON")
def webhook_ingest_inbox_command(
    account: str | None,
    destinations: tuple[str, ...],
    backend: str | None,
    limit: int | None,
    keep: bool,
    as_json: bool,
) -> None:
    """Ingest archived WhatsApp webhook payloads from the local inbox."""

    try:
        result = ingest_whatsapp_inbox(
            account=account,
            destinations=list(destinations) or None,
            backend=backend,
            limit=limit,
            keep=keep,
        )
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise SystemExit(1) from exc

    if as_json:
        click.echo(json.dumps(result.model_dump(mode="json"), indent=2))
        return
    console.print(f"[green]Ingested messages:[/green] {len(result.messages)}")
    console.print(f"[dim]Skipped duplicates:[/dim] {result.skipped_duplicates}")
    if result.errors:
        for error in result.errors:
            console.print(f"[yellow]{error}[/yellow]")


@whatsapp_cli.command(name="send")
@click.option("--account", default=None, help="Named WhatsApp account from config")
@click.option("--to", "to_number", required=True, help="Recipient phone number in E.164 form")
@click.option("--text", required=True, help="Message text")
@click.option("--preview-url/--no-preview-url", default=False, help="Enable link previews")
@click.option(
    "--window-check/--no-window-check",
    default=True,
    help="Require a local inbound message inside the WhatsApp customer-service window",
)
@click.option("--json", "as_json", is_flag=True, help="Emit the result as JSON")
def send_command(
    account: str | None,
    to_number: str,
    text: str,
    preview_url: bool,
    window_check: bool,
    as_json: bool,
) -> None:
    """Send a free-form WhatsApp reply through the Meta Cloud API."""

    try:
        result = send_text_message(
            account=account,
            to=to_number,
            text=text,
            preview_url=preview_url,
            check_window=window_check,
        )
    except (ConfigError, ValueError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise SystemExit(1) from exc
    if as_json:
        click.echo(json.dumps(result.model_dump(mode="json"), indent=2))
        return
    message_id = result.message.message_id if result.message else ""
    console.print(f"[green]Sent WhatsApp message:[/green] {message_id}")
    console.print(f"[dim]Thread:[/dim] {result.thread_id}")


@whatsapp_cli.command(name="send-template")
@click.option("--account", default=None, help="Named WhatsApp account from config")
@click.option("--to", "to_number", required=True, help="Recipient phone number in E.164 form")
@click.option("--template", required=True, help="Approved WhatsApp template name")
@click.option("--language", default="en_US", help="Template language code")
@click.option(
    "--components-json",
    default=None,
    help="Optional JSON array of template components",
)
@click.option("--json", "as_json", is_flag=True, help="Emit the result as JSON")
def send_template_command(
    account: str | None,
    to_number: str,
    template: str,
    language: str,
    components_json: str | None,
    as_json: bool,
) -> None:
    """Send an approved WhatsApp template through the Meta Cloud API."""

    try:
        components = _parse_components_json(components_json)
        result = send_template_message(
            account=account,
            to=to_number,
            template=template,
            language_code=language,
            components=components,
        )
    except (ConfigError, ValueError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise SystemExit(1) from exc
    if as_json:
        click.echo(json.dumps(result.model_dump(mode="json"), indent=2))
        return
    console.print(f"[green]Sent WhatsApp template:[/green] {template}")
    console.print(f"[dim]Thread:[/dim] {result.thread_id}")


@whatsapp_cli.group(name="threads")
def threads_group() -> None:
    """Inspect and triage local WhatsApp threads."""


@threads_group.command(name="list")
@click.option("--account", default=None, help="Named WhatsApp account from config")
@click.option("--status", "thread_status", type=_THREAD_STATUS_CHOICES, default=None)
@click.option("--limit", type=int, default=50, help="Maximum threads to show")
@click.option("--json", "as_json", is_flag=True, help="Emit threads as JSON")
def threads_list_command(
    account: str | None,
    thread_status: str | None,
    limit: int,
    as_json: bool,
) -> None:
    """List local WhatsApp conversation threads."""

    threads = list_threads(account=account, status=thread_status, limit=limit)  # type: ignore[arg-type]
    if as_json:
        click.echo(json.dumps([thread.model_dump(mode="json") for thread in threads], indent=2))
        return
    table = Table(title="WhatsApp Threads")
    table.add_column("Thread")
    table.add_column("Account")
    table.add_column("Contact")
    table.add_column("Status")
    table.add_column("Messages")
    table.add_column("Updated")
    for thread in threads:
        table.add_row(
            thread.thread_id,
            thread.account,
            thread.contact_name or thread.contact,
            thread.status,
            str(len(thread.messages)),
            thread.updated_at.isoformat(),
        )
    console.print(table)


@threads_group.command(name="read")
@click.argument("thread_id")
@click.option("--account", default=None, help="Named WhatsApp account from config")
@click.option("--json", "as_json", is_flag=True, help="Emit thread as JSON")
def threads_read_command(thread_id: str, account: str | None, as_json: bool) -> None:
    """Read one local WhatsApp conversation thread."""

    try:
        thread, _path = find_thread(thread_id, account=account)
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise SystemExit(1) from exc
    if as_json:
        click.echo(json.dumps(thread.model_dump(mode="json"), indent=2))
        return
    click.echo(render_thread_markdown(thread))


@threads_group.command(name="set-status")
@click.argument("thread_id")
@click.option("--account", default=None, help="Named WhatsApp account from config")
@click.option("--status", "thread_status", required=True, type=_THREAD_STATUS_CHOICES)
@click.option("--json", "as_json", is_flag=True, help="Emit updated thread as JSON")
def threads_set_status_command(
    thread_id: str,
    account: str | None,
    thread_status: str,
    as_json: bool,
) -> None:
    """Update the review status for one local WhatsApp thread."""

    try:
        thread = update_thread_status(
            thread_id,
            thread_status,  # type: ignore[arg-type]
            account=account,
        )
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise SystemExit(1) from exc
    if as_json:
        click.echo(json.dumps(thread.model_dump(mode="json"), indent=2))
        return
    console.print(f"[green]Updated:[/green] {thread.thread_id} -> {thread.status}")


def build_webhook_status(account: str | None) -> dict[str, Any]:
    """Build a redacted status payload for local WhatsApp webhook health."""

    cfg = load_config()
    target_account = account or cfg.whatsapp.default_account
    account_name = safe_account_name(target_account)
    account_config = None
    try:
        account_config = get_whatsapp_account_config(target_account)
    except ConfigError:
        account_config = None

    return {
        "account": account_name,
        "provider": account_config.provider if account_config else "meta",
        "phone_number_id": account_config.phone_number_id if account_config else None,
        "business_account_id": account_config.business_account_id if account_config else None,
        "api_version": account_config.api_version if account_config else None,
        "webhook_destination_url": (
            account_config.webhook_destination_url if account_config else None
        ),
        "access_token_configured": _configured(lambda: get_whatsapp_access_token(target_account)),
        "app_secret_configured": _configured(lambda: get_whatsapp_app_secret(target_account)),
        "verify_token_configured": _configured(lambda: get_whatsapp_verify_token(target_account)),
        "pending_count": len(list_inbox_files(account_name, "pending")),
        "processed_count": len(list_inbox_files(account_name, "processed")),
        "invalid_count": len(list_inbox_files(account_name, "invalid")),
    }


def _configured(loader: Any) -> bool:
    try:
        return bool(loader())
    except ConfigError:
        return False


def _parse_components_json(value: str | None) -> list[dict[str, Any]] | None:
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"--components-json must be valid JSON: {exc}") from exc
    if not isinstance(parsed, list) or not all(isinstance(item, dict) for item in parsed):
        raise ValueError("--components-json must be a JSON array of objects")
    return parsed
