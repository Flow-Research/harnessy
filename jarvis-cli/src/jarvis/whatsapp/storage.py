"""Local-first WhatsApp thread and inbox storage helpers."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .models import WhatsAppMessage, WhatsAppThread, WhatsAppThreadStatus

_USERNAME = os.environ.get("FLOW_USER", os.environ.get("USER", "default"))


def canonical_phone(value: str) -> str:
    """Normalize a phone number for stable local thread grouping."""

    digits = re.sub(r"\D+", "", value)
    return f"+{digits}" if digits else value.strip()


def safe_account_name(account: str | None) -> str:
    """Normalize account names for local paths."""

    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", (account or "default").strip()).strip(".-")
    return cleaned.lower() or "default"


def whatsapp_root() -> Path:
    """Resolve the private context root for WhatsApp channel state."""

    return _resolve_private_context_root() / "whatsapp"


def inbox_dir(account: str | None, state: str = "pending") -> Path:
    """Resolve the local inbox directory for archived WhatsApp payloads."""

    target = whatsapp_root() / safe_account_name(account) / "inbox" / state
    target.mkdir(parents=True, exist_ok=True)
    return target


def threads_dir(account: str | None) -> Path:
    """Resolve the local thread store directory for one account."""

    target = whatsapp_root() / safe_account_name(account) / "threads"
    target.mkdir(parents=True, exist_ok=True)
    return target


def thread_id_for(account: str | None, contact: str) -> str:
    """Return a stable opaque thread ID for an account/contact pair."""

    basis = f"{safe_account_name(account)}:{canonical_phone(contact)}"
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]
    return f"wa-{digest}"


def thread_json_path(account: str | None, thread_id: str) -> Path:
    """Return the JSON thread path for one account/thread."""

    return threads_dir(account) / f"{thread_id}.json"


def thread_markdown_path(account: str | None, thread_id: str) -> Path:
    """Return the Markdown thread path for one account/thread."""

    return threads_dir(account) / f"{thread_id}.md"


def list_inbox_files(account: str | None, state: str = "pending") -> list[Path]:
    """List archived webhook payload files for one account and state."""

    return sorted(inbox_dir(account, state=state).glob("*.json"))


def load_archived_payload(path: Path) -> dict[str, Any]:
    """Load an archived webhook payload wrapper."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def move_inbox_file(path: Path, account: str | None, state: str) -> Path:
    """Move an inbox file into a new processing state."""

    destination = inbox_dir(account, state=state) / path.name
    if destination.exists():
        destination = destination.with_name(f"{destination.stem}-{uuid4().hex}{destination.suffix}")
    path.replace(destination)
    return destination


def mark_inbox_file_invalid(path: Path, account: str | None, error: str) -> Path:
    """Attach a useful error to an archived payload, then move it to invalid."""

    try:
        wrapper = load_archived_payload(path)
    except Exception:
        wrapper = {"payload": None}
    wrapper["error"] = error
    wrapper["invalid_at"] = datetime.now(UTC).isoformat()
    path.write_text(json.dumps(wrapper, indent=2, sort_keys=True), encoding="utf-8")
    return move_inbox_file(path, account, "invalid")


def load_thread(account: str | None, thread_id: str) -> WhatsAppThread:
    """Load one thread from JSON storage."""

    path = thread_json_path(account, thread_id)
    if not path.exists():
        raise FileNotFoundError(f"WhatsApp thread not found: {thread_id}")
    return WhatsAppThread.model_validate_json(path.read_text(encoding="utf-8"))


def find_thread(thread_id: str, account: str | None = None) -> tuple[WhatsAppThread, Path]:
    """Find a thread by ID, optionally scoped to one account."""

    if account:
        thread = load_thread(account, thread_id)
        return thread, thread_json_path(account, thread_id)

    root = whatsapp_root()
    for path in sorted(root.glob(f"*/threads/{thread_id}.json")):
        thread = WhatsAppThread.model_validate_json(path.read_text(encoding="utf-8"))
        return thread, path
    raise FileNotFoundError(f"WhatsApp thread not found: {thread_id}")


def list_threads(
    *,
    account: str | None = None,
    status: WhatsAppThreadStatus | None = None,
    limit: int | None = None,
) -> list[WhatsAppThread]:
    """List local WhatsApp threads sorted by most recently updated."""

    paths = sorted(threads_dir(account).glob("*.json")) if account else sorted(
        whatsapp_root().glob("*/threads/*.json")
    )
    threads: list[WhatsAppThread] = []
    for path in paths:
        try:
            thread = WhatsAppThread.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if status and thread.status != status:
            continue
        threads.append(thread)
    threads.sort(key=lambda thread: thread.updated_at, reverse=True)
    return threads[:limit] if limit is not None else threads


def append_message_to_thread(message: WhatsAppMessage) -> tuple[WhatsAppThread, bool, list[Path]]:
    """Append a message to its local thread if it is not already present."""

    contact = canonical_phone(message.contact_phone)
    thread_id = thread_id_for(message.account, contact)
    json_path = thread_json_path(message.account, thread_id)
    markdown_path = thread_markdown_path(message.account, thread_id)

    if json_path.exists():
        thread = WhatsAppThread.model_validate_json(json_path.read_text(encoding="utf-8"))
    else:
        thread = WhatsAppThread(
            thread_id=thread_id,
            account=safe_account_name(message.account),
            contact=contact,
            contact_name=message.contact_name,
        )

    if any(existing.message_id == message.message_id for existing in thread.messages):
        return thread, False, [json_path, markdown_path]

    if message.contact_name and not thread.contact_name:
        thread.contact_name = message.contact_name
    thread.messages.append(message)
    thread.updated_at = max(message.timestamp, datetime.now(UTC))
    _write_thread(thread, json_path, markdown_path)
    return thread, True, [json_path, markdown_path]


def update_thread_status(
    thread_id: str,
    status: WhatsAppThreadStatus,
    *,
    account: str | None = None,
) -> WhatsAppThread:
    """Update the review status for a local WhatsApp thread."""

    thread, path = find_thread(thread_id, account=account)
    thread.status = status
    thread.updated_at = datetime.now(UTC)
    markdown_path = path.with_suffix(".md")
    _write_thread(thread, path, markdown_path)
    return thread


def render_thread_markdown(thread: WhatsAppThread) -> str:
    """Render a local thread as readable Markdown."""

    lines = [
        f"# WhatsApp Thread {thread.thread_id}",
        "",
        f"- Account: {thread.account}",
        f"- Contact: {thread.contact}",
        f"- Contact Name: {thread.contact_name or ''}",
        f"- Status: {thread.status}",
        f"- Updated: {thread.updated_at.isoformat()}",
        "",
        "## Messages",
        "",
    ]
    for message in sorted(thread.messages, key=lambda item: item.timestamp):
        label = message.direction.title()
        if message.direction == "status":
            label = f"Status: {message.status or 'unknown'}"
        body = message.text or _fallback_message_summary(message)
        lines.extend(
            [
                f"### {message.timestamp.isoformat()} - {label}",
                "",
                f"- Message ID: {message.message_id}",
                f"- Type: {message.message_type}",
                f"- From: {message.sender}",
                f"- To: {message.recipient}",
                "",
                body,
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _write_thread(thread: WhatsAppThread, json_path: Path, markdown_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(thread.model_dump(mode="json"), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    markdown_path.write_text(render_thread_markdown(thread), encoding="utf-8")


def _fallback_message_summary(message: WhatsAppMessage) -> str:
    if message.media:
        parts = [str(message.media.get("caption") or "").strip()]
        media_id = str(message.media.get("id") or "").strip()
        if media_id:
            parts.append(f"Media ID: `{media_id}`")
        return "\n".join(part for part in parts if part) or "[media attachment]"
    if message.location:
        return json.dumps(message.location, indent=2, sort_keys=True)
    if message.contacts:
        return json.dumps(message.contacts, indent=2, sort_keys=True)
    return "[no text]"


def _resolve_private_context_root() -> Path:
    """Locate `.jarvis/context/private/<user>` from the current workspace."""

    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        user_ctx = parent / ".jarvis" / "context" / "private" / _USERNAME
        if user_ctx.is_dir():
            user_ctx.mkdir(parents=True, exist_ok=True)
            return user_ctx
    fallback = cwd / ".jarvis" / "context" / "private" / _USERNAME
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback
